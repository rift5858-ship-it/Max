import os, logging, threading, time, requests
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CallbackQueryHandler, CommandHandler
from duckduckgo_search import DDGS

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
TOKEN = "8470584192:AAEi27EX-LPOLZhGPcR2U7_wON-Ic6NXY6s"  # <--- မင်းရဲ့ Token ကို ဒီမှာ အစားထိုးပါ
APP_URL = "https://maxx-bot.onrender.com"
PORT = int(os.environ.get("PORT", 10000))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- OPTIMIZED SEARCH ENGINE ---
class SmartSearch:
    @staticmethod
    def execute(category, query):
        results = []
        # Browser တစ်ခုလို ဟန်ဆောင်ရန် Headers (IP Block ကာကွယ်ရန်)
        search_modifiers = "Myanmar Subtitle Telegram Channel" if category != "MUSIC" else "Telegram MP3 Myanmar"
        full_query = f"{query} {search_modifiers} site:t.me"

        try:
            # DuckDuckGo ကို ပိုမိုခိုင်မာသော နည်းလမ်းဖြင့် ခေါ်ယူခြင်း
            with DDGS() as ddgs:
                # timelimit='y' (Last Year) ထည့်ခြင်းဖြင့် ပိုလတ်ဆတ်သော Result ရစေသည်
                ddgs_results = ddgs.text(full_query, max_results=15)
                
                for r in ddgs_results:
                    link = r.get('href', '')
                    title = r.get('title', 'No Title')
                    
                    if "t.me" in link:
                        # Link Fixer
                        clean_link = link.replace("t.me/s/", "t.me/").split('?')[0]
                        if clean_link not in [res['link'] for res in results]:
                            results.append({'title': title, 'link': clean_link})
            
            if not results:
                return "∅ ဘာမှရှာမတွေ့ပါ။ နာမည်ကို အင်္ဂလိပ်လို အတိအကျ ပြန်ရိုက်ကြည့်ပါ။"
            
            output = f"🔎 **Results for:** {query}\n\n"
            for res in results[:8]:
                output += f"📌 **{res['title']}**\n🔗 {res['link']}\n\n"
            return output

        except Exception as e:
            logger.error(f"Search Error: {e}")
            return "⚠️ ရှာဖွေမှု ခေတ္တရပ်ဆိုင်းနေပါသည်။ ခဏနေမှ ပြန်စမ်းပါ။"

# --- BOT HANDLERS ---
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("🎬 Movie/Series", callback_data='MOVIE'), InlineKeyboardButton("🎵 Music", callback_data='MUSIC')]]
    await update.message.reply_text("👋 **MmSub Search Bot Pro**\n\nဘာရှာချင်လဲ ရွေးပါ-", 
                                   reply_markup=InlineKeyboardMarkup(kb), parse_mode=constants.ParseMode.MARKDOWN)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['cat'] = query.data
    await query.edit_message_text(f"✅ **{query.data}** Mode Active!\n\nနာမည်ရိုက်ပို့ပေးပါ။")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cat = context.user_data.get('cat', 'MOVIE')
    msg = await update.message.reply_text("🔎 ရှာဖွေနေပါသည်...")
    
    response = SmartSearch.execute(cat, update.message.text)
    
    await msg.delete()
    await update.message.reply_text(response, parse_mode=constants.ParseMode.MARKDOWN, disable_web_page_preview=True)

# --- WEB SERVER & KEEP ALIVE ---
app = Flask(__name__)
@app.route('/')
def health(): return "Bot is Online", 200

def run_flask(): app.run(host='0.0.0.0', port=PORT)

def keep_alive():
    while True:
        try: requests.get(APP_URL)
        except: pass
        time.sleep(600)

# --- MAIN ---
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()
    
    print("Bot is starting...")
    # drop_pending_updates=True က Conflict ဖြစ်တဲ့ Message တွေကို ရှင်းပစ်ပါတယ်
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    application.run_polling(drop_pending_updates=True)
