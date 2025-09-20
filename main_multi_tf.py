import os
import time
import json
import requests
import pandas as pd
import numpy as np
from telegram import Bot
from telegram.error import TelegramError
from datetime import datetime

# ==== Load Environment Variables ====
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
BINANCE_SYMBOLS = os.environ.get("BINANCE_SYMBOLS", "BTCUSDT,ETHUSDT").split(",")
BINANCE_INTERVALS = os.environ.get("BINANCE_INTERVALS", "1h,15m").split(",")
ZIGZAG_PCT = float(os.environ.get("ZIGZAG_PCT", "0.01"))

bot = Bot(token=TELEGRAM_TOKEN)

# ==== Helper: Fetch Data from Binance ====
def fetch_binance_klines(symbol, interval, limit=200):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    r = requests.get(url, timeout=10)
    data = r.json()
    df = pd.DataFrame(data, columns=[
        'timestamp','open','high','low','close','volume',
        'close_time','quote_asset_volume','trades','taker_base','taker_quote','ignore'
    ])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['close'] = df['close'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['open'] = df['open'].astype(float)
    return df[['timestamp','open','high','low','close']]

# ==== ZigZag Swing Detection ====
def zigzag(df, pct=0.01):
    closes = df['close'].values
    pivots = [0]
    trend = 0
    for i in range(1, len(closes)):
        diff = closes[i] - closes[pivots[-1]]
        if trend == 0:
            if abs(diff) / closes[pivots[-1]] > pct:
                trend = 1 if diff > 0 else -1
                pivots.append(i)
        elif trend == 1 and closes[i] < closes[pivots[-1]] * (1 - pct):
            trend = -1
            pivots.append(i)
        elif trend == -1 and closes[i] > closes[pivots[-1]] * (1 + pct):
            trend = 1
            pivots.append(i)
    return pivots

# ==== Simple Harmonic Pattern Detection (example only) ====
def detect_harmonic(points):
    # Placeholder: basic pattern check
    if len(points) < 5:
        return None
    p = [pt[1] for pt in points]
    XA = abs(p[1] - p[0])
    AB = abs(p[2] - p[1])
    BC = abs(p[3] - p[2])
    CD = abs(p[4] - p[3])
    # Simple ratio check for Gartley
    if 0.61 < AB/XA < 0.79 and 0.38 < BC/AB < 0.886:
        return "Potential Gartley"
    return None

# ==== Entry / SL / TP Calculation (basic) ====
def calculate_levels(df):
    last_close = df['close'].iloc[-1]
    sl = last_close * 0.98
    tp1 = last_close * 1.02
    tp2 = last_close * 1.04
    tp3 = last_close * 1.06
    return sl, tp1, tp2, tp3

# ==== Send Telegram Message ====
def send_message(text):
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)
    except TelegramError as e:
        print("Telegram Error:", e)

# ==== Main Loop ====
def run_bot():
    print("🚀 Bot started (multi-timeframe)...")
    while True:
        for symbol in BINANCE_SYMBOLS:
            for interval in BINANCE_INTERVALS:
                try:
                    df = fetch_binance_klines(symbol, interval, 200)
                    pivots = zigzag(df, ZIGZAG_PCT)
                    if len(pivots) >= 5:
                        pts = [(df['timestamp'].iloc[i], df['close'].iloc[i]) for i in pivots[-5:]]
                        pattern = detect_harmonic(pts)
                        if pattern:
                            sl, tp1, tp2, tp3 = calculate_levels(df)
                            msg = (
                                f"🔔 [{interval}] {symbol}\n"
                                f"Pattern Detected: {pattern}\n"
                                f"Entry: {df['close'].iloc[-1]:.2f}\n"
                                f"SL: {sl:.2f}\n"
                                f"TP1: {tp1:.2f}\nTP2: {tp2:.2f}\nTP3: {tp3:.2f}\n"
                                f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
                            )
                            send_message(msg)
                except Exception as e:
                    print(f"Error {symbol}-{interval}:", e)
        time.sleep(60)  # check every 1 minute

if __name__ == "__main__":
    run_bot()
