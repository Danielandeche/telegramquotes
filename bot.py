import time
import requests
import json
import websocket
import threading
from datetime import datetime, timedelta
import statistics

# Telegram bot credentials
TOKEN = "8256982239:AAFZLRbcmRVgO1SiWOBqU7Hf00z6VU6nB64"
GROUP_ID = -1002810133474
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

# Store last 200 ticks for analysis
market_ticks = {market: [] for market in MARKETS}

# Track message IDs
active_messages = []
last_expired_id = None

# Track recovery state
recovery_mode = False


def send_telegram_message(message: str, image_path="logo.png", keep=False):
    """Send a message with logo and Run button."""
    keyboard = {
        "inline_keyboard": [[
            {"text": "🚀 Run on KashyTrader", "url": "https://www.kashytrader.site/"}
        ]]
    }

    try:
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
    except FileNotFoundError:
        # fallback if no logo.png
        resp = requests.post(
            f"{BASE_URL}/sendMessage",
            data={
                "chat_id": GROUP_ID,
                "text": message,
                "parse_mode": "HTML",
                "reply_markup": json.dumps(keyboard),
            }
        )

    if resp.ok:
        msg_id = resp.json()["result"]["message_id"]
        if not keep:
            active_messages.append(msg_id)
        return msg_id
    return None


def delete_messages():
    """Delete previous messages."""
    global active_messages
    for msg_id in active_messages:
        requests.post(f"{BASE_URL}/deleteMessage", data={
            "chat_id": GROUP_ID,
            "message_id": msg_id
        })
    active_messages = []


def delete_last_expired():
    """Delete last expired message before sending new cycle."""
    global last_expired_id
    if last_expired_id:
        requests.post(f"{BASE_URL}/deleteMessage", data={
            "chat_id": GROUP_ID,
            "message_id": last_expired_id
        })
        last_expired_id = None


def analyze_market(market: str, ticks: list):
    """
    Focus only on:
      - Under 8 primary trade
      - Recovery with Under 5 if first fails
    """
    if len(ticks) < 30:
        return None

    last_digits = [int(str(t)[-1]) for t in ticks]

    # probability checks
    under8_count = sum(d < 8 for d in last_digits)
    under5_count = sum(d < 5 for d in last_digits)

    # recent streak check (last 5 digits)
    last5 = last_digits[-5:]
    streak_under8 = sum(d < 8 for d in last5) / 5
    streak_under5 = sum(d < 5 for d in last5) / 5

    # volatility filter
    vol = statistics.pstdev(last_digits[-20:])

    # Calculate strengths
    strength = {
        "Under 8": (under8_count / len(last_digits) + streak_under8 * 0.4) / (1 + vol / 10),
        "Under 5": (under5_count / len(last_digits) + streak_under5 * 0.4) / (1 + vol / 10),
    }

    return strength


def fetch_and_analyze():
    """Pick only markets with Under 8 opportunity, else recovery with Under 5."""
    global last_expired_id, recovery_mode

    delete_last_expired()
    best_market, best_signal, best_confidence = None, None, 0

    for market in MARKETS:
        if len(market_ticks[market]) > 20:
            strength = analyze_market(market, market_ticks[market])
            if strength:
                if not recovery_mode:  # Primary Under 8 mode
                    signal = "Under 8"
                    confidence = strength["Under 8"]
                else:  # Recovery Under 5 mode
                    signal = "Under 5"
                    confidence = strength["Under 5"]

                if confidence > best_confidence:
                    best_confidence = confidence
                    best_signal = signal
                    best_market = market

    if best_market and best_signal:
        now = datetime.now()
        market_name = MARKET_NAMES.get(best_market, best_market)
        entry_digit = int(str(market_ticks[best_market][-1])[-1]) if market_ticks[best_market] else None

        # -------- MAIN SIGNAL --------
        main_msg = (
            f"⚡ <b>KashyTrader Premium Signal</b>\n\n"
            f"📊 Market: {market_name}\n"
            f"🎯 Signal: <b>{best_signal}</b>\n"
            f"🔢 Entry Point Digit: <b>{entry_digit}</b>\n"
            f"📈 Confidence: <b>{best_confidence:.2%}</b>\n"
            f"🔥 Mode: {'Primary Under 8' if not recovery_mode else 'Recovery Under 5'}"
        )
        send_telegram_message(main_msg)

        # Simulate expiry after 3 mins
        time.sleep(180)

        # -------- RESULT SIMULATION (replace with real win/loss if integrated with trading API) --------
        outcome = "win" if entry_digit < (8 if not recovery_mode else 5) else "loss"

        if outcome == "win":
            post_msg = (
                f"✅ <b>Trade Won</b>\n\n"
                f"📊 Market: {market_name}\n"
                f"🎯 Signal: {best_signal}\n"
                f"🔢 Last Digit: {entry_digit}\n"
                f"📌 Confidence: {best_confidence:.2%}\n\n"
                f"🎉 Cycle Complete!"
            )
            recovery_mode = False  # reset
        else:
            post_msg = (
                f"❌ <b>Trade Lost</b>\n\n"
                f"📊 Market: {market_name}\n"
                f"🎯 Signal: {best_signal}\n"
                f"🔢 Last Digit: {entry_digit}\n"
                f"📌 Confidence: {best_confidence:.2%}\n\n"
                f"⚠️ Entering Recovery Mode: Next trade will be <b>Under 5</b>"
            )
            recovery_mode = True  # enable recovery for next cycle

        last_expired_id = send_telegram_message(post_msg, keep=True)

        # Cleanup old messages
        time.sleep(30)
        delete_messages()


def on_message(ws, message):
    """Handle incoming tick data."""
    data = json.loads(message)

    if "tick" in data:
        symbol = data["tick"]["symbol"]
        quote = data["tick"]["quote"]

        market_ticks[symbol].append(quote)
        if len(market_ticks[symbol]) > 200:
            market_ticks[symbol].pop(0)


def subscribe_to_ticks(ws):
    for market in MARKETS:
        ws.send(json.dumps({"ticks": market}))


def run_websocket():
    ws = websocket.WebSocketApp(
        DERIV_API_URL,
        on_message=on_message
    )
    ws.on_open = lambda w: subscribe_to_ticks(w)
    ws.run_forever()


def schedule_signals():
    while True:
        fetch_and_analyze()
        time.sleep(60)  # check every minute


if __name__ == "__main__":
    ws_thread = threading.Thread(target=run_websocket)
    ws_thread.start()
    schedule_signals()
