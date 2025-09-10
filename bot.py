#!/usr/bin/env python3
"""
deriv_signal_bot_fixed.py

- Uses Deriv tick epoch (server time) to schedule signals.
- Presignal = slot - 2 minutes, Main = slot, Expiry = slot + 5 minutes.
- Analysis uses last up to 5000 ticks per market; picks best preceding digit for Over 3 / Under 6.
- Sends photo + inline button when possible; falls back to text message + inline button.
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

# Markets to analyze
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

# Local logo path used for sendPhoto. If missing, bot will fallback to text-only with button.
LOGO_PATH = "logo.png"
RUN_BUTTON_URL = "https://www.dbtraders.com/"

# ----------------------------------------

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Shared state
market_ticks = {m: deque(maxlen=MAX_TICKS) for m in MARKETS}
latest_epoch = None  # last tick epoch (UTC seconds)
state_lock = threading.Lock()

# Track message ids (pre + main) so we can delete them on expiry
tracked_message_ids = []


# ---------------- Telegram helpers ----------------
def _inline_keyboard_json():
    kb = {"inline_keyboard": [[{"text": "🚀 Run on DBTraders", "url": RUN_BUTTON_URL}]]}
    return json.dumps(kb)


def send_photo_with_button(caption: str, keep: bool = False) -> Optional[int]:
    """Try sendPhoto with inline keyboard. Return message_id or None."""
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
            logging.info(f"sendPhoto OK message_id={mid}")
            if mid and not keep:
                tracked_message_ids.append(mid)
            return mid
        else:
            logging.warning(f"sendPhoto failed: {resp.status_code} {resp.text}")
    except FileNotFoundError:
        logging.warning("Logo file not found for sendPhoto (fallback to sendMessage).")
    except Exception:
        logging.exception("Exception during sendPhoto (fallback to sendMessage).")
    return None


def send_message_with_button(text: str, keep: bool = False) -> Optional[int]:
    """Send text message with inline keyboard (fallback)."""
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
            logging.info(f"sendMessage OK message_id={mid}")
            if mid and not keep:
                tracked_message_ids.append(mid)
            return mid
        else:
            logging.error(f"sendMessage failed: {resp.status_code} {resp.text}")
    except Exception:
        logging.exception("Exception sending message")
    return None


def send_telegram(caption: str, keep: bool = False) -> Optional[int]:
    """
    Try sendPhoto+button; on any failure fallback to sendMessage+button.
    Returns message_id or None.
    """
    mid = send_photo_with_button(caption, keep=keep)
    if mid is not None:
        return mid
    return send_message_with_button(caption, keep=keep)


def delete_tracked_messages():
    """Delete tracked pre/main messages (best-effort)."""
    global tracked_message_ids
    for mid in list(tracked_message_ids):
        try:
            resp = requests.post(
                f"{BASE_TELEGRAM}/deleteMessage",
                json={"chat_id": CHAT_ID, "message_id": mid},
                timeout=10,
            )
            if resp.ok:
                logging.info(f"Deleted message {mid}")
            else:
                logging.warning(f"Failed to delete {mid}: {resp.status_code} {resp.text}")
        except Exception:
            logging.exception(f"Exception deleting message {mid}")
    tracked_message_ids = []


# ---------------- Utilities & Analysis ----------------
def get_last_digit_from_quote(q):
    s = str(q)
    for ch in reversed(s):
        if ch.isdigit():
            return int(ch)
    return None


def analyze_ticks_for_market(ticks_deque):
    digits = []
    for q in ticks_deque:
        d = get_last_digit_from_quote(q)
        if d is not None:
            digits.append(d)
    if len(digits) < 2:
        return {"over3": None, "under6": None}

    over_counts = [0] * 10
    under_counts = [0] * 10
    tot_over = 0
    tot_under = 0

    for i in range(1, len(digits)):
        prev = digits[i - 1]
        cur = digits[i]
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
            conf = info["confidence"]
            if best is None or conf > best["confidence"] or (conf == best["confidence"] and info["count"] > best["count"]):
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
    global latest_epoch
    try:
        data = json.loads(message)
    except Exception:
        return
    if "tick" in data:
        tick = data["tick"]
        symbol = tick.get("symbol")
        quote = tick.get("quote")
        epoch = tick.get("epoch")
        if symbol in market_ticks and quote is not None and epoch is not None:
            with state_lock:
                market_ticks[symbol].append(quote)
                latest_epoch = epoch


def on_ws_open(ws):
    logging.info("WebSocket opened — subscribing to ticks")
    for m in MARKETS:
        try:
            ws.send(json.dumps({"ticks": m}))
        except Exception:
            logging.exception(f"Failed to subscribe to {m}")


def on_ws_error(ws, err):
    logging.error(f"WebSocket error: {err}")


def on_ws_close(ws, code, reason):
    logging.warning(f"WebSocket closed: {code} {reason}")


def run_websocket_forever():
    while True:
        try:
            ws = websocket.WebSocketApp(
                DERIV_WS,
                on_message=on_ws_message,
                on_open=lambda w: on_ws_open(w),
                on_error=lambda w, e: on_ws_error(w, e),
                on_close=lambda w, c, r: on_ws_close(w, c, r),
            )
            ws.run_forever(ping_interval=30, ping_timeout=10)
        except Exception:
            logging.exception("Websocket crashed — reconnecting in 3s")
            time.sleep(3)


# ---------------- Scheduler ----------------
def scheduler_loop():
    """
    Schedules:
    - presignal at slot - 2 minutes
    - main at slot
    - expiry at slot + 5 minutes
    Uses latest_epoch (UTC seconds from ticks), converts to Nairobi for display.
    """
    presignal_sent = False
    main_sent = False
    expiry_sent = False
    candidate = None
    current_slot_epoch = None

    while True:
        with state_lock:
            epoch = latest_epoch

        if epoch is None:
            logging.debug("Waiting for first tick to sync Deriv time...")
            time.sleep(0.8)
            continue

        now_utc = datetime.fromtimestamp(epoch, tz=pytz.UTC)
        now_na = now_utc.astimezone(NAIROBI_TZ)

        # find next 10-min slot (ceiling)
        bucket_min = (now_na.minute // 10) * 10
        slot_na = now_na.replace(minute=bucket_min, second=0, microsecond=0)
        if now_na >= slot_na:
            slot_na = slot_na + timedelta(minutes=10)

        slot_utc = slot_na.astimezone(pytz.UTC)
        slot_epoch = int(slot_utc.timestamp())
        presignal_epoch = slot_epoch - 120
        expiry_epoch = slot_epoch + 300

        # reset flags when slot advances
        if current_slot_epoch != slot_epoch:
            logging.info(f"Upcoming slot (Nairobi): {slot_na.strftime('%Y-%m-%d %H:%M:%S')}")
            current_slot_epoch = slot_epoch
            presignal_sent = False
            main_sent = False
            expiry_sent = False
            candidate = None

        # PRESIGNAL
        if (not presignal_sent) and (presignal_epoch <= epoch < slot_epoch):
            logging.info("PRESIGNAL window — running analysis")
            candidate = pick_best_market_strategy()
            if candidate:
                pres_text = (
                    f"📢 <b>Upcoming Signal Reminder</b>\n\n"
                    f"⏰ <b>Entry in 2 minutes</b>\n"
                    f"📊 Market: <b>{candidate['market_name']}</b>\n"
                    f"🎯 Strategy: <b>{candidate['strategy']}</b>\n"
                    f"🔢 Candidate Entry Digit: <b>{candidate['best_digit']}</b>\n"
                    f"📈 Confidence: <b>{candidate['confidence']:.2%}</b> ({candidate['count']}/{candidate['total']})\n"
                    f"🕒 Entry Time (Nairobi): {slot_na.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    f"⚡ Get ready!"
                )
            else:
                pres_text = (
                    f"📢 <b>Upcoming Signal Reminder</b>\n\n"
                    f"⏰ Entry in 2 minutes\n"
                    f"⚠️ Not enough data to produce a reliable signal right now.\n"
                    f"🕒 Entry Time (Nairobi): {slot_na.strftime('%Y-%m-%d %H:%M:%S')}"
                )
            send_telegram(pres_text, keep=False)
            presignal_sent = True

        # MAIN
        if (not main_sent) and (epoch >= slot_epoch):
            logging.info("MAIN slot reached — sending main signal")
            if candidate is None:
                candidate = pick_best_market_strategy()
            if candidate:
                expiry_na = datetime.fromtimestamp(expiry_epoch, tz=pytz.UTC).astimezone(NAIROBI_TZ)
                main_text = (
                    f"⚡ <b>Main Signal</b>\n\n"
                    f"📊 Market: <b>{candidate['market_name']}</b>\n"
                    f"🎯 Strategy: <b>{candidate['strategy']}</b>\n"
                    f"🔢 Entry Point Digit: <b>{candidate['best_digit']}</b>\n"
                    f"📈 Confidence: <b>{candidate['confidence']:.2%}</b> ({candidate['count']}/{candidate['total']})\n"
                    f"🕒 Time (Nairobi): {slot_na.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"⏳ Expires: {expiry_na.strftime('%Y-%m-%d %H:%M:%S')} (Nairobi)\n\n"
                    f"🔥 Execute now!"
                )
            else:
                main_text = (
                    f"⚡ <b>Main Signal</b>\n\n"
                    f"⚠️ Not enough data for a reliable signal.\n"
                    f"🕒 Time (Nairobi): {slot_na.strftime('%Y-%m-%d %H:%M:%S')}"
                )
            send_telegram(main_text, keep=False)
            main_sent = True

        # EXPIRY
        if (not expiry_sent) and (epoch >= expiry_epoch):
            logging.info("EXPIRY — sending expiry message and deleting pre+main")
            expiry_na = datetime.fromtimestamp(expiry_epoch, tz=pytz.UTC).astimezone(NAIROBI_TZ)
            next_slot_na = (slot_na + timedelta(minutes=10))
            expiry_text = (
                f"✅ <b>Signal Expired</b>\n\n"
                f"🕒 Expired at: {expiry_na.strftime('%Y-%m-%d %H:%M:%S')} (Nairobi)\n"
                f"🔔 Next expected slot: {next_slot_na.strftime('%Y-%m-%d %H:%M:%S')} (Nairobi)"
            )
            send_telegram(expiry_text, keep=True)
            delete_tracked_messages()
            expiry_sent = True

        time.sleep(0.6)


# ---------------- Main ----------------
if __name__ == "__main__":
    logging.info("Starting Deriv signal bot — syncing to Deriv server time via ticks.")
    # Start websocket thread
    ws_thread = threading.Thread(target=run_websocket_forever, daemon=True)
    ws_thread.start()
    # Run scheduler loop in main thread
    try:
        scheduler_loop()
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt — cleaning up")
        delete_tracked_messages()
        time.sleep(0.5)
