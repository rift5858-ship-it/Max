import logging
import threading
import time
import requests
import os
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

# ==========================================
# ⚙️ CONFIGURATION (USER SETTINGS)
# ==========================================

# ⚠️ မင်းရဲ့ Token ကို ဒီ '' ကြားထဲမှာ ထည့်ပါ (Render Settings မလိုတော့ပါ)
TOKEN = "8470584192:AAEi27EX-LPOLZhGPcR2U7_wON-Ic6NXY6s" 

# Render URL (Keep-Alive အတွက်) - မင်းရဲ့ Render Link ကို ဒီမှာထည့်ပါ
APP_URL = "https://maxx-bot.onrender.com"

# ==========================================

PORT = int(os.environ.get("PORT", 10000))
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- SMART SEARCH ENGINE (NO GOOGLE API REQUIRED) ---
class SmartSearch:
    @staticmethod
    def clean_link(link):
        """Telegram Link တွေကို App ထဲတန်းရောက်အောင် ပြင်ပေးမည့် Function"""
        if "t.me/" in link:
            # Preview link (/s/) ကို ဖယ်ရှားခြင်း
            clean = link.replace("t.me/s/", "t.me/")
            # Link အနောက်က အပိုတွေ (?start=...) ဖြတ်ထုတ်ခြင်း
            if "?" in clean:
                clean = clean.split("?")[0]
            return clean
        return None

    @staticmethod
    def execute(category, query):
        results = []
        unique_links = set()
        
        # Step 1: Search Queries Preparation
        # (A) Primary: Myanmar Subtitles အဓိကထားရှာမယ်
        if category in ["MOVIE", "SERIES"]:
            queries_to_try = [
                f"site:t.me {query} (Myanmar OR MmSub OR \"မြန်မာစာတန်းထိုး\")", # Very Specific
                f"site:t.me {query} Channel", # Broad Channel Search
            ]
        else:
            queries_to_try = [
                f"site:t.me {query} mp3 Myanmar",
                f"site:t.me {query} audio",
            ]

        # Step 2: Execute Search (Cascade Logic)
        print(f"🔎 Smart Search started for: {query}")
        
        with DDGS() as ddgs:
            for q in queries_to_try:
                try:
                    # တစ်ခါရှာရင် Result ၁၀ ခု ယူမယ်
                    ddgs_gen = ddgs.text(q, max_results=10)
                    if ddgs_gen:
                        for r in ddgs_gen:
                            title = r.get('title', 'No Title')
                            raw_link = r.get('href', '')
                            
                            final_link = SmartSearch.clean_link(raw_link)
                            
                            # Valid Link ဖြစ်ပြီး၊ အရင်မထပ်သေးရင် List ထဲထည့်မယ်
                            if final_link and final_link not in unique_links:
                                unique_links.add(final_link)
                                results.append(f"📌 **{title}**\n🔗 {final_link}")
                except Exception as e:
                    print(f"Error in query '{q}': {e}")
                    continue
                
                # Result ၅ ခုပြည့်ရင် ဆက်မရှာတော့ဘူး (Speed အရေးကြီးလို့)
                if len(results) >= 5:
                    break
        
        # Step 3: Fallback (ဘာမှမတွေ့ရင် Global Search လုပ်မယ်)
        if not results:
            print("⚠️ Primary search failed. Trying Global Fallback...")
            try:
                with DDGS() as ddgs:
                    fallback = ddgs.text(f"site:t.me {query}", max_results=5)
                    for r in fallback:
                        l = SmartSearch.clean_link(r.get('href', ''))
                        if l and l not in unique_links:
                            unique_links.add(l)
                            results.append(f"🌐 **{r.get('title')}**\n🔗 {l}")
            except:
                pass

        # Final Output Generation
        if results:
            header = f"🔎 **Results for:** {query}\n(Total: {len(results)} found)\n\n"
            return header + "\n\n".join(results[:10]) # Top 10 ပဲ ပြမယ်
        else:
            return "❌ **ရှာမတွေ့ပါ။**\n\n• စာလုံးပေါင်း မှန်မမှန် စစ်ပါ။\n• English နာမည်ဖြင့် ရှာကြည့်ပါ။\n(ဥပမာ: 'Squid Game' အစား 'Squid Game Season 1' ဟု တိတိကျကျ ရိုက်ပါ)"

# --- BOT INTERFACE ---
search_engine = SmartSearch()

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("🎬 Movies", callback_data='MOVIE'), InlineKeyboardButton("📺 Series", callback_data='SERIES')],
        [InlineKeyboardButton("🎵 Music", callback_data='MUSIC')]
    ]
    await update.message.reply_text(
        "👋 **Hello! MmSub Search Bot မှ ကြိုဆိုပါသည်။**\n\nဒီ Bot က Telegram Channel ပေါင်းစုံမှ ရုပ်ရှင်များကို အလွယ်တကူ ရှာပေးနိုင်ပါတယ်။\n\nရွေးချယ်ပါ:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode=constants.ParseMode.MARKDOWN
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['cat'] = query.data
    await query.edit_message_text(
        f"✅ **{query.data}** Mode Active!\n\n✍️ ရှာလိုသော ခေါင်းစဉ်ကို ရိုက်ထည့်ပါ။"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cat = context.user_data.get('cat', 'MOVIE')
    user_text = update.message.text
    
    if not user_text: return

    status_msg = await update.message.reply_text("🔎 ရှာဖွေနေသည်... ခဏစောင့်ပါ...")
    
    # Run Search
    response = search_engine.execute(cat, user_text)
    
    # Delete "Searching..." message and send results
    await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=status_msg.message_id)
    await update.message.reply_text(
        response,
        parse_mode=constants.ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )

# --- SYSTEM KEEP-ALIVE ---
app = Flask(__name__)

@app.route('/')
def health():
    return "Bot is Running!", 200

def run_flask():
    app.run(host='0.0.0.0', port=PORT)

def keep_alive():
    while True:
        try:
            if APP_URL.startswith("http"):
                requests.get(APP_URL)
                print("Ping sent to keep bot alive.")
        except:
            pass
        time.sleep(600) # 10 minutes

if __name__ == "__main__":
    # Flask & Keep-Alive Starting
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()
    
    # Token Validation
    if TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ ERROR: Code ထဲမှာ Token မထည့်ရသေးပါ။ main.py ကို ပြန်ပြင်ပါ။")
    else:
        print("✅ Bot Starting with Smart Search Engine...")
        application = ApplicationBuilder().token(TOKEN).build()
        
        application.add_handler(CommandHandler("start", cmd_start))
        application.add_handler(CallbackQueryHandler(handle_callback))
        application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        
        application.run_polling(drop_pending_updates=True)
