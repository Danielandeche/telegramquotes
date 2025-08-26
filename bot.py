import time
import random
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime

# --- CONFIG ---
TOKEN = "8225529337:AAFYdTwJVTTLC1RvwiYrkzI9jcV-VpCiADM"
GROUP_ID = -1001829852593   # Binarytools group
WHATSAPP_GROUP_URL = "https://chat.whatsapp.com/J0il04i45Jb9qdh8CroyGa"
bot = telebot.TeleBot(TOKEN)

# Track the last message IDs to delete them
last_message_ids = {
    "quote": None,
    "poll": None
}

# --- ENHANCED QUOTES & STRATEGIES ---
quotes = [
    "🔥 *TRADING EXCELLENCE* 🔥\n\n"
    "📈 *Discipline is the bridge between goals and extraordinary trading success.*\n"
    "✨ Stay focused, trade smart, and watch your account grow! 💰\n\n"
    "⚡ _BinaryTool helps you maintain discipline with precise trading tools_ ⚡",
    
    "🚀 *BINARY TRADING MASTERY* 🚀\n\n"
    "💡 *In Binary Trading, consistency always beats intensity.*\n"
    "⚡ Small, consistent gains lead to massive results over time! 🌟\n\n"
    "📊 _Track your consistency with BinaryTool's performance analytics_ 📊",
    
    "🎯 *EMOTIONAL CONTROL* 🎯\n\n"
    "🧠 *Trade the trend, never your emotions.*\n"
    "💎 Master your mind, and the markets will reward you! 📊\n\n"
    "🛡️ _BinaryTool's signals remove emotion from your trading decisions_ 🛡️",
    
    "🛡️ *RISK MANAGEMENT* 🛡️\n\n"
    "📊 *A legendary trader controls risk before chasing profits.*\n"
    "⚖️ Protect your capital, and profits will follow naturally! 🌈\n\n"
    "💰 _Use BinaryTool's risk management features to protect your capital_ 💰",
    
    "🌅 *TRADING MINDSET* 🌅\n\n"
    "🔥 *Losses are merely tuition fees for your trading education.*\n"
    "✨ Learn, adapt, and come back stronger than ever! 💪\n\n"
    "📚 _Learn from every trade with BinaryTool's detailed history_ 📚",
    
    "⚡ *PATIENCE POWER* ⚡\n\n"
    "⏳ *Overtrading is the enemy of consistent profits.*\n"
    "🎯 Wait for your perfect setup - quality over quantity always wins! 🏆\n\n"
    "🔍 _BinaryTool helps identify high-probability setups_ 🔍",
    
    "🧠 *STRATEGIC EDGE* 🧠\n\n"
    "🎯 *Focus on perfecting your strategy, not on hoping for luck.*\n"
    "📚 The more you practice, the luckier you become! 💫\n\n"
    "🎮 _Test strategies risk-free with BinaryTool's demo mode_ 🎮",
    
    "💎 *DISCIPLINE WINS* 💎\n\n"
    "✨ *Your true edge in trading is unwavering discipline, not predictions.*\n"
    "🔥 Stay consistent, and success will be inevitable! 📈\n\n"
    "⏰ _Set trading reminders with BinaryTool's notification system_ ⏰",
    
    "🌊 *EMOTIONAL MASTERY* 🌊\n\n"
    "🧘 *Emotions can dismantle the most brilliant strategy.*\n"
    "⚡ Stay calm, trade logically, and watch your profits soar! 🚀\n\n"
    "🤖 _Let BinaryTool's automated signals remove emotion from trading_ 🤖",
    
    "🏆 *WINNER'S MINDSET* 🏆\n\n"
    "🌟 *The market doesn't distribute money, it redistributes it from the impatient to the patient.*\n"
    "💎 Your patience will be rewarded beyond measure! 💰\n\n"
    "📈 _BinaryTool helps you wait for the best opportunities_ 📈",
    
    "💫 *COMMUNITY POWER* 💫\n\n"
    "👥 *Join our WhatsApp trading community for real-time insights and support!*\n"
    "🤝 Learn from experienced traders and share your journey! 📱\n\n"
    f"💬 _Join now: {WHATSAPP_GROUP_URL}_ 💬",
    
    "📱 *TRADING COMMUNITY* 📱\n\n"
    "🌐 *Connect with fellow traders in our active WhatsApp group!*\n"
    "💡 Get daily market analysis, tips, and collaborative learning! ✨\n\n"
    f"🚀 _Be part of our growing community: {WHATSAPP_GROUP_URL}_ 🚀"
]

# --- POLL QUESTIONS ---
polls = [
    {
        "question": "📊 *Which strategy brings you the most consistent results?* 📊",
        "options": ["Even/Odd", "Rise/Fall", "Over/Under", "Matches/Differs"]
    },
    {
        "question": "💡 *How many quality trades do you take daily?* 💡",
        "options": ["1-5 focused trades", "6-10 strategic trades", "11-20 active trades", "20+ high-frequency trades"]
    },
    {
        "question": "🔥 *What's your biggest challenge in trading?* 🔥",
        "options": ["Maintaining Discipline", "Controlling Emotions", "Perfecting Strategy", "Risk Management"]
    },
    {
        "question": "🚀 *Where do you primarily build your skills?* 🚀",
        "options": ["Demo Account Practice", "Real Account Execution", "Both Equally", "Learning from Mentors"]
    },
    {
        "question": "💎 *What time frame do you find most profitable?* 💎",
        "options": ["Short-term (1-5 min)", "Medium-term (5-15 min)", "Long-term (15+ min)", "Varies based on market"]
    },
    {
        "question": "📱 *Have you joined our WhatsApp trading community yet?* 📱",
        "options": ["Yes, already member!", "Joining right now!", "Will join soon", "Prefer Telegram only"]
    }
]

# --- Delete Previous Messages ---
def delete_previous_messages(message_type):
    """Delete the previous message of the specified type"""
    try:
        if last_message_ids[message_type]:
            bot.delete_message(GROUP_ID, last_message_ids[message_type])
            last_message_ids[message_type] = None
    except Exception as e:
        print(f"Could not delete previous {message_type} message: {e}")

# --- Send Quote ---
def send_quote():
    # Delete previous quote if exists
    delete_previous_messages("quote")
    
    quote = random.choice(quotes)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🌐 Visit BinaryTool Today", url="https://app.binarytool.site/"))
    markup.add(InlineKeyboardButton("📱 Join WhatsApp Group", url=WHATSAPP_GROUP_URL))
    
    # Send new quote and store its message ID
    sent_message = bot.send_message(GROUP_ID, f"{quote}", reply_markup=markup, parse_mode="Markdown")
    last_message_ids["quote"] = sent_message.message_id

# --- Send Poll ---
def send_poll():
    # Delete previous poll if exists
    delete_previous_messages("poll")
    
    poll = random.choice(polls)
    
    # Send new poll and store its message ID
    sent_poll = bot.send_poll(
        GROUP_ID,
        poll["question"],
        poll["options"],
        is_anonymous=False,
        allows_multiple_answers=False,
        parse_mode="Markdown"
    )
    last_message_ids["poll"] = sent_poll.message_id

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
    print("💎 Enhanced with motivational trading quotes")
    print("📱 Integrated WhatsApp group community")
    print("🗑️  Auto-deleting previous messages for clean chat")
    print("📈 Delivering value every 10 minutes")
    run_scheduler()
