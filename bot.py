import time
import requests
import websocket
import json
from datetime import datetime, timedelta

# ========================
# Telegram Config
# ========================
TOKEN = "8256982239:AAFZLRbcmRVgO1SiWOBqU7Hf00z6VU6nB64"  # Replace with your bot token
GROUP_ID = -1002810133474  # Replace with your group/chat id
TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

# ========================
# Deriv Config
# ========================
DERIV_APP_ID = "1089"   # Replace with your real App ID
MARKETS = ["R_25", "R_50", "R_75", "R_100", "R_150", "R_200", "R_250"]
TICKS_TO_ANALYZE = 5000

# ========================
# Telegram Message Sender
# ========================
def send_message(text):
    payload = {
        "chat_id": GROUP_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    requests.post(TELEGRAM_API, data=payload)

# ========================
# Deriv WebSocket Connection
# ========================
def fetch_ticks(symbol):
    ws = websocket.create_connection(
        f"wss://ws.binaryws.com/websockets/v3?app_id={DERIV_APP_ID}"
    )
    ws.send(json.dumps({
        "ticks_history": symbol,
        "count": TICKS_TO_ANALYZE,
        "end": "latest",
        "style": "ticks"
    }))
    response = ws.recv()
    ws.close()
    return json.loads(response)

# ========================
# Analyze Signal for One Market
# ========================
def analyze_market(symbol):
    try:
        data = fetch_ticks(symbol)
        prices = [float(p) for p in data["history"]["prices"]]
        digits = [int(str(price)[-1]) for price in prices]

        # Transition tracking: after digit X, what digit comes next?
        transition_counts = {x: {d: 0 for d in range(10)} for x in range(10)}

        for i in range(len(digits) - 1):
            current_digit = digits[i]
            next_digit = digits[i + 1]
            transition_counts[current_digit][next_digit] += 1

        over3_probs, under7_probs = {}, {}

        for entry_digit in range(10):
            total_after = sum(transition_counts[entry_digit].values())
            if total_after == 0:
                continue

            over3_count = sum(v for d, v in transition_counts[entry_digit].items() if d > 3)
            under7_count = sum(v for d, v in transition_counts[entry_digit].items() if d < 7)

            over3_probs[entry_digit] = over3_count / total_after * 100
            under7_probs[entry_digit] = under7_count / total_after * 100

        if not over3_probs or not under7_probs:
            return None

        best_over3 = max(over3_probs, key=over3_probs.get)
        best_under7 = max(under7_probs, key=under7_probs.get)

        if over3_probs[best_over3] > under7_probs[best_under7]:
            return (symbol, "OVER 3", best_over3, over3_probs[best_over3])
        else:
            return (symbol, "UNDER 7", best_under7, under7_probs[best_under7])

    except Exception as e:
        print(f"Error analyzing {symbol}: {e}")
        return None

# ========================
# Pick Strongest Market Signal
# ========================
def analyze_all_markets():
    best_signal = None
    for symbol in MARKETS:
        result = analyze_market(symbol)
        if result:
            if not best_signal or result[3] > best_signal[3]:
                best_signal = result
    return best_signal

# ========================
# Signal Flow
# ========================
def send_reminder():
    best_signal = analyze_all_markets()
    if not best_signal:
        send_message("⚠️ No valid signal found this hour.")
        return

    symbol, signal, entry_digit, prob = best_signal
    send_message(
        f"⏰ *Signal Reminder*\n\n"
        f"Signal in 2 minutes!\n"
        f"Market: Volatility {symbol.split('_')[1]} Index\n"
        f"Trade Type: {signal}\n"
        f"Entry Point: Digit {entry_digit}\n"
        f"Probability: {prob:.2f}%\n\n"
        f"📌 Use *Over3Signal.xml*\n"
        f"[▶ Run on app.binarytool.site](https://app.binarytool.site)\n"
    )

def send_signal():
    best_signal = analyze_all_markets()
    if not best_signal:
        send_message("⚠️ No valid signal generated.")
        return

    symbol, signal, entry_digit, prob = best_signal
    expiry_time = (datetime.utcnow() + timedelta(minutes=5)).strftime('%H:%M:%S')
    send_message(
        f"✅ *NEW SIGNAL*\n\n"
        f"Market: Volatility {symbol.split('_')[1]} Index\n"
        f"Trade Type: {signal}\n"
        f"Entry Point: Digit {entry_digit}\n"
        f"Signal Expires: {expiry_time} UTC\n"
        f"Probability: {prob:.2f}%\n\n"
        f"[▶ Run on app.binarytool.site](https://app.binarytool.site)\n"
    )

# ========================
# Custom Scheduler (No `schedule`)
# ========================
def run_scheduler():
    while True:
        now = datetime.utcnow()
        minute = now.minute
        second = now.second

        # Reminder at HH:58:00
        if minute == 58 and second == 0:
            send_reminder()
            time.sleep(1)

        # Signal at HH:00:00
        if minute == 0 and second == 0:
            send_signal()
            time.sleep(1)

        time.sleep(0.5)  # check clock twice per second

# ========================
# Start
# ========================
if __name__ == "__main__":
    send_message("🤖 Bot Started! Monitoring all volatility markets for signals...")
    run_scheduler()
