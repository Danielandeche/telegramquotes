#!/usr/bin/env python3
"""
deriv_signal_bot.py

- Subscribes to Deriv tick streams
- Uses server tick epoch as "Deriv time" and converts to Africa/Nairobi
- Sends presignal (slot - 2m), main signal (slot), expiry (slot + 5m)
- Analysis: looks at last up to 5000 ticks and finds the best "preceding digit"
  for Over 3 and for Under 6; chooses the strongest candidate.
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

# ---------- CONFIG ----------
TELEGRAM_TOKEN = "8225529337:AAFYdTwJVTTLC1RvwiYrkzI9jcV-VpCiADM"
TELEGRAM_CHAT_ID = -1002776818122
BASE_TELEGRAM = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

DERIV_WS_URL = "wss://ws.binaryws.com/websockets/v3?app_id=1089"

MARKETS = ["R_10", "R_25", "R_50", "R_75", "R_100"]
MARKET_NAMES = {
    "R_10": "Volatility 10 Index",
    "R_25": "Volatility 25 Index",
    "R_50": "Volatility 50 Index",
    "R_75": "Volatility 75 Index",
    "R_100": "Volatility 100 Index",
}

MAX_TICKS = 5000  # keep last 5000 ticks
MIN_TICKS_FOR_ANALYSIS = 100  # minimum ticks to analyze a market
NAIROBI_TZ = pytz.timezone("Africa/Nairobi")
# ----------------------------

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Shared state (thread-safe via lock)
market_ticks = {m: deque(maxlen=MAX_TICKS) for m in MARKETS}
latest_epoch = None  # last tick epoch from Deriv (UTC seconds)
state_lock = threading.Lock()

# Track message ids (so we can delete pre/main after expiry)
tracked_message_ids = []


# ---------- Utilities ----------
def send_telegram_message(text: str, parse_mode: str = "HTML") -> int | None:
    """Send Telegram message; returns message_id if successful."""
    try:
        resp = requests.post(
            f"{BASE_TELEGRAM}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": parse_mode},
            timeout=10,
        )
        if resp.ok:
            msg_id = resp.json().get("result", {}).get("message_id")
            logging.info(f"Telegram sent (message_id={msg_id})")
            return msg_id
        else:
            logging.error(f"Telegram send failed: {resp.status_code} {resp.text}")
    except Exception as e:
        logging.exception("Telegram send exception")
    return None


def delete_telegram_message(message_id: int):
    """Attempt to delete a Telegram message (ignore failures)."""
    try:
        requests.post(
            f"{BASE_TELEGRAM}/deleteMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "message_id": message_id},
            timeout=10,
        )
    except Exception:
        logging.exception("deleteMessage failed")


def clear_tracked_messages():
    """Delete tracked (pre + main) messages and clear list."""
    global tracked_message_ids
    for mid in tracked_message_ids:
        try:
            delete_telegram_message(mid)
        except Exception:
            pass
    tracked_message_ids = []


def get_last_digit_from_quote(q) -> int | None:
    """Robustly extract last digit character from a quote (float or str)."""
    s = str(q)
    # iterate reversed to find first digit char
    for ch in reversed(s):
        if ch.isdigit():
            return int(ch)
    return None


# ---------- Analysis ----------
def analyze_market_digits(ticks_deque: deque):
    """
    Given deque of quotes, compute:
    - best preceding digit for Over3 (digit after is >3)
    - best preceding digit for Under6 (digit after is <6)
    Returns dict: {
        "over3": {"best_digit": int, "count": int, "total": int, "confidence": float},
        "under6": {...}
    }
    If not enough events, totals are 0 and confidence 0.
    """
    digits = []
    for q in ticks_deque:
        d = get_last_digit_from_quote(q)
        if d is not None:
            digits.append(d)

    n = len(digits)
    if n < 2:
        return {"over3": None, "under6": None}

    over3_counts = [0] * 10
    under6_counts = [0] * 10
    total_over3 = 0
    total_under6 = 0

    for i in range(1, n):
        prev = digits[i - 1]
        cur = digits[i]

        # Over 3: cur in [4..9]
        if cur > 3:
            over3_counts[prev] += 1
            total_over3 += 1
        # Under 6: cur in [0..5]
        if cur < 6:
            under6_counts[prev] += 1
            total_under6 += 1

    def best_from_counts(counts, total):
        if total == 0:
            return {"best_digit": None, "count": 0, "total": 0, "confidence": 0.0}
        best_digit = max(range(10), key=lambda d: counts[d])
        best_count = counts[best_digit]
        return {
            "best_digit": int(best_digit),
            "count": int(best_count),
            "total": int(total),
            "confidence": float(best_count) / float(total),
        }

    return {"over3": best_from_counts(over3_counts, total_over3),
            "under6": best_from_counts(under6_counts, total_under6)}


def pick_best_market_and_strategy():
    """
    Analyze all markets and pick the single best (market, strategy) based on confidence.
    Strategy is either "Over 3" or "Under 6".
    Returns None if nothing qualifies, otherwise dict with:
    {market, market_name, strategy, best_digit, count, total, confidence}
    """
    best = None
    with state_lock:
        markets_copy = {m: list(market_ticks[m]) for m in MARKETS}

    for market, ticks in markets_copy.items():
        if len(ticks) < MIN_TICKS_FOR_ANALYSIS:
            continue
        res = analyze_market_digits(ticks)
        for strategy_key, strategy_name in (("over3", "Over 3"), ("under6", "Under 6")):
            info = res.get(strategy_key)
            if not info:
                continue
            if info["total"] == 0:
                continue
            conf = info["confidence"]
            # choose the highest confidence (tie-breaker by count)
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


# ---------- WebSocket (collect ticks & server time) ----------
def on_ws_message(ws, message):
    global latest_epoch
    try:
        data = json.loads(message)
    except Exception:
        return

    # Update ticks and epoch from tick messages
    if "tick" in data:
        tick = data["tick"]
        symbol = tick.get("symbol")
        quote = tick.get("quote")
        epoch = tick.get("epoch")  # seconds (UTC)
        if symbol and (symbol in market_ticks) and quote is not None:
            with state_lock:
                market_ticks[symbol].append(quote)
                latest_epoch = epoch
    # handle time response if sent explicitly (not necessary with ticks, but left for completeness)
    elif "time" in data:
        try:
            epoch = data.get("time")
            with state_lock:
                latest_epoch = epoch
        except Exception:
            pass


def on_ws_open(ws):
    logging.info("WebSocket opened, subscribing to ticks...")
    # Subscribe to markets
    for m in MARKETS:
        try:
            ws.send(json.dumps({"ticks": m}))
        except Exception:
            logging.exception(f"Failed to subscribe to {m}")


def on_ws_error(ws, err):
    logging.error(f"WebSocket error: {err}")


def on_ws_close(ws, code, reason):
    logging.warning(f"WebSocket closed: {code} {reason}")


def run_ws():
    """Run websocket in a blocking loop with auto-reconnect."""
    while True:
        try:
            ws = websocket.WebSocketApp(
                DERIV_WS_URL,
                on_message=on_ws_message,
                on_open=lambda w: on_ws_open(w),
                on_error=lambda w, e: on_ws_error(w, e),
                on_close=lambda w, c, r: on_ws_close(w, c, r),
            )
            ws.run_forever(ping_interval=30, ping_timeout=10)
        except Exception:
            logging.exception("Websocket crashed, reconnecting in 3s...")
            time.sleep(3)


# ---------- Scheduler (uses Deriv server time via latest_epoch) ----------
def scheduler_loop():
    """
    Main loop:
    - waits until latest_epoch is known
    - computes next slot (next multiple of 10 minutes)
    - sends presignal at slot-2min, main at slot, expiry at slot+5min
    """
    presignal_sent = False
    main_sent = False
    expiry_sent = False
    pending_signal = None  # store chosen market/strategy between pre and main

    while True:
        with state_lock:
            epoch = latest_epoch

        if epoch is None:
            logging.info("Waiting for first server tick (to sync Deriv time)...")
            time.sleep(1)
            continue

        now_na = datetime.fromtimestamp(epoch, tz=pytz.UTC).astimezone(NAIROBI_TZ)

        # find the upcoming 10-minute slot (round up to next multiple of 10)
        slot_minute = (now_na.minute // 10) * 10
        slot_time = now_na.replace(minute=slot_minute, second=0, microsecond=0)
        if now_na >= slot_time:
            slot_time = slot_time + timedelta(minutes=10)

        presignal_time = slot_time - timedelta(minutes=2)
        expiry_time = slot_time + timedelta(minutes=5)

        # PRESIGNAL (2 minutes before slot)
        if (not presignal_sent) and (presignal_time <= now_na < slot_time):
            # run analysis now to determine the candidate
            logging.info(f"Running analysis for presignal (slot at {slot_time.strftime('%Y-%m-%d %H:%M:%S')})")
            candidate = pick_best_market_and_strategy()
            if candidate:
                pending_signal = candidate
                pres_text = (
                    f"📢 <b>Upcoming Signal Reminder</b>\n\n"
                    f"⏰ <b>Entry in 2 minutes</b>\n"
                    f"📊 Market: <b>{candidate['market_name']}</b>\n"
                    f"🎯 Strategy: <b>{candidate['strategy']}</b>\n"
                    f"🔢 Candidate Entry Digit: <b>{candidate['best_digit']}</b>\n"
                    f"📈 Confidence: <b>{candidate['confidence']:.2%}</b> ({candidate['count']}/{candidate['total']})\n"
                    f"🕒 Entry Time (Nairobi): {slot_time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    f"⚡ Get ready!"
                )
            else:
                pending_signal = None
                pres_text = (
                    f"📢 <b>Upcoming Signal Reminder</b>\n\n"
                    f"⏰ Entry in 2 minutes\n"
                    f"⚠️ Not enough data to produce a reliable signal right now.\n"
                    f"🕒 Entry Time (Nairobi): {slot_time.strftime('%Y-%m-%d %H:%M:%S')}"
                )

            mid = send_telegram_message(pres_text, parse_mode="HTML")
            if mid:
                tracked_message_ids.append(mid)
            presignal_sent = True
            logging.info("Presignal sent.")
            # continue loop quickly (do not sleep long) so we catch main on time
            time.sleep(1)
            continue

        # MAIN SIGNAL (exact slot)
        if (not main_sent) and (now_na >= slot_time):
            # If we had a pending_signal from presignal, keep it; otherwise compute again
            logging.info("Generating main signal at slot time")
            if pending_signal is None:
                candidate = pick_best_market_and_strategy()
            else:
                candidate = pending_signal

            if candidate:
                main_text = (
                    f"⚡ <b>Main Signal</b>\n\n"
                    f"📊 Market: <b>{candidate['market_name']}</b>\n"
                    f"🎯 Strategy: <b>{candidate['strategy']}</b>\n"
                    f"🔢 Entry Point Digit: <b>{candidate['best_digit']}</b>\n"
                    f"📈 Confidence: <b>{candidate['confidence']:.2%}</b> ({candidate['count']}/{candidate['total']})\n"
                    f"🕒 Time (Nairobi): {slot_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"⏳ Expires: {expiry_time.strftime('%Y-%m-%d %H:%M:%S')} (Nairobi)\n\n"
                    f"🔥 Execute now!"
                )
            else:
                main_text = (
                    f"⚡ <b>Main Signal</b>\n\n"
                    f"⚠️ Not enough data for a reliable signal.\n"
                    f"🕒 Time (Nairobi): {slot_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"⏳ Expires: {expiry_time.strftime('%Y-%m-%d %H:%M:%S')} (Nairobi)"
                )

            mid = send_telegram_message(main_text, parse_mode="HTML")
            if mid:
                tracked_message_ids.append(mid)
            main_sent = True
            logging.info("Main signal sent.")
            time.sleep(1)
            continue

        # EXPIRY (slot + 5 minutes)
        if (not expiry_sent) and (now_na >= expiry_time):
            logging.info("Sending expiry message and cleaning pre/main messages")
            expiry_text = (
                f"✅ <b>Signal Expired</b>\n\n"
                f"🕒 Expired at: {expiry_time.strftime('%Y-%m-%d %H:%M:%S')} (Nairobi)\n"
                f"🔔 Next slot after: { (slot_time + timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S') } (Nairobi)"
            )
            # expiry is kept (not deleted)
            send_telegram_message(expiry_text, parse_mode="HTML")
            # delete previously tracked messages (pre + main)
            clear_tracked_messages()
            expiry_sent = True
            logging.info("Expiry processed.")

            # reset flags for the next slot
            presignal_sent = False
            main_sent = False
            expiry_sent = False
            pending_signal = None
            # tiny sleep so we don't immediately loop too hot
            time.sleep(1)
            continue

        # small sleep to avoid busy-looping
        time.sleep(0.8)


# ---------- Main ----------
if __name__ == "__main__":
    logging.info("Starting Deriv signal bot (Deriv time synced via ticks).")

    # Start websocket thread
    ws_thread = threading.Thread(target=run_ws, daemon=True)
    ws_thread.start()

    # Start scheduler loop in main thread (or you can run in another thread)
    try:
        scheduler_loop()
    except KeyboardInterrupt:
        logging.info("Stopping on KeyboardInterrupt. Cleaning up...")
        clear_tracked_messages()
        logging.info("Stopped.")
