#!/usr/bin/env python3
"""
deriv_signal_bot_fixed_v2.py

- System time drives schedule (every 10 min slot).
- Presignal = slot - 2 minutes
- Main = slot
- Expiry = slot + 5 minutes
- Ticks are used only for analysis (confidence, digit counts).
- Sends photo + inline button when possible; falls back to text message.
- Deletes pre+main at expiry (keeps expiry).
"""

import time
import json
import logging
import threading
from collections import deque
from datetime import datetime, timedelta
import pytz
import requests
import websocket
from typing import Optional

# ---------------- CONFIG ----------------
TOKEN = "8225529337:AAFYdTwJVTTLC1RvwiYrkzI9jcV-VpCiADM"
CHAT_ID = -1002776818122
BASE_TELEGRAM = f"https://api.telegram.org/bot{TOKEN}"

DERIV_WS = "wss://ws.binaryws.com/websockets/v3?app_id=1089"

MARKETS = ["R_10", "R_25", "R_50", "R_75", "R_100"]
MARKET_NAMES = {
    "R_10": "Volatility 10 Index",
    "R_25": "Volatility 25 Index",
    "R_50": "Volatility 50 Index",
    "R_75": "Volatility 75 Index",
    "R_100": "Volatility 100 Index",
}

MAX_TICKS = 5000
MIN_TICKS_FOR_ANALYSIS = 100
NAIROBI_TZ = pytz.timezone("Africa/Nairobi")

LOGO_PATH = "logo.png"
RUN_BUTTON_URL = "https://www.dbtraders.com/"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ---------------- State ----------------
market_ticks = {m: deque(maxlen=MAX_TICKS) for m in MARKETS}
state_lock = threading.Lock()
tracked_message_ids = []

# ---------------- Telegram helpers ----------------
def _inline_keyboard_json():
    return json.dumps({
        "inline_keyboard": [[{"text": "🚀 Run on DBTraders", "url": RUN_BUTTON_URL}]]
    })

def send_photo_with_button(caption: str, keep: bool = False) -> Optional[int]:
    try:
        with open(LOGO_PATH, "rb") as img:
            resp = requests.post(
                f"{BASE_TELEGRAM}/sendPhoto",
                data={
                    "chat_id": CHAT_ID,
                    "caption": caption,
                    "parse_mode": "HTML",
                    "reply_markup": _inline_keyboard_json(),
                },
                files={"photo": img},
                timeout=12,
            )
        if resp.ok:
            mid = resp.json().get("result", {}).get("message_id")
            if mid and not keep:
                tracked_message_ids.append(mid)
            return mid
    except FileNotFoundError:
        logging.warning("Logo not found, fallback to text.")
    except Exception:
        logging.exception("Error sending photo.")
    return None

def send_message_with_button(text: str, keep: bool = False) -> Optional[int]:
    try:
        resp = requests.post(
            f"{BASE_TELEGRAM}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": [[{"text": "🚀 Run on DBTraders", "url": RUN_BUTTON_URL}]]},
            },
            timeout=12,
        )
        if resp.ok:
            mid = resp.json().get("result", {}).get("message_id")
            if mid and not keep:
                tracked_message_ids.append(mid)
            return mid
    except Exception:
        logging.exception("Error sending message.")
    return None

def send_telegram(caption: str, keep: bool = False) -> Optional[int]:
    mid = send_photo_with_button(caption, keep)
    if mid:
        return mid
    return send_message_with_button(caption, keep)

def delete_tracked_messages():
    global tracked_message_ids
    for mid in list(tracked_message_ids):
        try:
            requests.post(
                f"{BASE_TELEGRAM}/deleteMessage",
                json={"chat_id": CHAT_ID, "message_id": mid},
                timeout=10,
            )
        except Exception:
            logging.exception(f"Error deleting message {mid}")
    tracked_message_ids = []

# ---------------- Tick analysis ----------------
def get_last_digit_from_quote(q):
    s = str(q)
    for ch in reversed(s):
        if ch.isdigit():
            return int(ch)
    return None

def analyze_ticks_for_market(ticks_deque):
    digits = [get_last_digit_from_quote(q) for q in ticks_deque if get_last_digit_from_quote(q) is not None]
    if len(digits) < 2:
        return {"over3": None, "under6": None}

    over_counts = [0] * 10
    under_counts = [0] * 10
    tot_over = tot_under = 0

    for i in range(1, len(digits)):
        prev, cur = digits[i - 1], digits[i]
        if cur > 3:
            over_counts[prev] += 1
            tot_over += 1
        if cur < 6:
            under_counts[prev] += 1
            tot_under += 1

    def best(counts, total):
        if total == 0:
            return None
        b = max(range(10), key=lambda x: counts[x])
        return {"best_digit": b, "count": counts[b], "total": total, "confidence": counts[b] / total}

    return {"over3": best(over_counts, tot_over), "under6": best(under_counts, tot_under)}

def pick_best_market_strategy():
    best = None
    with state_lock:
        snapshot = {m: list(market_ticks[m]) for m in MARKETS}

    for market, ticks in snapshot.items():
        if len(ticks) < MIN_TICKS_FOR_ANALYSIS:
            continue
        res = analyze_ticks_for_market(ticks)
        for key, strategy_name in (("over3", "Over 3"), ("under6", "Under 6")):
            info = res.get(key)
            if not info:
                continue
            if best is None or info["confidence"] > best["confidence"]:
                best = {
                    "market": market,
                    "market_name": MARKET_NAMES.get(market, market),
                    "strategy": strategy_name,
                    "best_digit": info["best_digit"],
                    "count": info["count"],
                    "total": info["total"],
                    "confidence": info["confidence"],
                }
    return best

# ---------------- WebSocket ----------------
def on_ws_message(ws, message):
    try:
        data = json.loads(message)
    except Exception:
        return
    if "tick" in data:
        tick = data["tick"]
        symbol, quote = tick.get("symbol"), tick.get("quote")
        if symbol in market_ticks and quote is not None:
            with state_lock:
                market_ticks[symbol].append(quote)

def on_ws_open(ws):
    for m in MARKETS:
        ws.send(json.dumps({"ticks": m}))

def run_websocket_forever():
    while True:
        try:
            ws = websocket.WebSocketApp(
                DERIV_WS,
                on_message=on_ws_message,
                on_open=on_ws_open,
            )
            ws.run_forever(ping_interval=30, ping_timeout=10)
        except Exception:
            time.sleep(3)

# ---------------- Scheduler ----------------
def scheduler_loop():
    current_slot_epoch = None
    candidate = None
    presignal_sent = main_sent = expiry_sent = False

    while True:
        now_na = datetime.now(NAIROBI_TZ)
        bucket_min = (now_na.minute // 10) * 10
        slot_na = now_na.replace(minute=bucket_min, second=0, microsecond=0)
        if now_na >= slot_na:
            slot_na += timedelta(minutes=10)

        slot_epoch = int(slot_na.astimezone(pytz.UTC).timestamp())
        presignal_epoch = slot_epoch - 120
        expiry_epoch = slot_epoch + 300

        # Reset flags for new slot
        if current_slot_epoch != slot_epoch:
            logging.info(f"New slot: {slot_na}")
            current_slot_epoch = slot_epoch
            presignal_sent = main_sent = expiry_sent = False
            candidate = None

        now_epoch = int(time.time())

        # Presignal
        if not presignal_sent and presignal_epoch <= now_epoch < slot_epoch:
            candidate = pick_best_market_strategy()
            if candidate:
                pres_text = (
                    f"📢 <b>Upcoming Signal Reminder</b>\n\n"
                    f"⏰ Entry in 2 minutes\n"
                    f"📊 Market: <b>{candidate['market_name']}</b>\n"
                    f"🎯 Strategy: <b>{candidate['strategy']}</b>\n"
                    f"🔢 Digit: <b>{candidate['best_digit']}</b>\n"
                    f"📈 Confidence: {candidate['confidence']:.2%}\n"
                    f"🕒 Entry Time: {slot_na.strftime('%Y-%m-%d %H:%M:%S')}"
                )
            else:
                pres_text = "📢 <b>Upcoming Signal Reminder</b>\n⚠️ Not enough data."
            send_telegram(pres_text)
            presignal_sent = True

        # Main
        if not main_sent and slot_epoch <= now_epoch < slot_epoch + 10:
            if candidate is None:
                candidate = pick_best_market_strategy()
            if candidate:
                expiry_na = datetime.fromtimestamp(expiry_epoch, tz=pytz.UTC).astimezone(NAIROBI_TZ)
                main_text = (
                    f"⚡ <b>Main Signal</b>\n\n"
                    f"📊 Market: <b>{candidate['market_name']}</b>\n"
                    f"🎯 Strategy: <b>{candidate['strategy']}</b>\n"
                    f"🔢 Digit: <b>{candidate['best_digit']}</b>\n"
                    f"📈 Confidence: {candidate['confidence']:.2%}\n"
                    f"🕒 Time: {slot_na.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"⏳ Expires: {expiry_na.strftime('%Y-%m-%d %H:%M:%S')}"
                )
            else:
                main_text = "⚡ <b>Main Signal</b>\n⚠️ Not enough data."
            send_telegram(main_text)
            main_sent = True

        # Expiry
        if not expiry_sent and expiry_epoch <= now_epoch < expiry_epoch + 10:
            expiry_na = datetime.fromtimestamp(expiry_epoch, tz=pytz.UTC).astimezone(NAIROBI_TZ)
            next_slot_na = slot_na + timedelta(minutes=10)
            expiry_text = (
                f"✅ <b>Signal Expired</b>\n\n"
                f"🕒 Expired at: {expiry_na.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"🔔 Next slot: {next_slot_na.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            send_telegram(expiry_text, keep=True)
            delete_tracked_messages()
            expiry_sent = True

        time.sleep(1)

# ---------------- Main ----------------
if __name__ == "__main__":
    logging.info("Starting Deriv signal bot (system-time scheduler).")
    threading.Thread(target=run_websocket_forever, daemon=True).start()
    try:
        scheduler_loop()
    except KeyboardInterrupt:
        delete_tracked_messages()
