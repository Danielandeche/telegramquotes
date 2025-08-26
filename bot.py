import time
import random
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime

# --- CONFIG ---
TOKEN = "8225529337:AAFYdTwJVTTLC1RvwiYrkzI9jcV-VpCiADM"
GROUP_ID = -1001829852593   # Binarytools group
bot = telebot.TeleBot(TOKEN)

# --- ENHANCED QUOTES & STRATEGIES ---
quotes = [
    "🔥 *TRADING EXCELLENCE* 🔥\n\n"
    "📈 *Discipline is the bridge between goals and extraordinary trading success.*\n"
    "✨ Stay focused, trade smart, and watch your account grow! 💰",
    
    "🚀 *BINARY TRADING MASTERY* 🚀\n\n"
    "💡 *In Binary Trading, consistency always beats intensity.*\n"
    "⚡ Small, consistent gains lead to massive results over time! 🌟",
    
    "🎯 *EMOTIONAL CONTROL* 🎯\n\n"
    "🧠 *Trade the trend, never your emotions.*\n"
    "💎 Master your mind, and the markets will reward you! 📊",
    
    "🛡️ *RISK MANAGEMENT* 🛡️\n\n"
    "📊 *A legendary trader controls risk before chasing profits.*\n"
    "⚖️ Protect your capital, and profits will follow naturally! 🌈",
    
    "🌅 *TRADING MINDSET* 🌅\n\n"
    "🔥 *Losses are merely tuition fees for your trading education.*\n"
    "✨ Learn, adapt, and come back stronger than ever! 💪",
    
    "⚡ *PATIENCE POWER* ⚡\n\n"
    "⏳ *Overtrading is the enemy of consistent profits.*\n"
    "🎯 Wait for your perfect setup - quality over quantity always wins! 🏆",
    
    "🧠 *STRATEGIC EDGE* 🧠\n\n"
    "🎯 *Focus on perfecting your strategy, not on hoping for luck.*\n"
    "📚 The more you practice, the luckier you become! 💫",
    
    "💎 *DISCIPLINE WINS* 💎\n\n"
    "✨ *Your true edge in trading is unwavering discipline, not predictions.*\n"
    "🔥 Stay consistent, and success will be inevitable! 📈",
    
    "🌊 *EMOTIONAL MASTERY* 🌊\n\n"
    "🧘 *Emotions can dismantle the most brilliant strategy.*\n"
    "⚡ Stay calm, trade logically, and watch your profits soar! 🚀",
    
    "🏆 *WINNER'S MINDSET* 🏆\n\n"
    "🌟 *The market doesn't distribute money, it redistributes it from the impatient to the patient.*\n"
    "💎 Your patience will be rewarded beyond measure! 💰",
    
    "✨ *TRADING WISDOM* ✨\n\n"
    "📚 *The best traders are not experts at predicting markets, but experts at managing risk.*\n"
    "🛡️ Protect your capital like the precious resource it is! 🔒",
    
    "🚀 *SUCCESS FORMULA* 🚀\n\n"
    "💡 *Profitability comes from consistency, not from home runs.*\n"
    "📈 Small gains, compounded daily, create extraordinary wealth! 💰",
    
    "🔥 *PSYCHOLOGICAL EDGE* 🔥\n\n"
    "🧠 *Your mindset is your most valuable trading asset.*\n"
    "⚡ Cultivate patience, discipline, and emotional control for unstoppable success! 🌟",
    
    "🎯 *STRATEGIC EXECUTION* 🎯\n\n"
    "📊 *Plan your trade, then trade your plan - without deviation.*\n"
    "💎 Discipline turns strategy into reality! 🏆",
    
    "🌈 *PROFIT JOURNEY* 🌈\n\n"
    "✨ *Trading success is a marathon, not a sprint.*\n"
    "⏳ Celebrate small victories and learn from every experience! 📚",
    
    "⚡ *MARKET MASTERY* ⚡\n\n"
    "🌊 *Ride the waves of market trends, don't fight against the current.*\n"
    "🚀 Align with momentum, and profits will flow effortlessly! 💰",
    
    "💫 *CONSISTENCY KEY* 💫\n\n"
    "🔑 *The secret to wealth is consistency, not complexity.*\n"
    "🎯 Simple strategies executed flawlessly beat complex ones executed poorly! 🏆",
    
    "🦅 *TRADER'S VISION* 🦅\n\n"
    "👁️ *See opportunities where others see obstacles.*\n"
    "💡 Market volatility is not risk - it's opportunity in disguise! ✨",
    
    "🏛️ *FOUNDATIONS OF SUCCESS* 🏛️\n\n"
    "📚 *Master the fundamentals before chasing advanced strategies.*\n"
    "⚡ A strong foundation builds an unshakable trading career! 🌟",
    
    "🌌 *FINANCIAL FREEDOM* 🌌\n\n"
    "✨ *Trading isn't just about making money - it's about designing your ideal life.*\n"
    "🚀 Every disciplined trade brings you closer to your dreams! 💫"
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
    }
]

# --- Send Quote ---
def send_quote():
    quote = random.choice(quotes)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🌐 Visit BinaryTool Today", url="https://app.binarytool.site/"))
    markup.add(InlineKeyboardButton("💎 Join VIP Signals", callback_data="vip_signals"))
    bot.send_message(GROUP_ID, f"{quote}", reply_markup=markup, parse_mode="Markdown")

# --- Send Poll ---
def send_poll():
    poll = random.choice(polls)
    bot.send_poll(
        GROUP_ID,
        poll["question"],
        poll["options"],
        is_anonymous=False,
        allows_multiple_answers=False,
        parse_mode="Markdown"
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
    print("💎 Enhanced with motivational trading quotes")
    print("📈 Delivering value every 10 minutes")
    run_scheduler()
