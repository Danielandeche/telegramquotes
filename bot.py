import telebot
import schedule
import time
from datetime import datetime
import threading

# Bot token and group ID
TOKEN = "8225529337:AAFYdTwJVTTLC1RvwiYrkzI9jcV-VpCiADM"
GROUP_ID = -1001829852593
bot = telebot.TeleBot(TOKEN)

# Store last message ID so we can delete it
last_message_id = None

# Trading quotes/strategies/advice
quotes = [
    "📈 Success in trading comes from discipline, not luck.",
    "💡 A good strategy beats emotions every time.",
    "⚡ Small consistent profits > Big occasional wins.",
    "📊 In binary trading, patience and timing are everything.",
    "💎 Manage your risk before chasing rewards.",
    "🔥 Don’t just trade… Trade with a strategy.",
    "🎯 Stick to your trading plan no matter what.",
    "🧠 The best traders are masters of psychology.",
]

# Poll questions
polls = [
    ("Which trading style do you prefer?", ["Scalping", "Day Trading", "Swing Trading", "Long-Term"]),
    ("Which is harder in trading?", ["Finding entries", "Risk management", "Controlling emotions"]),
    ("How do you decide stake size?", ["Fixed stake", "Martingale", "Percentage of balance"]),
    ("Which Deriv strategy works best for you?", ["Over/Under", "Rise/Fall", "Even/Odd", "Differ/Matches"]),
]

quote_index = 0
poll_index = 0

# Function to send quotes with button
def send_quote():
    global last_message_id, quote_index

    # Delete previous message
    if last_message_id:
        try:
            bot.delete_message(GROUP_ID, last_message_id)
        except Exception as e:
            print(f"Error deleting message: {e}")

    # Pick quote
    quote = quotes[quote_index % len(quotes)]
    quote_index += 1

    # Inline button
    markup = telebot.types.InlineKeyboardMarkup()
    btn = telebot.types.InlineKeyboardButton(
        "🚀 Visit Binarytool Today 🌍", url="https://app.binarytool.site/"
    )
    markup.add(btn)

    # Send styled message
    msg = bot.send_message(
        GROUP_ID,
        f"✨ *Trading Motivation & Strategy* ✨\n\n{quote}\n\nStay disciplined, stay profitable 💹",
        parse_mode="Markdown",
        reply_markup=markup,
    )
    last_message_id = msg.message_id

# Function to send polls
def send_poll():
    global poll_index
    question, options = polls[poll_index % len(polls)]
    poll_index += 1

    bot.send_poll(
        GROUP_ID,
        question,
        options,
        is_anonymous=False,
        type="regular",
        open_period=1800,  # 30 minutes
    )

# Schedule tasks (every 10 mins for quotes, every 30 mins for polls)
schedule.every(10).minutes.at(":00").do(send_quote)
schedule.every(30).minutes.at(":00").do(send_poll)

# Run schedule
def run_schedule():
    while True:
        schedule.run_pending()
        time.sleep(1)

# Start thread
threading.Thread(target=run_schedule).start()

print("🤖 Bot is running...")
bot.infinity_polling()
