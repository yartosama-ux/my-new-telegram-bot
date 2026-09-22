import logging
import os
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = "8631809233:AAFdyh_E9vKjs92jqGQviGCJ34wyeDNPdEo"
OPENAI_API_KEY = "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"

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def openai_translate(text, system_prompt):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-3.5-turbo",  # ပိုမိုကျယ်ပြန့်စွာ အလုပ်လုပ်သော Model သို့ ပြောင်းထားပါသည်
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ],
        "temperature": 0.3
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=20)
        if response.status_code == 200:
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        else:
            logging.error(f"OpenAI API Error: {response.text}")
            return f"API Error: {response.status_code}"
    except Exception as e:
        logging.error(f"Exception: {e}")
        return "Connection Error occurred."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "မင်္ဂလာပါ။ Manager-Style Translate Bot သို့ ကြိုဆိုပါတယ်။\n\n"
        "- **မြန်မာစာ** ပို့ပါက -> စပိန် (Venezuela Manager Style) နှင့် အင်္ဂလိပ် ဘာသာပြန်ပေးပါမည်။\n"
        "- **အင်္ဂလိပ်/စပိန်စာ** ပို့ပါက -> စပိန် (Venezuela Manager Style) နှင့် မြန်မာဘာသာ ပြန်ပေးပါမည်။"
    )

async def translate_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text:
        return

    try:
        is_myanmar = any('\u1000' <= char <= '\u109f' for char in text)
        
        if is_myanmar:
            spanish_manager = openai_translate(text, "Translate this text into polite, professional Venezuelan Spanish manager style using 'Usted'. Return ONLY the translated text.")
            english_trans = openai_translate(text, "Translate this text into professional English. Return ONLY the translated text.")
            
            final_result = (
                f"🇪🇸 Spanish (Venezuela Manager Style):\n{spanish_manager}\n\n"
                f"🇬🇧 English (Professional):\n{english_trans}"
            )
        else:
            spanish_manager = openai_translate(text, "Translate this text into polite, professional Venezuelan Spanish manager style using 'Usted'. Return ONLY the translated text.")
            myanmar_trans = openai_translate(text, "Translate this text into natural, clear Myanmar (Burmese) language. Return ONLY the translated text.")
            
            final_result = (
                f"🇪🇸 Spanish (Venezuela Manager Style):\n{spanish_manager}\n\n"
                f"🇲🇲 မြန်မာဘာသာပြန်:\n{myanmar_trans}"
            )
            
        await update.message.reply_text(final_result)
    except Exception as e:
        logging.error(f"General Error: {e}")
        await update.message.reply_text("ဘာသာပြန်ရာတွင် အမှားအယွင်း ရှိနေပါသည်။")

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running alive!")

def run_health_check_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

if __name__ == '__main__':
    threading.Thread(target=run_health_check_server, daemon=True).start()
    
    app = ApplicationBuilder().token(TOKEN).job_queue(None).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, translate_text))
    
    print("Translate Bot အလုပ်လုပ်နေပါပြီ...")
    app.run_polling()