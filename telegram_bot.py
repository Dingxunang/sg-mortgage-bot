import os
import requests
import asyncio
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
# 2. TELEGRAM COMMAND HANDLERS
# ==========================================
async def start_command(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    # UPDATED: Changed instructions to point to /bank
    welcome_text = (
        "🇸🇬 *Welcome to the SG Finance Super Bot!*\n\n"
        "I can help you with two things today:\n\n"
        "1️⃣ *Compare All Bank FD Rates:*\n"
        "Just tap or type /bank to scan DBS, UOB, OCBC, CIMB & more.\n\n"
        "2️⃣ *Refinance Mortgage (MAS SORA vs Fixed):*\n"
        "Send your loan details like this:\n"
        "`Loan: 800000\n"
        "Fixed: 2.85\n"
        "Spread: 0.65`"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

# UPDATED: Renamed from fd_command to bank_command
async def bank_command(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🌐 Initiating live web scan of all major SG bank Fixed Deposit rates... Please hold.")

    gemini_key = os.environ.get("GEMINI_API_KEY")
    client = genai.Client(api_key=gemini_key)

    system_prompt = """
    You are an elite Singapore Wealth Management Advisor. 
    
    ROLE ACTIONS:
    1. Use Google Search to find the LATEST promotional Fixed Deposit (FD) interest rates across major Singapore banks (DBS, UOB, OCBC, CIMB, RHB, Hong Leong, etc.).
    2. Create a concise Markdown Table comparing the best rates, their required tenure (e.g., 3, 6, 12 months), and minimum deposit amounts. Keep the table very compact.
    3. Briefly compare the best FD rate against current alternatives like SG 6-month T-Bills or SSB (Singapore Savings Bonds).
    4. Conclude with a definitive 1-sentence verdict on where to park cash right now.
    
    FORMATTING CONSTRAINTS (CRITICAL):
    - Telegram has a strict 4096 character limit. Your ENTIRE response MUST be under 3000 characters.
    - Use clean, standard Markdown. Do not use overly complex formatting that might break the parser.
    """

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents="Search the internet for today's SG bank fixed deposit promotional rates and compare them.",
                config=genai.types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.2,
                    tools=[{"google_search": {}}]
                )
            )

            final_message = f"🏦 *SG Banks Fixed Deposit Comparison*\n\n{response.text}"

            if len(final_message) > 4000:
                chunks = [final_message[i:i+4000] for i in range(0, len(final_message), 4000)]
                for chunk in chunks:
                    await update.message.reply_text(chunk)
            else:
                try:
                    await update.message.reply_text(final_message, parse_mode="Markdown")
                except Exception as parse_error:
                    print(f"Markdown error bypassed. Sending plain text. Detail: {parse_error}")
                    await update.message.reply_text(final_message)
            break

        except Exception as e:
            error_msg = str(e)
            if "503" in error_msg and attempt < max_retries - 1:
                await update.message.reply_text(f"⏳ Google AI is currently experiencing high demand. Retrying in 3 seconds... (Attempt {attempt + 2}/{max_retries})")
                await asyncio.sleep(3)
            else:
                await update.message.reply_text(f"⚠️ Could not complete AI market scan after {max_retries} attempts. Details: {error_msg}")
                break

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
    
    FORMATTING:
    Keep the total response concise, ensuring it easily fits within a Telegram message.
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
# 3. WEBHOOK ENTRYPOINT FOR RENDER
# ==========================================
if __name__ == "__main__":
    TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    PORT = int(os.environ.get("PORT", 8443))
    RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")

    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    # UPDATED: Registers "bank" as the active trigger command
    application.add_handler(CommandHandler("bank", bank_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_mortgage_calculation))

    print(f"Starting webhook on port {PORT} via endpoint {RENDER_URL}/{TOKEN}")
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=f"{RENDER_URL}/{TOKEN}"
    )