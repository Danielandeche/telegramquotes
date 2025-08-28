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

# Store last 100 ticks for analysis
market_ticks = {market: [] for market in MARKETS}

# Track last message ID for deleting
last_message_id = None


def send_telegram_message(message: str, image_path="logo.png"):
    """Send a message with logo and Run button, delete old one if exists."""
    global last_message_id

    # Delete previous message
    if last_message_id:
        requests.post(f"{BASE_URL}/deleteMessage", data={
            "chat_id": GROUP_ID,
            "message_id": last_message_id
        })

    # Inline button
    keyboard = {
        "inline_keyboard": [[
            {"text": "🚀 Run on KashyTrader", "url": "https://www.kashytrader.site/"}
        ]]
    }

    # Send photo with caption
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
        last_message_id = resp.json()["result"]["message_id"]


def analyze_market(market: str, ticks: list):
    """Analyze market ticks for even/odd, over 3, under 6."""
    if len(ticks) < 20:
        return None

    last_digits = [int(str(t)[-1]) for t in ticks]

    even_count = sum(1 for d in last_digits if d % 2 == 0)
    odd_count = len(last_digits) - even_count
    over3_count = sum(1 for d in last_digits if d > 3)
    under6_count = sum(1 for d in last_digits if d < 6)

    strength = {
        "Even": even_count / len(last_digits),
        "Odd": odd_count / len(last_digits),
        "Over 3": over3_count / len(last_digits),
        "Under 6": under6_count / len(last_digits),
    }

    best_signal = max(strength, key=strength.get)
    confidence = strength[best_signal]

    return best_signal, confidence


def fetch_and_analyze():
    """Pick the best market and send full signal cycle."""
    best_market = None
    best_signal = None
    best_confidence = 0

    for market in MARKETS:
        if len(market_ticks[market]) > 10:
            result = analyze_market(market, market_ticks[market])
            if result:
                signal, confidence = result
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_signal = signal
                    best_market = market

    if best_market:
        now = datetime.now()
        entry_time = now + timedelta(minutes=1)
        expiry_time = now + timedelta(minutes=4)  # 1m pre + 3m duration
        next_signal_time = now + timedelta(minutes=10)

        market_name = MARKET_NAMES.get(best_market, best_market)

        # Pre-notification
        pre_msg = (
            f"📢 <b>Upcoming Signal Alert</b>\n\n"
            f"⏰ Entry in <b>1 minute</b>\n"
            f"📊 Market: {market_name}\n"
            f"🕒 Entry Time: {entry_time.strftime('%H:%M:%S')}\n\n"
            f"⚡ Get ready!"
        )
        send_telegram_message(pre_msg)
        time.sleep(20)

        # Main signal
        main_msg = (
            f"⚡ <b>KashyTrader Premium Signal</b>\n\n"
            f"⏰ Time: {entry_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"📊 Market: {market_name}\n"
            f"🎯 Signal: <b>{best_signal}</b>\n"
            f"📈 Confidence: <b>{best_confidence:.2%}</b>\n\n"
            f"🔥 Execute now!"
        )
        send_telegram_message(main_msg)
        time.sleep(80)

        # Post-notification
        post_msg = (
            f"✅ <b>Signal Expired</b>\n\n"
            f"📊 Market: {market_name}\n"
            f"🕒 Expired at: {expiry_time.strftime('%H:%M:%S')}\n\n"
            f"🔔 Next Signal Expected: {next_signal_time.strftime('%H:%M:%S')}"
        )
        send_telegram_message(post_msg)


def on_message(ws, message):
    """Handle incoming tick data."""
    data = json.loads(message)

    if "tick" in data:
        symbol = data["tick"]["symbol"]
        quote = data["tick"]["quote"]

        market_ticks[symbol].append(quote)
        if len(market_ticks[symbol]) > 100:
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
    # Start WebSocket thread
    ws_thread = threading.Thread(target=run_websocket)
    ws_thread.start()

    # Start scheduled signal sender
    schedule_signals()
