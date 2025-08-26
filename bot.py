from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Poll
from telegram.ext import Application
import random
import datetime

# === Your details ===
BOT_TOKEN = "8225529337:AAFYdTwJVTTLC1RvwiYrkzI9jcV-VpCiADM"
GROUP_ID = -1001829852593  # group id

# Keep track of last sent message & poll
last_message_id = None
last_poll_id = None

# === Stylish Quotes ===
quotes = [
    "✨ *Trading Tip*: _Risk management is the holy grail of trading._ Never risk more than 2% of your balance per trade.",
    "💡 *Strategy Insight*: _Patience is power._ Wait for clear setups before pulling the trigger.",
    "🚀 *Motivation*: Every great trader was once a beginner. Stay consistent and disciplined.",
    "📈 *Advice*: A losing trade doesn’t define you. Learn, adapt, and improve for the next opportunity.",
    "🔥 *Binary Hack*: Always back-test your strategy on a demo before risking real money.",
    "🧠 *Wisdom*: Trading is 80% psychology and 20% strategy. _Master your emotions first._",
    "🎯 *Pro Tip*: Focus on one market at a time. Mastery beats mediocrity across many.",
    "⚡ *Quick Strategy*: In volatile markets, short-term contracts (1–5 ticks) can capture quick moves.",
    "💎 *Reminder*: Success in trading is not about being right, it’s about *making money when you’re right*.",
    "📊 *Binary Strategy*: Use Even/Odd or Over/Under contracts for quick probability-based trades."
]

# === Poll Options ===
poll_questions = [
    ("Which do you prefer?", ["Even/Odd", "Over/Under", "Rise/Fall", "Matches/Differs"]),
    ("What’s your trading style?", ["Scalping", "Day Trading", "Swing", "Long-term"]),
    ("How do you manage risk?", ["Stop Loss", "Martingale", "Fixed %", "No Risk Plan 😅"]),
    ("Which market do you trust most?", ["Crash/BOOM", "Volatility Index", "Synthetic R_100", "Forex"]),
]

# === Build Inline Button ===
def get_button():
    keyboard = [[InlineKeyboardButton("🚀 Visit Binarytool Today 🚀", url="https://app.binarytool.site/")]]
    return InlineKeyboardMarkup(keyboard)

# === Job to send a random stylish quote & poll ===
async def send_quote(context):
    global last_message_id, last_poll_id

    # Delete previous message if exists
    if last_message_id:
        try:
            await context.bot.delete_message(chat_id=GROUP_ID, message_id=last_message_id)
        except Exception as e:
            print(f"⚠️ Could not delete previous message: {e}")

    # Close previous poll if exists
    if last_poll_id:
        try:
            await context.bot.stop_poll(chat_id=GROUP_ID, message_id=last_poll_id)
        except Exception as e:
            print(f"⚠️ Could not close previous poll: {e}")

    # Send stylish quote
    quote = random.choice(quotes)
    msg = await context.bot.send_message(
        chat_id=GROUP_ID,
        text=f"💬 {quote}\n\n🔗 _Stay sharp, stay disciplined!_",
        reply_markup=get_button(),
        parse_mode="Markdown"
    )
    last_message_id = msg.message_id

    # Send poll after the quote
    poll_q, poll_opts = random.choice(poll_questions)
    poll = await context.bot.send_poll(
        chat_id=GROUP_ID,
        question=f"📊 {poll_q}",
        options=poll_opts,
        is_anonymous=True
    )
    last_poll_id = poll.message_id

# === Main ===
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Schedule job every 10 minutes
    app.job_queue.run_repeating(
        send_quote,
        interval=600,  # 10 minutes
        first=datetime.timedelta(seconds=0)
    )

    print("🤖 Bot is running... sending stylish quotes + polls every 10 minutes.")
    app.run_polling()

if __name__ == "__main__":
    main()
