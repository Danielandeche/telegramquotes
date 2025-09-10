import time
import requests
import json
import websocket
import threading
from datetime import datetime, timedelta

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


def fetch_and_analyze():
    """Pick the best market and send full signal cycle."""
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
        return

    now = datetime.now()
    entry_time = now + timedelta(minutes=1)
    expiry_time = now + timedelta(minutes=4)
    next_signal_time = now + timedelta(minutes=10)

    market_name = MARKET_NAMES.get(best_market, best_market)

    # -------- PRE-NOTIFICATION --------
    pre_msg = (
        f"📢 <b>Upcoming Signal Alert</b>\n\n"
        f"⏰ Entry in <b>1 minute</b>\n"
        f"📊 Market: {market_name}\n"
        f"🕒 Entry Time: {entry_time.strftime('%H:%M:%S')}\n\n"
        f"⚡ Get ready!"
    )
    send_telegram_message(pre_msg)
    time.sleep(6)

    # -------- MAIN SIGNAL --------
    main_msg = (
        f"⚡ <b>DBTraders Premium Signal</b>\n\n"
        f"📊 Market: {market_name}\n"
        f"🎯 Strategy: Over 3 / Under 6\n"
        f"🔢 Entry Digit: <b>{best_digit}</b>\n"
        f"📈 Confidence: <b>{best_confidence:.2%}</b>\n\n"
        f"🔥 Execute now!"
    )
    send_telegram_message(main_msg)
    time.sleep(9)

    # -------- POST-NOTIFICATION --------
    post_msg = (
        f"✅ <b>Signal Expired</b>\n\n"
        f"📊 Market: {market_name}\n"
        f"🕒 Expired at: {expiry_time.strftime('%H:%M:%S')}\n\n"
        f"🔔 Next Signal Expected: {next_signal_time.strftime('%H:%M:%S')}"
    )
    send_telegram_message(post_msg, keep=True)

    # -------- CLEANUP --------
    time.sleep(10)
    delete_messages()


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


def schedule_signals():
    """Send signals every 10 minutes."""
    while True:
        fetch_and_analyze()
        time.sleep(60)  # 10 minutes


if __name__ == "__main__":
    ws_thread = threading.Thread(target=run_websocket)
    ws_thread.start()
    schedule_signals()
