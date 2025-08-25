from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application
import random, asyncio

# === Your details ===
BOT_TOKEN = "8225529337:AAFYdTwJVTTLC1RvwiYrkzI9jcV-VpCiADM"
GROUP_ID = -1001829852593  # group id

# === Deriv / Binary Trading Quotes & Strategies ===
quotes = [
    "📊 *Trading Tip*: Risk management is the holy grail of trading. Never risk more than 2% of your balance per trade.",
    "💡 *Strategy Insight*: In Binary trading, patience is power. Wait for clear setups before pulling the trigger.",
    "🚀 *Motivation*: Every great trader was once a beginner. Stay consistent and disciplined.",
    "📈 *Advice*: A losing trade doesn’t define you. Learn, adapt, and improve for the next opportunity.",
    "🔥 *Binary Hack*: Always back-test your strategy on a demo before risking real money.",
    "🧠 *Wisdom*: Trading is 80% psychology and 20% strategy. Master your emotions first.",
    "🎯 *Pro Tip*: Focus on one market at a time. Mastery beats mediocrity across many.",
    "⚡ *Quick Strategy*: In volatile markets, short-term contracts (1–5 ticks) can capture quick moves.",
    "💎 *Reminder*: Success in trading is not about being right, it’s about making money when you’re right.",
    "📊 *Binary Strategy*: Use Even/Odd or Over/Under contracts for quick probability-based trades."
]

# === Build Inline Button ===
def get_button():
    keyboard = [[InlineKeyboardButton("🚀 Visit Binarytool Today 🚀", url="https://app.binarytool.site/")]]
    return InlineKeyboardMarkup(keyboard)

# === Send Random Quote ===
async def send_quote(app: Application):
    while True:
        quote = random.choice(quotes)
        await app.bot.send_message(
            chat_id=GROUP_ID,
            text=quote,
            reply_markup=get_button(),
            parse_mode="Markdown"
        )
        await asyncio.sleep(1800)  # 30 minutes (1800 seconds)

# === Main ===
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Start auto-scheduler
    app.job_queue.run_once(lambda _: asyncio.create_task(send_quote(app)), when=0)

    print("🤖 Bot is running... sending quotes every 30 minutes.")
    app.run_polling()

if __name__ == "__main__":
    main()
