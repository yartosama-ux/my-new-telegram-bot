import os
import asyncio
import threading
import time
import random
import requests

from flask import Flask
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================================================
# CONFIG
# =========================================================

TOKEN = os.getenv("TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

MODEL = "gemini-3.1-flash-lite"

GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/"
    f"v1beta/models/{MODEL}:generateContent"
)

if not TOKEN:
    raise RuntimeError("TOKEN is missing")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is missing")


# =========================================================
# HTTP SESSION
# =========================================================

session = requests.Session()

adapter = requests.adapters.HTTPAdapter(
    pool_connections=20,
    pool_maxsize=20,
    max_retries=0,
)

session.mount("https://", adapter)

HEADERS = {
    "x-goog-api-key": GEMINI_API_KEY,
    "Content-Type": "application/json",
}


# =========================================================
# LANGUAGE DETECTION
# =========================================================

def detect_language(text: str) -> str:

    for ch in text:
        code = ord(ch)

        # Myanmar
        if 0x1000 <= code <= 0x109F:
            return "myanmar"

        # Chinese
        if (
            0x4E00 <= code <= 0x9FFF
            or 0x3400 <= code <= 0x4DBF
        ):
            return "chinese"

    return "unknown"


# =========================================================
# PROMPTS
# =========================================================

MYANMAR_TO_CHINESE = """
Translate the following Myanmar message into natural, professional Chinese.

Use polite customer-service language.
Preserve the exact meaning.
Do not add, remove, explain, or summarize information.
Return ONLY the Chinese translation.

TEXT:
"""

CHINESE_TO_SPANISH_BURMESE = """
Translate the following Chinese message into BOTH Spanish and Burmese.

Spanish:
- Use professional, polite Venezuelan customer-service language.
- Natural and suitable for communicating with a customer or client.
- Preserve the exact meaning.
- Do not add or remove information.

Burmese:
- Use clear, natural Burmese.
- Preserve the exact meaning.
- Do not add or remove information.

Return ONLY in this format:

🇪🇸 Español:
[Spanish translation]

🇲🇲 မြန်မာ:
[Burmese translation]

TEXT:
"""


# =========================================================
# GEMINI TRANSLATION
# =========================================================

def gemini_translate(text: str, language: str) -> str:

    if language == "myanmar":
        prompt = MYANMAR_TO_CHINESE + text

    elif language == "chinese":
        prompt = CHINESE_TO_SPANISH_BURMESE + text

    else:
        raise ValueError(
            "Only Myanmar and Chinese are supported."
        )

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 800,
            "thinkingConfig": {
                "thinkingLevel": "minimal"
            }
        }
    }

    for attempt in range(2):

        start = time.perf_counter()

        try:

            response = session.post(
                GEMINI_URL,
                headers=HEADERS,
                json=payload,
                timeout=(5, 20),
            )

            elapsed = time.perf_counter() - start

            print(
                f"Gemini | {language} | "
                f"status={response.status_code} | "
                f"time={elapsed:.2f}s | "
                f"attempt={attempt + 1}"
            )

            # SUCCESS
            if response.status_code == 200:

                data = response.json()

                candidates = data.get(
                    "candidates",
                    []
                )

                if not candidates:
                    raise RuntimeError(
                        "Gemini returned no candidates"
                    )

                parts = (
                    candidates[0]
                    .get("content", {})
                    .get("parts", [])
                )

                result = "".join(
                    part.get("text", "")
                    for part in parts
                    if part.get("text")
                ).strip()

                if not result:
                    raise RuntimeError(
                        "Gemini returned empty text"
                    )

                return result

            # TEMPORARY ERRORS
            if response.status_code in (
                408,
                429,
                500,
                502,
                503,
                504,
            ):

                if attempt == 0:

                    wait = (
                        0.8 +
                        random.uniform(0, 0.4)
                    )

                    print(
                        f"Temporary Gemini error "
                        f"{response.status_code}; "
                        f"retrying in "
                        f"{wait:.2f}s"
                    )

                    time.sleep(wait)
                    continue

            # OTHER ERRORS
            try:

                error_data = response.json()

                error_message = (
                    error_data
                    .get("error", {})
                    .get(
                        "message",
                        response.text[:500]
                    )
                )

            except Exception:

                error_message = response.text[:500]

            raise RuntimeError(
                f"Gemini API error "
                f"{response.status_code}: "
                f"{error_message}"
            )

        except requests.Timeout:

            print(
                f"Gemini timeout | "
                f"attempt={attempt + 1}"
            )

            if attempt == 0:

                time.sleep(0.5)
                continue

            raise RuntimeError(
                "Gemini response timeout"
            )

        except requests.RequestException as e:

            print(
                f"Gemini network error: {e}"
            )

            if attempt == 0:

                time.sleep(0.5)
                continue

            raise RuntimeError(
                "Gemini network error"
            )

    raise RuntimeError(
        "Gemini request failed"
    )


# =========================================================
# START COMMAND
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "မင်္ဂလာပါ 👋\n\n"
        "🇲🇲 မြန်မာ → 🇨🇳 တရုတ်\n"
        "🇨🇳 တရုတ် → 🇪🇸 စပိန် + 🇲🇲 မြန်မာ\n\n"
        "စာပို့လိုက်ရုံနဲ့ ဘာသာပြန်ပေးပါမယ်။"
    )


# =========================================================
# MESSAGE HANDLER
# =========================================================

async def translate_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if not update.message.text:
        return

    text = update.message.text.strip()

    if not text:
        return

    # Maximum message length
    if len(text) > 5000:

        await update.message.reply_text(
            "⚠️ စာအရမ်းရှည်နေပါတယ်။ "
            "စာကို အပိုင်းခွဲပြီး ပို့ပေးပါ။"
        )

        return

    language = detect_language(text)

    # Unsupported language
    if language == "unknown":

        await update.message.reply_text(
            "⚠️ လောလောဆယ် မြန်မာစာနဲ့ "
            "တရုတ်စာကိုသာ ဘာသာပြန်ပေးနိုင်ပါတယ်။"
        )

        return

    status_message = await update.message.reply_text(
        "⚡ ဘာသာပြန်နေပါတယ်..."
    )

    try:

        result = await asyncio.to_thread(
            gemini_translate,
            text,
            language
        )

        await status_message.edit_text(
            result
        )

    except Exception as e:

        print(
            f"Translation error: {repr(e)}"
        )

        await status_message.edit_text(
            "⚠️ ခဏတာ ဘာသာပြန်မရသေးပါ။ "
            "ခဏအကြာ ပြန်ပို့ပေးပါ။"
        )


# =========================================================
# RENDER HEALTH SERVER
# =========================================================

app = Flask(__name__)


@app.route("/")
def health():

    return "Myanmar-Chinese Customer Service Bot is running."


def run_health_server():

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )


# =========================================================
# MAIN
# =========================================================

def main():

    # Render health server
    threading.Thread(
        target=run_health_server,
        daemon=True
    ).start()

    # Telegram bot
    application = (
        Application.builder()
        .token(TOKEN)
        .concurrent_updates(8)
        .build()
    )

    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            translate_message
        )
    )

    print(
        "🚀 Myanmar-Chinese Customer Service Bot started"
    )

    application.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
