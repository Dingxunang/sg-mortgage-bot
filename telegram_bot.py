import os
import requests
import re
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai

# ==========================================
# 1. MAS SORA DATA FETCHING
# ==========================================
def get_latest_sora_rates():
    url = "https://eservices.mas.gov.sg/api/action/datastore/search.json"
    params = {
        "resource_id": "5f2b18a5-1174-48e2-a3c1-0c3fbcd299e5",
        "sort": "end_of_day desc",
        "limit": 1
    }
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        records = data.get("result", {}).get("records", [])
        if not records:
            raise ValueError("No records returned.")
        latest = records[0]
        return {
            "date": latest.get("end_of_day", "Unknown Date"),
            "sora_daily": float(latest.get("sora", 0.0)),
            "sora_3m": float(latest.get("sora_comp_3m", 0.0))
        }
    except Exception as e:
        print(f"SORA Fetch Error: {e}")
        return {"date": "Fallback Baseline (Recent)", "sora_daily": 3.45, "sora_3m": 3.55}

# ==========================================
# 2. OCBC FD WEB SCRAPING
# ==========================================
def get_ocbc_fd_rates_text():
    url = "https://www.ocbc.com/personal-banking/deposits/fixed-deposit-account"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        rates_text = "🏦 *OCBC SGD Time Deposit Rates*\n\n"
        tables = soup.find_all('table')

        found_rates = False
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                # Extract individual columns instead of mashing them together immediately
                cols = row.find_all(['td', 'th'])
                if not cols:
                    continue

                col_texts = [c.get_text(separator=' ', strip=True) for c in cols]
                full_text = ' '.join(col_texts)

                if 'Singapore Dollar' in full_text and '%' in full_text:
                    found_rates = True

                    # Try to parse the columns neatly (Currency, Tenor, Method, Rate, Min Amt)
                    if len(col_texts) >= 5 and 'Singapore Dollar' in col_texts[0]:
                        tenor = col_texts[1]
                        method = col_texts[2]
                        rate = col_texts[3]
                        min_amt = col_texts[4]
                        rates_text += f"🔹 *{tenor} Months* ({method}): *{rate}* (Min {min_amt})\n"
                    else:
                        # Fallback for weirdly shaped tables
                        clean_text = re.sub(r'\s+', ' ', full_text).replace('Singapore Dollar', '').strip()
                        # Add the word 'Months' after the first number
                        clean_text = re.sub(r'^(\d+)', r'\1 Months -', clean_text)
                        rates_text += f"👉 {clean_text}\n"

        if not found_rates:
            rates_text += "⚠️ *Format Changed.* Could not locate exact rate table.\nFallback: 12-Month Online: 1.10% | 18-Month Online: 1.15%"

        return rates_text
    except Exception as e:
        return f"❌ OCBC Connection failed. Anti-bot firewall might be active.\nDetails: {e}"

# ==========================================
# 3. TELEGRAM COMMAND HANDLERS
# ==========================================
async def start_command(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🇸🇬 *Welcome to the SG Finance Super Bot!*\n\n"
        "I can help you with two things today:\n\n"
        "1️⃣ *Check OCBC Fixed Deposit Rates:*\n"
        "Just tap or type /ocbc\n\n"
        "2️⃣ *Refinance Mortgage (MAS SORA vs Fixed):*\n"
        "Send your loan details like this:\n"
        "`Loan: 800000\n"
        "Fixed: 2.85\n"
        "Spread: 0.65`"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def ocbc_command(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🌐 Connecting to OCBC servers... Please hold.")
    rates_msg = get_ocbc_fd_rates_text()
    await update.message.reply_text(rates_msg, parse_mode="Markdown")

async def handle_mortgage_calculation(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    await update.message.reply_text("🔄 Fetching live MAS SORA data and calculating... Please hold.")

    loan_amount, fixed_rate, current_spread = 800000.0, 2.85, 0.65

    try:
        for line in text.split('\n'):
            if 'loan:' in line.lower():
                loan_amount = float(line.lower().replace('loan:', '').replace(',', '').strip())
            if 'fixed:' in line.lower():
                fixed_rate = float(line.lower().replace('fixed:', '').replace('%', '').strip())
            if 'spread:' in line.lower():
                current_spread = float(line.lower().replace('spread:', '').replace('%', '').strip())
    except Exception as e:
        print(f"Parsing error: {e}")
        await update.message.reply_text("⚠️ Could not parse text perfectly. Using default configuration baseline.")

    sora_data = get_latest_sora_rates()
    effective_floating = round(sora_data['sora_3m'] + current_spread, 3)

    gemini_key = os.environ.get("GEMINI_API_KEY")
    client = genai.Client(api_key=gemini_key)

    system_prompt = f"""
    You are an expert Singapore Mortgage Advisory Agent.
    LIVE BENCHMARK CONTEXT:
    - SORA Date: {sora_data['date']}
    - 3M SORA: {sora_data['sora_3m']}%
    - Floating Rate (3M SORA + {current_spread}%): {effective_floating}%
    - Loan Amount: SGD {loan_amount:,.2f}

    ROLE ACTIONS:
    1. Compare the user's fixed rate vs floating rate options mathematically.
    2. Output a Markdown Table formatting all monetary values in SGD.
    3. Conclude with a definitive 2-year horizon risk recommendation.
    """
    user_query = f"Loan amount: SGD {loan_amount:,.2f}. Fixed rate offered: {fixed_rate}%. Floating alternative: 3M SORA + {current_spread}%. Which is better based on today's SORA?"

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=user_query,
            config=genai.types.GenerateContentConfig(system_instruction=system_prompt, temperature=0.1)
        )
        await update.message.reply_text(response.text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ AI Error: {e}")

# ==========================================
# 4. WEBHOOK ENTRYPOINT FOR RENDER
# ==========================================
if __name__ == "__main__":
    TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    PORT = int(os.environ.get("PORT", 8443))
    RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")

    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("ocbc", ocbc_command))  # New OCBC Command Route!
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_mortgage_calculation))

    print(f"Starting webhook on port {PORT} via endpoint {RENDER_URL}/{TOKEN}")
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=f"{RENDER_URL}/{TOKEN}"
    )