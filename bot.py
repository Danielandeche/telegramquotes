import time
import requests
import json
import websocket
import threading
from datetime import datetime

# Telegram bot credentials
TOKEN = "8225529337:AAFYdTwJVTTLC1RvwiYrkzI9jcV-VpCiADM"
GROUP_ID = -1001829852593
TELEGRAM_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

# Deriv API WebSocket endpoint
DERIV_API_URL = "wss://ws.binaryws.com/websockets/v3?app_id=1089"

# Markets to analyze
MARKETS = ["R_10", "R_25", "R_50", "R_75", "R_100"]

# Store last 100 ticks for analysis
market_ticks = {market: [] for market in MARKETS}


def send_telegram_message(message: str):
    """Send a message to the Telegram group/channel."""
    payload = {
        "chat_id": GROUP_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    requests.post(TELEGRAM_URL, data=payload)


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
        "even": even_count / len(last_digits),
        "odd": odd_count / len(last_digits),
        "over3": over3_count / len(last_digits),
        "under6": under6_count / len(last_digits),
    }

    best_signal = max(strength, key=strength.get)
    confidence = strength[best_signal]

    return best_signal, confidence


def fetch_and_analyze():
    """Pick the best market and send a signal every 10 minutes."""

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
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = (
            f"📊 <b>Deriv Trading Signal</b>\n\n"
            f"⏰ Time: {now}\n"
            f"🛒 Market: <b>{best_market}</b>\n"
            f"🎯 Signal: <b>{best_signal.upper()}</b>\n"
            f"📈 Confidence: {best_confidence:.2%}\n\n"
            f"⚡ Trade wisely!"
        )
        send_telegram_message(message)


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
        time.sleep(20)  # 10 minutes


if __name__ == "__main__":
    # Start WebSocket thread
    ws_thread = threading.Thread(target=run_websocket)
    ws_thread.start()

    # Start scheduled signal sender
    schedule_signals()
