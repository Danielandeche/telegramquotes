import time
import random
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime

# --- CONFIG ---
TOKEN = "8225529337:AAFYdTwJVTTLC1RvwiYrkzI9jcV-VpCiADM"
GROUP_ID = -1001829852593   # Binarytools group
bot = telebot.TeleBot(TOKEN)

# --- QUOTES & STRATEGIES ---
quotes = [
    "📈 *Discipline is the bridge between goals and trading success.*",
    "💡 *In Binary Trading, consistency beats intensity.*",
    "🚀 *Trade the trend, not your emotions.*",
    "📊 *A good trader controls risk before chasing profits.*",
    "🔥 *Losses are tuition fees for learning. Learn and move forward.*",
    "⚡ *Overtrading is the enemy. Patience is the weapon.*",
    "🎯 *Focus on strategies, not on luck.*",
    "💎 *Your edge in trading is discipline, not predictions.*",
    "🧠 *Emotions can ruin the best strategy. Stay calm, trade smart.*",
]

# --- POLL QUESTIONS ---
polls = [
    {
        "question": "📊 Which strategy do you prefer?",
        "options": ["Even/Odd", "Rise/Fall", "Over/Under", "Matches/Differs"]
    },
    {
        "question": "💡 How many trades do you take daily?",
        "options": ["1-5", "6-10", "11-20", "20+"]
    },
    {
        "question": "🔥 What's your biggest trading challenge?",
        "options": ["Discipline", "Emotions", "Strategy", "Risk Management"]
    },
    {
        "question": "🚀 Do you trade mostly on:",
        "options": ["Demo Account", "Real Account"]
    },
]

# --- Send Quote ---
def send_quote():
    quote = random.choice(quotes)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🌐 Visit Binarytool Today", url="https://app.binarytool.site/"))
    bot.send_message(GROUP_ID, f"{quote}", reply_markup=markup, parse_mode="Markdown")

# --- Send Poll ---
def send_poll():
    poll = random.choice(polls)
    bot.send_poll(
        GROUP_ID,
        poll["question"],
        poll["options"],
        is_anonymous=False,
        allows_multiple_answers=False
    )

# --- Scheduler ---
def run_scheduler():
    while True:
        now = datetime.now()
        minute = now.minute
        second = now.second

        # Every 10 minutes (00, 10, 20, 30, 40, 50)
        if minute % 10 == 0 and second == 0:
            send_quote()

        # Every 30 minutes (00, 30)
        if minute % 30 == 0 and second == 5:  # slight delay to not clash with quotes
            send_poll()

        time.sleep(1)

# --- Start Bot ---
if __name__ == "__main__":
    print("🚀 Bot is running...")
    run_scheduler()
