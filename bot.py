import time
import requests
import websocket
import json
import threading
from datetime import datetime, timedelta

# Telegram Config
TOKEN = "8256982239:AAFZLRbcmRVgO1SiWOBqU7Hf00z6VU6nB64"
GROUP_ID = -1002810133474
TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

# Deriv Config
DERIV_APP_ID = "1089"  # Demo app_id, replace with your own
SYMBOL = "R_100"       # Example market
TICKS_TO_ANALYZE = 1000

# Send Telegram Message
def send_message(text):
    payload = {"chat_id": GROUP_ID, "text": text, "parse_mode": "Markdown"}
    requests.post(TELEGRAM_API, data=payload)

# Deriv WebSocket Connection
def fetch_ticks():
    ws = websocket.create_connection(f"wss://ws.binaryws.com/websockets/v3?app_id={DERIV_APP_ID}")
    ws.send(json.dumps({"ticks_history": SYMBOL, "count": TICKS_TO_ANALYZE, "end": "latest", "style": "ticks"}))
    response = ws.recv()
    ws.close()
    return json.loads(response)

# Analyze best signal
def analyze_signal():
    data = fetch_ticks()
    prices = [float(tick["quote"]) for tick in data["history"]["prices"]]
    digits = [int(str(price)[-1]) for price in prices]

    # Probability calculation
    over2 = sum(1 for d in digits if d > 2) / len(digits) * 100
    under7 = sum(1 for d in digits if d < 7) / len(digits) * 100

    if over2 > under7:
        return "OVER 2", over2
    else:
        return "UNDER 7", under7

# Signal Scheduler
def signal_cycle():
    while True:
        signal, prob = analyze_signal()
        entry_time = datetime.utcnow() + timedelta(minutes=2)
        expiry_time = entry_time + timedelta(minutes=5)

        # Pre-notification
        send_message(f"⚠️ *Upcoming Signal Alert*\n\nPossible strong market condition detected.\nSignal: `{signal}`\nProbability: {prob:.2f}%\n\n📢 Entry in *2 minutes* at {entry_time.strftime('%H:%M:%S')} UTC")

        # Wait 2 minutes
        time.sleep(120)

        # Send actual signal
        send_message(f"✅ *NEW SIGNAL*\n\nTrade: `{signal}`\nEntry Time: {datetime.utcnow().strftime('%H:%M:%S')} UTC\nExpiry: {expiry_time.strftime('%H:%M:%S')} UTC\n\n⚠️ Signal valid for *5 minutes*!")

        # Wait 28 more minutes (total 30 min cycle)
        time.sleep(1680)

# Run bot in background
if __name__ == "__main__":
    send_message("🚀 Deriv Signal Bot Started...\nSignals will be sent every 30 minutes.")
    signal_cycle()
