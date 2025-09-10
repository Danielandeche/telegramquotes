#!/usr/bin/env python3
import time
import json
import threading
from collections import deque
from datetime import datetime, timedelta
import pytz
import requests
import websocket

# --- CONFIG ---
TOKEN = "8225529337:AAFYdTwJVTTLC1RvwiYrkzI9jcV-VpCiADM"
CHAT_ID = -1002776818122
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
DERIV_WS = "wss://ws.binaryws.com/websockets/v3?app_id=1089"

MARKETS = ["R_100"]  # keep only R_100 if you prefer
MARKET_NAMES = {"R_100": "Volatility 100 Index"}

MAX_TICKS = 5000
NAIROBI = pytz.timezone("Africa/Nairobi")

market_ticks = {m: deque(maxlen=MAX_TICKS) for m in MARKETS}
latest_epoch = None
lock = threading.Lock()

tracked_msgs = []

# --- TELEGRAM ---
def send_msg(text, keep=False):
    r = requests.post(f"{BASE_URL}/sendMessage",
        json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"})
    if r.ok:
        mid = r.json()["result"]["message_id"]
        if not keep:
            tracked_msgs.append(mid)
        return mid
    return None

def clear_msgs():
    global tracked_msgs
    for mid in tracked_msgs:
        requests.post(f"{BASE_URL}/deleteMessage", json={"chat_id": CHAT_ID, "message_id": mid})
    tracked_msgs = []

# --- ANALYSIS ---
def last_digit(q):
    s = str(q)
    for ch in reversed(s):
        if ch.isdigit():
            return int(ch)
    return None

def analyze(ticks):
    digits = [last_digit(q) for q in ticks if last_digit(q) is not None]
    if len(digits) < 50:
        return None
    over_counts = [0]*10
    under_counts = [0]*10
    tot_over = tot_under = 0
    for i in range(1, len(digits)):
        prev, cur = digits[i-1], digits[i]
        if cur > 3:
            over_counts[prev]+=1; tot_over+=1
        if cur < 6:
            under_counts[prev]+=1; tot_under+=1
    def best(counts, total):
        if total==0: return None
        d=max(range(10), key=lambda x: counts[x])
        return (d, counts[d], counts[d]/total)
    best_over = best(over_counts, tot_over)
    best_under = best(under_counts, tot_under)
    if not best_over and not best_under: return None
    if best_over and (not best_under or best_over[2]>=best_under[2]):
        return ("Over 3", *best_over)
    else:
        return ("Under 6", *best_under)

# --- WEBSOCKET ---
def on_msg(ws, msg):
    global latest_epoch
    d=json.loads(msg)
    if "tick" in d:
        sym=d["tick"]["symbol"]; q=d["tick"]["quote"]; e=d["tick"]["epoch"]
        with lock:
            market_ticks[sym].append(q)
            latest_epoch=e

def run_ws():
    ws=websocket.WebSocketApp(DERIV_WS,on_message=on_msg)
    ws.on_open=lambda w:[w.send(json.dumps({"ticks":m})) for m in MARKETS]
    ws.run_forever()

# --- SCHEDULER ---
def scheduler():
    present=False; mainsent=False; expsent=False; candidate=None
    while True:
        with lock: epoch=latest_epoch
        if not epoch:
            time.sleep(1); continue
        now=datetime.fromtimestamp(epoch,pytz.UTC).astimezone(NAIROBI)
        slot=(now.replace(minute=(now.minute//10)*10,second=0,microsecond=0))
        if now>=slot: slot+=timedelta(minutes=10)
        pre=slot-timedelta(minutes=2)
        exp=slot+timedelta(minutes=5)
        # PRESIGNAL
        if not present and pre<=now<slot:
            with lock: ticks=list(market_ticks["R_100"])
            candidate=analyze(ticks)
            if candidate:
                strat,digit,count,conf=candidate
                send_msg(f"📢 <b>Upcoming Signal</b>\n\n"
                         f"⏰ Entry in 2 minutes\n"
                         f"📊 Market: {MARKET_NAMES['R_100']}\n"
                         f"🎯 Strategy: {strat}\n"
                         f"🔢 Entry Digit: <b>{digit}</b>\n"
                         f"📈 Confidence: {conf:.2%}")
            else:
                send_msg("⚠️ Not enough data for signal.")
            present=True
        # MAIN
        if not mainsent and now>=slot:
            if candidate:
                strat,digit,count,conf=candidate
                send_msg(f"⚡ <b>Main Signal</b>\n\n"
                         f"📊 Market: {MARKET_NAMES['R_100']}\n"
                         f"🎯 Strategy: {strat}\n"
                         f"🔢 Entry Digit: <b>{digit}</b>\n"
                         f"📈 Confidence: {conf:.2%}\n"
                         f"⏳ Expires at {exp.strftime('%H:%M:%S')}")
            else:
                send_msg("⚠️ Main signal skipped (no data).")
            mainsent=True
        # EXPIRY
        if not expsent and now>=exp:
            send_msg(f"✅ <b>Signal Expired</b>\n\n"
                     f"🕒 Expired at {exp.strftime('%H:%M:%S')}",keep=True)
            clear_msgs()
            present=mainsent=expsent=False; candidate=None
        time.sleep(1)

# --- MAIN ---
if __name__=="__main__":
    threading.Thread(target=run_ws,daemon=True).start()
    scheduler()
