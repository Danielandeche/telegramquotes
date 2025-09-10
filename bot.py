#!/usr/bin/env python3
"""
deriv_signal_bot.py

- Uses Deriv tick epoch (server time) to schedule signals.
- Presignal = slot - 2 minutes, Main = slot, Expiry = slot + 5 minutes.
- Analysis: last up to 5000 ticks per market; finds best preceding digit
  for Over 3 and Under 6, chooses strongest (by confidence).
- Avoids duplicate messages; deletes pre+main on expiry (keeps expiry).
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

# ---------------- CONFIG ----------------
TOKEN = "8225529337:AAFYdTwJVTTLC1RvwiYrkzI9jcV-VpCiADM"
CHAT_ID = -1002776818122
BASE_TELEGRAM = f"https://api.telegram.org/bot{TOKEN}"

DERIV_WS = "wss://ws.binaryws.com/websockets/v3?app_id=1089"

# Markets to analyze (change to single market if you prefer)
MARKETS = ["R_10", "R_25", "R_50", "R_75", "R_100"]
MARKET_NAMES = {
    "R_10": "Volatility 10 Index",
    "R_25": "Volatility 25 Index",
    "R_50": "Volatility 50 Index",
    "R_75": "Volatility 75 Index",
    "R_100": "Volatility 100 Index",
}

MAX_TICKS = 5000
MIN_TICKS_FOR_ANALYSIS = 100  # require at least this many ticks per market to analyze
NAIROBI_TZ = pytz.timezone("Africa/Nairobi")
# ----------------------------------------

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Shared state
market_ticks = {m: deque(maxlen=MAX_TICKS) for m in MARKETS}
latest_epoch = None  # seconds (UTC) from last tick
state_lock = threading.Lock()

# tracked message ids for deletion (pre + main)
tracked_message_ids = []

# ---------------- Telegram helpers ----------------
def send_text_message(text: str, keep: bool = False):
    """Send a Telegram text message. Record message_id if not 'keep' (so we can delete later)."""
    try:
        resp = requests.post(
            f"{BASE_TELEGRAM}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            },
            timeout=10,
        )
        if resp.ok:
            mid = resp.json().get("result", {}).get("message_id")
            logging.info(f"Telegram sent message_id={mid}")
            if mid and not keep:
                tracked_message_ids.append(mid)
            return mid
        else:
            logging.error(f"Telegram send failed: {resp.status_code} {resp.text}")
    except Exception as e:
        logging.exception("Exception sending Telegram message")
    return None

def delete_tracked_messages():
    """Delete tracked pre/main messages (best-effort)."""
    global tracked_message_ids
    for mid in list(tracked_message_ids):
        try:
            requests.post(
                f"{BASE_TELEGRAM}/deleteMessage",
                json={"chat_id": CHAT_ID, "message_id": mid},
                timeout=8,
            )
            logging.info(f"Deleted Telegram message {mid}")
        except Exception:
            logging.exception(f"Failed deleting message {mid}")
    tracked_message_ids = []

# ---------------- Utilities & Analysis ----------------
def get_last_digit_from_quote(q):
    """Extract last digit from a quote robustly (handles floats & strings)."""
    s = str(q)
    for ch in reversed(s):
        if ch.isdigit():
            return int(ch)
    return None

def analyze_ticks_for_market(ticks_deque):
    """
    Return analysis dict for a market:
    {
      "over3": {"best_digit": int, "count": int, "total": int, "confidence": float} or None,
      "under6": {...} or None
    }
    """
    digits = []
    for q in ticks_deque:
        d = get_last_digit_from_quote(q)
        if d is not None:
            digits.append(d)
    if len(digits) < 2:
        return {"over3": None, "under6": None}

    over_counts = [0]*10
    under_counts = [0]*10
    tot_over = 0
    tot_under = 0

    for i in range(1, len(digits)):
        prev = digits[i-1]
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
        best_d = max(range(10), key=lambda x: counts[x])
        return {"best_digit": best_d, "count": counts[best_d], "total": total, "confidence": counts[best_d]/total}

    return {"over3": best(over_counts, tot_over), "under6": best(under_counts, tot_under)}

def pick_best_market_strategy():
    """
    Analyze all markets and return the best candidate or None.
    Candidate structure:
    {
      "market": "R_100",
      "market_name": "...",
      "strategy": "Over 3" or "Under 6",
      "best_digit": int,
      "count": int,
      "total": int,
      "confidence": float
    }
    """
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
            # pick by highest confidence, tie-breaker by count
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

# ---------------- WebSocket: collect ticks & server epoch ----------------
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
        epoch = tick.get("epoch")  # seconds (UTC)
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
    """Runs the WS client and reconnects automatically on drop."""
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

# ---------------- Scheduler (Deriv server time -> Nairobi) ----------------
def scheduler_loop():
    """
    Uses latest_epoch (UTC seconds from ticks) to determine Nairobi time and schedule:
    - presignal at slot - 2min
    - main at slot
    - expiry at slot + 5min
    """
    presignal_sent = False
    main_sent = False
    expiry_sent = False
    candidate = None
    current_slot_epoch = None  # epoch (UTC seconds) of the slot's start time in UTC

    while True:
        with state_lock:
            epoch = latest_epoch

        if epoch is None:
            logging.debug("Waiting for first tick to sync time...")
            time.sleep(0.8)
            continue

        # Convert Deriv epoch (UTC seconds) -> Nairobi datetime
        now_utc = datetime.fromtimestamp(epoch, tz=pytz.UTC)
        now_na = now_utc.astimezone(NAIROBI_TZ)

        # Compute next 10-minute slot (ceiling to the next 10-min mark)
        minute_bucket = (now_na.minute // 10) * 10
        slot_na = now_na.replace(minute=minute_bucket, second=0, microsecond=0)
        if now_na >= slot_na:
            slot_na = slot_na + timedelta(minutes=10)

        # Convert slot_na back to UTC epoch seconds (slot's main time)
        slot_utc = slot_na.astimezone(pytz.UTC)
        slot_epoch = int(slot_utc.timestamp())

        presignal_epoch = slot_epoch - 120  # 2 minutes before
        main_epoch = slot_epoch
        expiry_epoch = slot_epoch + 300  # +5 minutes

        # If slot changed (new upcoming slot) reset flags (only if we moved to a new slot)
        if current_slot_epoch != slot_epoch:
            logging.info(f"New upcoming slot at (Nairobi) {slot_na.strftime('%Y-%m-%d %H:%M:%S')}")
            current_slot_epoch = slot_epoch
            presignal_sent = False
            main_sent = False
            expiry_sent = False
            candidate = None
            # Do NOT clear tracked_message_ids here (we clear them on expiry)

        # PRESIGNAL window (send once)
        if (not presignal_sent) and (presignal_epoch <= epoch < main_epoch):
            logging.info("PRESIGNAL WINDOW — running analysis")
            candidate = pick_best_market_strategy()
            if candidate:
                text = (
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
                text = (
                    f"📢 <b>Upcoming Signal Reminder</b>\n\n"
                    f"⏰ Entry in 2 minutes\n"
                    f"⚠️ Not enough data to produce a reliable signal now.\n"
                    f"🕒 Entry Time (Nairobi): {slot_na.strftime('%Y-%m-%d %H:%M:%S')}"
                )
            send_text_message(text, keep=False)
            presignal_sent = True

        # MAIN signal (send once)
        if (not main_sent) and (epoch >= main_epoch):
            logging.info("MAIN SLOT reached — sending main signal")
            if candidate is None:
                candidate = pick_best_market_strategy()

            if candidate:
                expiry_na = datetime.fromtimestamp(expiry_epoch, tz=pytz.UTC).astimezone(NAIROBI_TZ)
                text = (
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
                text = (
                    f"⚡ <b>Main Signal</b>\n\n"
                    f"⚠️ No reliable signal (not enough data).\n"
                    f"🕒 Time (Nairobi): {slot_na.strftime('%Y-%m-%d %H:%M:%S')}"
                )
            send_text_message(text, keep=False)
            main_sent = True

        # EXPIRY (send once, keep expiry message and delete tracked pre+main)
        if (not expiry_sent) and (epoch >= expiry_epoch):
            logging.info("EXPIRY — sending expiry message and cleaning pre/main messages")
            expiry_na = datetime.fromtimestamp(expiry_epoch, tz=pytz.UTC).astimezone(NAIROBI_TZ)
            next_slot_na = (slot_na + timedelta(minutes=10))
            text = (
                f"✅ <b>Signal Expired</b>\n\n"
                f"🕒 Expired at: {expiry_na.strftime('%Y-%m-%d %H:%M:%S')} (Nairobi)\n"
                f"🔔 Next expected slot: {next_slot_na.strftime('%Y-%m-%d %H:%M:%S')} (Nairobi)"
            )
            send_text_message(text, keep=True)
            # delete pre + main (tracked_message_ids)
            delete_tracked_messages()
            expiry_sent = True
            # After expiry we will reset on next slot change above

        # small sleep to avoid busy loop
        time.sleep(0.6)

# ---------------- Main ----------------
if __name__ == "__main__":
    logging.info("Starting Deriv signal bot — syncing to Deriv server time via ticks.")

    # Start websocket thread
    ws_thread = threading.Thread(target=run_websocket_forever, daemon=True)
    ws_thread.start()

    # Start scheduler (runs in main thread; can be moved to its own thread if desired)
    try:
        scheduler_loop()
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt received — cleaning up and exiting.")
        delete_tracked_messages()
        time.sleep(0.5)
