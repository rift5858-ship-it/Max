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
TOKEN = os.getenv("TOKEN", "8470584192:AAEi27EX-LPOLZhGPcR2U7_wON-Ic6NXY6s")
PORT = int(os.environ.get("PORT", 10000))
APP_URL = os.getenv("APP_URL", "") # Render မှာရတဲ့ URL ကို Environment Variable ထဲထည့်ပါ

logging.basicConfig(level=logging.ERROR)

# --- INTERNAL SEARCH ENGINE ---
class SearchCore:
    @staticmethod
    def execute(category, query):
        # Logic: Entertainment အတွက် MmSub, Mm Sub နှင့် မြန်မာစာ ပါဝင်မှုကို နောက်ကွယ်မှ တွဲပေးခြင်း
        if category in ["MOVIE", "SERIES"]:
            search_query = f"{query} (MmSub OR \"Mm Sub\" OR \"မြန်မာ\") site:t.me/s/"
        else: # Music logic
            search_query = f"{query} site:t.me/s/"
            
        results = []
        try:
            # DDGS Version 6.0+ တွင် Async အစား Synchronous mode ဖြင့် Error ကင်းအောင်သုံးခြင်း
            with DDGS() as ddgs:
                search_results = ddgs.text(search_query, max_results=10)
                for r in search_results:
                    title = r.get('title', 'No Title')
                    link = r.get('href', '')
                    
                    if "t.me/s/" in link:
                        # Internal Link Fixer: App ထဲတန်းရောက်အောင် /s/ ကို ဖြုတ်ခြင်း
                        clean_link = link.replace("t.me/s/", "t.me/")
                        results.append(f"📌 **{title}**\n🔗 {clean_link}")
            
            return "\n\n".join(results) if results else "∅ ရှာမတွေ့ပါသဖြင့် အခြားနာမည်ဖြင့် ထပ်စမ်းကြည့်ပါ။"
        except Exception as e:
            print(f"Internal Search Error: {e}")
            return "⚠️ စနစ်အတွင်း အမှားအယွင်းရှိနေပါသည်။ ခဏနေမှ ပြန်စမ်းပါ။"

# --- BOT INTERFACE ---
search_engine = SearchCore()

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("🎬 Movies", callback_data='MOVIE'), InlineKeyboardButton("📺 Series", callback_data='SERIES')],
        [InlineKeyboardButton("🎵 Music", callback_data='MUSIC')]
    ]
    await update.message.reply_text(
        "**MmSub Search Bot** မှ ကြိုဆိုပါသည်။\nရှာဖွေလိုသည့် Category ကို ရွေးချယ်ပါ-",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode=constants.ParseMode.MARKDOWN
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['cat'] = query.data
    await query.edit_message_text(f"🌐 **{query.data}** Mode ပြောင်းလိုက်ပါပြီ။\nကားနာမည် သို့မဟုတ် သီချင်းနာမည် ပို့ပေးပါ။")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cat = context.user_data.get('cat', 'MOVIE')
    user_text = update.message.text
    
    # Typing Action
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)
    
    # Run search in a separate thread if necessary or directly
    response = search_engine.execute(cat, user_text)
    
    await update.message.reply_text(
        f"🔎 **Search Results for:** {user_text}\n\n{response}",
        parse_mode=constants.ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )

# --- KEEP-ALIVE SYSTEM ---
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
            time.sleep(600)
        except:
            time.sleep(60)

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=self_ping, daemon=True).start()
    
    bot_app = ApplicationBuilder().token(TOKEN).build()
    
    bot_app.add_handler(CommandHandler("start", cmd_start))
    bot_app.add_handler(CallbackQueryHandler(handle_callback))
    bot_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("Bot is running...")
    bot_app.run_polling(drop_pending_updates=True)
