import os
import logging
import threading
import time
import requests
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
    CommandHandler,
)
from duckduckgo_search import DDGS

# --- CONFIGURATION ---
# Render Environment Variable မှ Token ကို ယူမည်
TOKEN = os.getenv("8470584192:AAEi27EX-LPOLZhGPcR2U7_wON-Ic6NXY6s")
PORT = int(os.environ.get("PORT", 10000))
APP_URL = os.getenv("APP_URL", "")

# Logging ဖွင့်ထားခြင်း (Error ရှာရန်)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- SEARCH ENGINE CORE (Fixed Logic) ---
class SearchCore:
    @staticmethod
    def execute(category, query):
        results = []
        try:
            # Logic: site:t.me ကို ရှေ့ဆုံးကထားပြီး Keyword ကို Broad ဖြစ်အောင် ပြင်ဆင်ခြင်း
            if category in ["MOVIE", "SERIES"]:
                # "Channel" နဲ့ "Myanmar" ကို ထည့်ရှာမှ ပိုတိကျပြီး ကျယ်ပြန့်မည်
                search_query = f"site:t.me {query} Myanmar Channel"
            else:
                # Music အတွက်
                search_query = f"site:t.me {query} mp3 audio"

            print(f"Searching for: {search_query}") # Log မှာ ပြန်ကြည့်လို့ရအောင်

            with DDGS() as ddgs:
                # max_results ကို ၂၀ အထိ တိုးထားသည်
                search_results = ddgs.text(search_query, max_results=20)
                
                for r in search_results:
                    title = r.get('title', 'No Title')
                    link = r.get('href', '')
                    
                    # Telegram link အစစ်ဖြစ်မှ ယူမည်
                    if "t.me/" in link:
                        # Link Cleaning:
                        # 1. t.me/s/ ပါရင် t.me/ ပြောင်းမယ် (Direct App Link)
                        # 2. ?start= တို့ဘာတို့ ပါရင် ဖယ်ထုတ်မယ် (Clean Link)
                        clean_link = link.replace("t.me/s/", "t.me/")
                        if "?" in clean_link:
                            clean_link = clean_link.split("?")[0]
                        
                        # Duplicate မဖြစ်အောင် စစ်ဆေးခြင်း
                        if clean_link not in [res['link'] for res in results]:
                            results.append({'title': title, 'link': clean_link})

            # Formatting Results for Telegram
            if not results:
                # ဒုတိယ အကြိမ် ထပ်ရှာခြင်း (Fallback Search - Less Strict)
                print("First attempt failed. Trying fallback...")
                with DDGS() as ddgs:
                    fallback_query = f"site:t.me {query}"
                    fallback_results = ddgs.text(fallback_query, max_results=5)
                    for r in fallback_results:
                        if "t.me/" in r.get('href', ''):
                            clean_link = r.get('href').replace("t.me/s/", "t.me/")
                            results.append({'title': r.get('title'), 'link': clean_link})

            if results:
                final_text = []
                for res in results[:10]: # Top 10 ပဲ ပြမယ်
                    final_text.append(f"📌 **{res['title']}**\n🔗 {res['link']}")
                return "\n\n".join(final_text)
            else:
                return "∅ ရှာမတွေ့ပါသဖြင့် အခြားနာမည် (English/Myannglish) ပြောင်းပြီး ထပ်စမ်းကြည့်ပါ။"

        except Exception as e:
            logger.error(f"Search Error: {e}")
            return "⚠️ Search Engine Error. ခဏနေမှ ပြန်စမ်းပါ။"

# --- BOT INTERFACE ---
search_engine = SearchCore()

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("🎬 Movies", callback_data='MOVIE'), InlineKeyboardButton("📺 Series", callback_data='SERIES')],
        [InlineKeyboardButton("🎵 Music", callback_data='MUSIC')]
    ]
    await update.message.reply_text(
        "**MmSub Search Bot** မှ ကြိုဆိုပါသည်။\n\nဘာရှာဖွေချင်ပါသလဲ?",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode=constants.ParseMode.MARKDOWN
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['cat'] = query.data
    await query.edit_message_text(
        f"✅ **{query.data}** Mode ရွေးချယ်ထားသည်။\n\n🔎 ရှာလိုသည့် ကားနာမည်/သီချင်းနာမည် ရိုက်ထည့်ပါ။"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cat = context.user_data.get('cat', 'MOVIE')
    user_text = update.message.text
    
    if not user_text:
        return

    # User ကို စောင့်ခိုင်းခြင်း (Typing status)
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)
    
    # ရှာဖွေခြင်း
    response = search_engine.execute(cat, user_text)
    
    await update.message.reply_text(
        f"🔎 **Results for:** {user_text}\n\n{response}",
        parse_mode=constants.ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )

# --- FLASK KEEP-ALIVE ---
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is Active", 200

def run_flask():
    app.run(host='0.0.0.0', port=PORT)

def self_ping():
    if not APP_URL: return
    while True:
        try:
            requests.get(APP_URL)
        except:
            pass
        time.sleep(600)

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    # Start Flask Server
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=self_ping, daemon=True).start()
    
    # Check Token
    if not TOKEN:
        print("Error: TOKEN is missing in Environment Variables!")
    else:
        print("Bot is starting...")
        bot_app = ApplicationBuilder().token(TOKEN).build()
        
        bot_app.add_handler(CommandHandler("start", cmd_start))
        bot_app.add_handler(CallbackQueryHandler(handle_callback))
        bot_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        
        bot_app.run_polling(drop_pending_updates=True)
