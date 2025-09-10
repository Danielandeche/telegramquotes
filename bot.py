import time
import requests
import json
import websocket
import threading
from datetime import datetime, timedelta
import pytz

# Telegram bot credentials
TOKEN = "8225529337:AAFYdTwJVTTLC1RvwiYrkzI9jcV-VpCiADM"
GROUP_ID = -1002776818122
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

# Deriv API WebSocket endpoint
DERIV_API_URL = "wss://ws.binaryws.com/websockets/v3?app_id=1089"

# Markets to analyze
MARKETS = ["R_10", "R_25", "R_50", "R_75", "R_100"]

# Market symbol to name mapping
MARKET_NAMES = {
    "R_10": "Volatility 10 Index",
    "R_25": "Volatility 25 Index",
    "R_50": "Volatility 50 Index",
    "R_75": "Volatility 75 Index",
    "R_100": "Volatility 100 Index",
}

# Store last 5000 ticks for analysis
market_ticks = {market: [] for market in MARKETS}

# Track active message IDs
active_messages = []

# Nairobi timezone
NAIROBI_TZ = pytz.timezone('Africa/Nairobi')

# Signal tracking
last_signal_time = None
signal_cycle_active = False
current_market = None
current_digit = None
current_confidence = None


def get_nairobi_time():
    """Get current time in Nairobi timezone."""
    return datetime.now(NAIROBI_TZ)


def send_telegram_message(message: str, image_path="logo.png", keep=False):
    """Send a message with logo and Run button."""
    keyboard = {
        "inline_keyboard": [[
            {"text": "🚀 Run on DBTraders", "url": "https://www.dbtraders.com/"}
        ]]
    }

    with open(image_path, "rb") as img:
        resp = requests.post(
            f"{BASE_URL}/sendPhoto",
            data={
                "chat_id": GROUP_ID,
                "caption": message,
                "parse_mode": "HTML",
                "reply_markup": json.dumps(keyboard),
            },
            files={"photo": img}
        )

    if resp.ok:
        msg_id = resp.json()["result"]["message_id"]
        if not keep:  # only track if it should be auto-deleted
            active_messages.append(msg_id)
        return msg_id
    return None


def delete_messages():
    """Delete tracked messages."""
    global active_messages
    for msg_id in active_messages:
        requests.post(f"{BASE_URL}/deleteMessage", data={
            "chat_id": GROUP_ID,
            "message_id": msg_id
        })
    active_messages = []


def analyze_market(market: str, ticks: list):
    """
    Analyze market ticks:
    - Look for digits before Over3 (>3) or Under6 (<6).
    - Count which preceding digit occurs most often in last 5000 ticks.
    """
    if len(ticks) < 50:
        return None

    last_digits = [int(str(t)[-1]) for t in ticks]

    pre_digit_counts = {i: 0 for i in range(10)}

    for i in range(1, len(last_digits)):
        current = last_digits[i]
        prev = last_digits[i - 1]

        if current > 3 or current < 6:  # Over 3 or Under 6
            pre_digit_counts[prev] += 1

    best_pre_digit = max(pre_digit_counts, key=pre_digit_counts.get)
    best_count = pre_digit_counts[best_pre_digit]
    total = sum(pre_digit_counts.values()) or 1
    confidence = best_count / total

    return best_pre_digit, best_count, confidence


def send_pre_signal(market, digit, confidence):
    """Send pre-signal notification 2 minutes before main signal."""
    market_name = MARKET_NAMES.get(market, market)
    nairobi_time = get_nairobi_time()
    main_signal_time = (nairobi_time + timedelta(minutes=2)).strftime('%H:%M:%S')
    
    pre_msg = (
        f"🔔 <b>Pre-Signal Notification</b>\n\n"
        f"📊 Market: {market_name}\n"
        f"🎯 Predicted Digit: <b>{digit}</b>\n"
        f"📈 Confidence: <b>{confidence:.2%}</b>\n\n"
        f"⏰ Main Signal at: <b>{main_signal_time}</b>\n\n"
        f"⚡ Get ready!"
    )
    return send_telegram_message(pre_msg)


def send_main_signal(market, digit, confidence):
    """Send main signal."""
    market_name = MARKET_NAMES.get(market, market)
    nairobi_time = get_nairobi_time()
    expiry_time = (nairobi_time + timedelta(minutes=5)).strftime('%H:%M:%S')
    
    main_msg = (
        f"🚀 <b>DBTraders Premium Signal</b>\n\n"
        f"📊 Market: {market_name}\n"
        f"🎯 Strategy: Over 3 / Under 6\n"
        f"🔢 Entry Digit: <b>{digit}</b>\n"
        f"📈 Confidence: <b>{confidence:.2%}</b>\n\n"
        f"⏰ Expiry: <b>{expiry_time}</b>\n\n"
        f"🔥 Execute now!"
    )
    return send_telegram_message(main_msg)


def send_expiry_signal(market):
    """Send expiry signal 5 minutes after main signal."""
    market_name = MARKET_NAMES.get(market, market)
    nairobi_time = get_nairobi_time()
    next_signal_time = (nairobi_time + timedelta(minutes=5)).strftime('%H:%M:%S')
    
    expiry_msg = (
        f"✅ <b>Signal Expired</b>\n\n"
        f"📊 Market: {market_name}\n"
        f"🕒 Expired at: {nairobi_time.strftime('%H:%M:%S')}\n\n"
        f"🔔 Next Signal Expected: {next_signal_time}"
    )
    msg_id = send_telegram_message(expiry_msg, keep=True)
    
    # Clean up previous messages
    time.sleep(5)
    delete_messages()
    
    return msg_id


def fetch_and_analyze():
    """Pick the best market for analysis."""
    global current_market, current_digit, current_confidence
    
    best_market = None
    best_digit = None
    best_confidence = 0

    for market in MARKETS:
        if len(market_ticks[market]) > 100:
            result = analyze_market(market, market_ticks[market])
            if result:
                pre_digit, count, confidence = result
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_digit = pre_digit
                    best_market = market

    if best_market is None:
        return None, None, None
        
    current_market = best_market
    current_digit = best_digit
    current_confidence = best_confidence
    
    return best_market, best_digit, best_confidence


def schedule_signals():
    """Schedule signals based on Nairobi time."""
    global last_signal_time, signal_cycle_active, current_market, current_digit, current_confidence
    
    while True:
        nairobi_time = get_nairobi_time()
        current_minute = nairobi_time.minute
        current_second = nairobi_time.second
        
        # Check if it's time for a new signal cycle (every 10 minutes at :00, :10, :20, etc.)
        if current_minute % 10 == 0 and current_second == 0 and not signal_cycle_active:
            # Get the best market for this cycle
            market, digit, confidence = fetch_and_analyze()
            if market:
                signal_cycle_active = True
                last_signal_time = nairobi_time
                
                # Send pre-signal immediately (2 minutes before main signal)
                send_pre_signal(market, digit, confidence)
                
        # Check if it's time for main signal (2 minutes after pre-signal)
        elif signal_cycle_active and nairobi_time >= last_signal_time + timedelta(minutes=2):
            if current_market:
                send_main_signal(current_market, current_digit, current_confidence)
                
        # Check if it's time for expiry signal (5 minutes after main signal)
        elif signal_cycle_active and nairobi_time >= last_signal_time + timedelta(minutes=7):
            if current_market:
                send_expiry_signal(current_market)
                # Reset for next cycle
                signal_cycle_active = False
                current_market = None
                current_digit = None
                current_confidence = None
        
        time.sleep(1)  # Check every second


def on_message(ws, message):
    """Handle incoming tick data."""
    data = json.loads(message)

    if "tick" in data:
        symbol = data["tick"]["symbol"]
        quote = data["tick"]["quote"]

        market_ticks[symbol].append(quote)
        if len(market_ticks[symbol]) > 5000:
            market_ticks[symbol].pop(0)


def subscribe_to_ticks(ws):
    """Subscribe to tick streams for all markets."""
    for market in MARKETS:
        ws.send(json.dumps({"ticks": market}))


def run_websocket():
    """Run Deriv WebSocket client."""
    ws = websocket.WebSocketApp(
        DERIV_API_URL,
        on_message=on_message
    )
    ws.on_open = lambda w: subscribe_to_ticks(w)
    ws.run_forever()


if __name__ == "__main__":
    ws_thread = threading.Thread(target=run_websocket)
    ws_thread.daemon = True
    ws_thread.start()
    
    # Wait a bit for websocket to connect and start receiving data
    time.sleep(5)
    
    schedule_signals()