# ============================================================
# Faisal Stock Screener Bot - Version 10.0
# Yahoo (via Proxy) + Finnhub metrics
# ============================================================

import os
import time
import random
import logging
import threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
import pandas as pd
import numpy as np
from flask import Flask

from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes

# ============================================================
# CONFIG
# ============================================================

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "")
TWELVEDATA_API_KEY = os.environ.get("TWELVEDATA_API_KEY", "")
PROXY_URL = os.environ.get("PROXY_URL", "")
ET = ZoneInfo("America/New_York")

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

flask_app = Flask(__name__)


@flask_app.route("/")
def home():
    return "Faisal Bot is running!", 200


@flask_app.route("/health")
def health():
    return {"status": "ok", "time": datetime.now(ET).isoformat()}, 200


def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port)


# ============================================================
# UNIVERSE
# ============================================================

LOCAL_UNIVERSE = [
    "AEMD", "AKAN", "BFRG", "BIAF", "BNKK", "CDTG", "CLIK", "CPOP",
    "DGHG", "DXST", "GWAV", "HTCR", "LFS", "MBRX", "MWC", "NXTS",
    "SVRE", "VSME", "YYAI", "SHPH", "SONN", "TNXP", "PHIO", "SNPX",
    "AVGR", "BDRX", "BIOR", "CLRB", "CRKN", "CYTX", "DTSS", "EEIQ",
    "ELAB", "EVGN", "EYEN", "FWBI", "GCTK", "GNPX", "HCDI", "HILS",
    "HOTH", "IMCC", "INBS", "INDP", "IPDN", "IVDA", "JWEL", "KITT",
    "KRKR", "LGMK", "LGVN", "LUCY", "LUXH", "MEGL", "MLGO", "MNPR",
    "MRIN", "MTNB", "MYNZ", "NEXI", "NITO", "NKGN", "NUKK", "NVOS",
    "OMQS", "ONCO", "OPGN", "OPTT", "PAVM", "PHGE", "PLRX", "PMN",
    "PRFX", "PRST", "PXMD", "QNRX", "RDHL", "RIME", "RKDA", "RSLS",
    "SBFM", "SCPX", "SEEL", "SGBX", "SLXN", "SNDL", "SOBR", "SPRB",
    "STAF", "STI", "SXTP", "SYRA", "TCON", "TCRT", "THMO", "TIVC",
    "TNON", "TOMZ", "TRNR", "TRVN", "TSBX", "UPC", "USEG", "VBIV",
    "VERO", "VINO", "VIRI", "VRPX", "VTVT", "WATT", "WISA", "WKEY",
    "XELB", "XERS", "XLO", "XRTX", "YCBD", "ZAPP", "ZCMD", "ZJYL",
    "BJDX", "CTM", "KWE", "SOPA", "PRSO", "ELYM", "ALLR", "AGRI",
    "ALZN", "AMST", "APRE",", "A "UID", "AUUD", "AVTX",B "AXLA", "BCDA",
    "BCLI", "BEAT", "BIVI", "BLBXMEA", "BNOX", "BOLT",
    "BRTX", "BTBT", "BTCS", "BTTR", "BYSI", "CANF", "CARV", "CASI",
    "CBIH", "CCCC", "CELZ", "CFRX", "CGEN", "CHRS", "CLVR", "CNTB",
    "CNTX", "COCP", "COEP", "CRBP", "CREX", "CRGE", "CTSO", "CUEN",
    "CVKD", "CVM", "CYCC", "CYTO", "DBGI", "DCTH", "DFLI", "DMAC",
    "DRMA", "DRRX", "EFTR", "EIGR", "ELDN", "ENG", "ENSC",
    "EPIX", "ERNA", "EVFM", "EVLO", "EXPR", "FBRX", "FFIE", "FGEN",
    "FHTX", "FLGC", "FPAY", "FRES", "FREQ", "FRGE", "GANX", "GENE",
    "GHSI", "GLMD", "GLTO", "GMBL", "GOVX", "GRNA", "GRTS",
    "GTBP", "GTHX", "HCWB", "HGEN", "HOLO", "HOOK", "HOWL", "HPCO",
]

# ============================================================
# FINNHUB METRICS
# ============================================================

_last_finnhub = {"time": 0}


def _finnhub_get(endpoint, params):
    now = time.time()
    elapsed = now - _last_finnhub["time"]
    if elapsed < 1.1:
        time.sleep(1.1 - elapsed)
    _last_finnhub["time"] = time.time()
    params["token"] = FINNHUB_API_KEY
    try:
        r = requests.get("https://finnhub.io/api/v1" + endpoint, params=params, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


# ============================================================
# DATA: Yahoo via Proxy + Finnhub
# ============================================================

def get_stock_data(symbol, period="6mo"):
    if PROXY_URL:
        try:
            url = PROXY_URL + "/yahoo/candles"
            r = requests.get(url, params={"symbol": symbol, "period": period}, timeout=30)
            if r.status_code == 200:
                data = r.json()
                if data.get("success") and data.get("candles"):
                    df = pd.DataFrame(data["candles"])
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.set_index("date").sort_index()
                    df.columns = [c.capitalize() for c in df.columns]

                    info = {"floatShares": 0, "averageVolume": 0,
                            "shortPercentOfFloat": 0,
                            "currentPrice": float(df["Close"].iloc[-1])}

                    if FINNHUB_API_KEY:
                        m = _finnhub_get("/stock/metric", {"symbol": symbol, "metric": "all"})
                        if m and "metric" in m:
                            mm = m["metric"]
                            ff = mm.get("freeFloat") or 0
                            info["floatShares"] = ff * 1000000 if ff and ff < 1000 else ff
                            av = mm.get("10DayAverageVolume") or 0
                            info["averageVolume"] = av * 1000000 if av and av < 1000 else av
                            sp = mm.get("shortPercentOfFloat") or 0
                            info["shortPercentOfFloat"] = sp / 100 if sp > 1 else sp

                    if not info["averageVolume"] and len(df) >= 20:
                        info["averageVolume"] = int(df["Volume"].tail(20).mean())

                    logger.info("Yahoo Proxy: " + symbol + " (" + str(len(df)) + " rows)")
                    return df, info
        except Exception as e:
            logger.warning("Proxy failed " + symbol + ": " + str(e))

    if TWELVEDATA_API_KEY:
        try:
            url = "https://api.twelvedata.com/time_series"
            params = {"symbol": symbol, "interval": "1day",
                      "outputsize": 200, "apikey": TWELVEDATA_API_KEY}
            r = requests.get(url, params=params, timeout=20)
            data = r.json()
            if data.get("status") != "error":
                values = data.get("values", [])
                if values and len(values) >= 30:
                    rows = []
                    for v in values:
                        rows.append({
                            "Date": v["datetime"],
                            "Open": float(v["open"]),
                            "High": float(v["high"]),
                            "Low": float(v["low"]),
                            "Close": float(v["close"]),
                            "Volume": int(float(v.get("volume", 0))) if v.get("volume") else 0,
                        })
                    df = pd.DataFrame(rows)
                    df["Date"] = pd.to_datetime(df["Date"])
                    df = df.set_index("Date").sort_index()
                    info = {"floatShares": 0,
                            "averageVolume": int(df["Volume"].tail(20).mean()),
                            "shortPercentOfFloat": 0,
                            "currentPrice": float(df["Close"].iloc[-1])}
                    return df, info
        except Exception:
            pass

    return pd.DataFrame(), {}


# ============================================================
# INDICATORS
# ============================================================

def calc_rsi(close, period=14):
    if len(close) < period + 1:
        return 50.0
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1]
    return float(val) if pd.notna(val) else 50.0


def calc_macd(close):
    if len(close) < 26:
        return 0, 0, 0, False, False
    e12 = close.ewm(span=12, adjust=False).mean()
    e26 = close.ewm(span=26, adjust=False).mean()
    macd = e12 - e26
    sig = macd.ewm(span=9, adjust=False).mean()
    h = macd - sig
    cur = h.iloc[-1]
    prev = h.iloc[-3] if len(h) > 3 else cur
    return float(macd.iloc[-1]), float(sig.iloc[-1]), float(cur), macd.iloc[-1] > sig.iloc[-1], cur > prev


def calc_sma(close, period):
    if len(close) < period:
        return None
    return float(close.rolling(period).mean().iloc[-1])


def calc_stoch(high, low, close, kp=14, dp=3):
    if len(close) < kp:
        return 50.0, 50.0
    ll = low.rolling(kp).min()
    hh = high.rolling(kp).max()
    d = (hh - ll).replace(0, np.nan)
    k = 100 * ((close - ll) / d)
    ks = k.rolling(dp).mean()
    kv = ks.iloc[-1]
    dv = ks.rolling(dp).mean().iloc[-1]
    return (float(kv) if pd.notna(kv) else 50.0,
            float(dv) if pd.notna(dv) else 50.0)


def find_sr(hist, window=20):
    if hist.empty or len(hist) < window:
        return None, None
    s = float(hist["Low"].rolling(window).min().iloc[-1])
    r = float(hist["High"].rolling(window).max().iloc[-1])
    return s, r


def former_runner(hist):
    if hist.empty or len(hist) < 20:
        return False
    ret = hist["Close"].pct_change()
    return bool((ret > 0.5).any())


# ============================================================
# SCORING
# ============================================================

def score_stock(symbol, hist, info):
    close = hist["Close"]
    high = hist["High"]
    low = hist["Low"]
    volume = hist["Volume"]
    price = float(close.iloc[-1])
    rsi = calc_rsi(close)
    _, _, _, macd_pos, macd_imp = calc_macd(close)
    stoch_k, _ = calc_stoch(high, low, close)
    sma20 = calc_sma(close, 20)
    sma30 = calc_sma(close, 30)
    sma50 = calc_sma(close, 50)
    support, resistance = find_sr(hist, 20)
    float_sh = info.get("floatShares", 0) or 0
    avg_vol = info.get("averageVolume", 0) or 0
    cur_vol = int(volume.iloc[-1]) if len(volume) else 0
    rvol = round(cur_vol / avg_vol, 2) if avg_vol > 0 else 0
    is_runner = former_runner(hist)

    bd = {}

    if 23 <= rsi <= 27:
        bd["rsi"] = 25
    elif 20 <= rsi < 23:
        bd["rsi"] = 12
    elif 27 < rsi <= 30:
        bd["rsi"] = 15
    elif 30 < rsi <= 33:
        bd["rsi"] = 6
    elif 33 < rsi <= 35:
        bd["rsi"] = 2
    else:
        bd["rsi"] = 0

    bd["split"] = 0

    if float_sh:
        if float_sh < 1000000:
            bd["float"] = 15
        elif float_sh < 5000000:
            bd["float"] = 12
        elif float_sh < 10000000:
            bd["float"] = 8
        elif float_sh < 20000000:
            bd["float"] = 5
        else:
            bd["float"] = 0
    else:
        bd["float"] = 0

    if macd_pos and macd_imp:
        bd["macd"] = 15
    elif macd_imp:
        bd["macd"] = 8
    else:
        bd["macd"] = 0

    if sma20 and sma30 and sma50:
        below = 0
        if price < sma20:
            below += 1
        if price < sma30:
            below += 1
        if price < sma50:
            below += 1
        bd["ma"] = {3: 15, 2: 8, 1: 5}.get(below, 0)
    else:
        bd["ma"] = 0

    if stoch_k < 20:
        bd["stoch"] = 10
    elif stoch_k < 30:
        bd["stoch"] = 8
    elif stoch_k < 40:
        bd["stoch"] = 6
    elif stoch_k < 50:
        bd["stoch"] = 4
    else:
        bd["stoch"] = 0

    dist_sup = None
    if support:
        dist_sup = round((price - support) / price * 100, 2)
        if dist_sup < 3:
            bd["support"] = 10
        elif dist_sup < 5:
            bd["support"] = 7
        elif dist_sup < 8:
            bd["support"] = 3
        else:
            bd["support"] = 0
    else:
        bd["support"] = 0

    bd["runner"] = 5 if is_runner else 0

    if rvol > 5:
        bd["rvol"] = 5
    elif rvol >= 2:
        bd["rvol"] = 3
    else:
        bd["rvol"] = 0

    total = sum(bd.values())

    if total >= 80:
        verdict = "مثالي"
    elif total >= 65:
        verdict = "ممتاز"
    elif total >= 50:
        verdict = "جيد"
    elif total >= 35:
        verdict = "ضعيف"
    else:
        verdict = "مرفوض"

    return {
        "symbol": symbol, "price": price,
        "rsi": round(rsi, 2), "stoch_k": round(stoch_k, 2),
        "macd_pos": macd_pos, "macd_improving": macd_imp,
        "sma20": sma20, "sma30": sma30, "sma50": sma50,
        "support": support, "resistance": resistance,
        "dist_support": dist_sup,
        "float_shares": float_sh, "rvol": rvol,
        "former_runner": is_runner,
        "breakdown": bd, "total": total, "verdict": verdict,
    }


def squeeze_score(hist, info, base):
    float_sh = base.get("float_shares") or 0
    short_pct = (info.get("shortPercentOfFloat", 0) or 0) * 100
    rsi = base.get("rsi", 50)
    stoch_k = base.get("stoch_k", 50)
    dist_sup = base.get("dist_support", 999)
    score = 0

    v = hist["Volume"].tail(4).values
    if len(v) >= 4 and v[-1] > v[-2] > v[-3]:
        score += 15
    elif len(v) >= 3 and v[-1] > v[-2]:
        score += 7

    lows = hist["Low"].tail(15).values
    if len(lows) >= 10 and lows[-5:].min() > lows[:5].min():
        score += 10

    if dist_sup is not None and dist_sup < 3:
        score += 10
    if base.get("macd_improving"):
        score += 5

    if short_pct >= 60:
        score += 20
    elif short_pct >= 40:
        score += 15
    elif short_pct >= 30:
        score += 10

    if float_sh:
        if float_sh < 2000000:
            score += 10
        elif float_sh < 5000000:
            score += 7
        elif float_sh < 10000000:
            score += 3

    if 20 <= rsi <= 27:
        score += 10
    elif 27 < rsi <= 35:
        score += 6

    if dist_sup is not None:
        if dist_sup < 2:
            score += 8
        elif dist_sup < 5:
            score += 5

    if stoch_k < 30:
        score += 7

    return min(score, 100)


# ============================================================
# SCANNER
# ============================================================

def finviz_scan(max_results=25):
    universe = LOCAL_UNIVERSE.copy()
    random.shuffle(universe)
    return [{"Ticker": s} for s in universe[:max_results]]


# ============================================================
# FORMATTERS
# ============================================================

def format_block(rank, r):
    lines = []
    if rank == 1:
        medal = "🥇"
    elif rank == 2:
        medal = "🥈"
    elif rank == 3:
        medal = "🥉"
    else:
        medal = "•"
    lines.append(medal + " <b>" + str(rank) + ". " + r["symbol"] + " - " + str(r["total"]) + "/100</b>")
    lines.append("💰 السعر: <code>$" + str(round(r["price"], 3)) + "</code>")
    lines.append("📊 RSI: <code>" + str(r["rsi"]) + "</code> | Stoch: <code>" + str(r["stoch_k"]) + "</code>")
    if r["macd_pos"] and r["macd_improving"]:
        me = "✅"
    elif r["macd_improving"]:
        me = "🟡"
    else:
        me = "❌"
    lines.append("📈 MACD: " + me)
    if r["sma20"] and r["sma30"] and r["sma50"]:
        below = 0
        if r["price"] < r["sma20"]:
            below += 1
        if r["price"] < r["sma30"]:
            below += 1
        if r["price"] < r["sma50"]:
            below += 1
        if below == 3:
            mt = "تحت الكل ✅"
        elif below > 0:
            mt = "تحت جزئياً"
        else:
            mt = "فوق الكل"
        lines.append("📉 المتوسطات: " + mt)
    if r["support"]:
        lines.append("📏 الدعم: <code>$" + str(round(r["support"], 3)) + "</code> (" + str(r["dist_support"]) + "%)")
    lines.append("⭐ " + r["verdict"])
    return "\n".join(lines)


# ============================================================
# HANDLERS
# ============================================================

async def cmd_start(update, ctx):
    msg = (
        "🎯 <b>Faisal's Stock Screener</b>\n"
        "البورصات: NASDAQ + NYSE\n"
        "📡 البيانات: Yahoo (Proxy) + Finnhub\n\n"
        "<b>الأوامر:</b>\n"
        "/top - أفضل 10 أسهم\n"
        "/scan - فحص سريع\n"
        "/hunt - رادار الاكتشاف\n"
        "/analyze SYMBOL - تحليل سهم\n"
        "/setup SYMBOL - خطة دخول\n\n"
        "⚠️ تعليمي فقط"
    )
    await update.message.reply_text(msg, parse_mode="HTML")


async def cmd_top(update, ctx):
    await update.message.reply_text("🔍 جاري فحص السوق...")
    rows = finviz_scan(20)
    results = []
    for row in rows:
        sym = row.get("Ticker")
        if not sym:
            continue
        try:
            hist, info = get_stock_data(sym)
            if hist.empty or len(hist) < 30:
                continue
            sc = score_stock(sym, hist, info)
            if sc["total"] >= 30:
                results.append(sc)
        except Exception as e:
            logger.warning("scan " + sym + ": " + str(e))

    if not results:
        await update.message.reply_text("📊 فُحص " + str(len(rows)) + " سهم - لا نتائج.")
        return

    results.sort(key=lambda x: x["total"], reverse=True)
    top = results[:10]
    header = "🎯 <b>أفضل " + str(len(top)) + " أسهم</b>\n"
    header += "⏰ " + datetime.now(ET).strftime("%Y-%m-%d %H:%M") + "\n"
    header += "🔍 فُحص: " + str(len(rows)) + "\n\n"
    body = "\n\n".join(format_block(i + 1, r) for i, r in enumerate(top))
    full = header + body + "\n\n⚠️ تعليمي فقط"

    if len(full) > 4000:
        await update.message.reply_text(header, parse_mode="HTML")
        for i in range(0, len(body), 3500):
            await update.message.reply_text(body[i:i+3500], parse_mode="HTML")
        await update.message.reply_text("⚠️ تعليمي فقط", parse_mode="HTML")
    else:
        await update.message.reply_text(full, parse_mode="HTML")


async def cmd_scan(update, ctx):
    await update.message.reply_text("🔍 فحص سريع...")
    rows = finviz_scan(10)
    results = []
    for row in rows:
        sym = row.get("Ticker")
        if not sym:
            continue
        try:
            hist, info = get_stock_data(sym)
            if hist.empty or len(hist) < 30:
                continue
            sc = score_stock(sym, hist, info)
            if sc["total"] >= 30:
                results.append(sc)
        except Exception:
            continue

    if not results:
        await update.message.reply_text("📊 لا نتائج.")
        return

    results.sort(key=lambda x: x["total"], reverse=True)
    top = results[:5]
    header = "🎯 <b>أفضل 5 أسهم</b>\n\n"
    body = "\n\n".join(format_block(i + 1, r) for i, r in enumerate(top))
    await update.message.reply_text(header + body, parse_mode="HTML")


async def cmd_hunt(update, ctx):
    await update.message.reply_text("💣 رادار الاكتشاف...")
    rows = finviz_scan(20)
    results = []
    for row in rows:
        sym = row.get("Ticker")
        if not sym:
            continue
        try:
            hist, info = get_stock_data(sym)
            if hist.empty or len(hist) < 30:
                continue
            base = score_stock(sym, hist, info)
            if base["rsi"] > 35:
                continue
            sq = squeeze_score(hist, info, base)
            if sq < 30:
                continue
            base["squeeze"] = sq
            base["total"] = sq
            results.append(base)
        except Exception:
            continue

    if not results:
        await update.message.reply_text("📊 لا فرص مبكرة.")
        return

    results.sort(key=lambda x: x["squeeze"], reverse=True)
    top = results[:10]
    header = "💣 <b>رادار الاكتشاف</b>\n\n"
    chunks = []
    for i, r in enumerate(top, 1):
        block = format_block(i, r) + "\n⚡ Squeeze: " + str(r.get("squeeze", 0)) + "/100"
        chunks.append(block)
    await update.message.reply_text(header + "\n\n".join(chunks), parse_mode="HTML")


async def cmd_analyze(update, ctx):
    if not ctx.args:
        await update.message.reply_text("استخدم: /analyze SYMBOL")
        return
    sym = ctx.args[0].upper()
    await update.message.reply_text("🔬 تحليل " + sym + "...")
    hist, info = get_stock_data(sym)
    if hist.empty:
        await update.message.reply_text("❌ لا بيانات لـ " + sym)
        return
    r = score_stock(sym, hist, info)
    msg = "📊 <b>تحليل " + sym + "</b>\n\n"
    msg += "💰 السعر: <code>$" + str(round(r["price"], 3)) + "</code>\n"
    msg += "📊 RSI: <code>" + str(r["rsi"]) + "</code> | Stoch: <code>" + str(r["stoch_k"]) + "</code>\n"
    mt = "إيجابي" if r["macd_pos"] else "سلبي"
    it = "يتحسن" if r["macd_improving"] else "لا يتحسن"
    msg += "📈 MACD: " + mt + " | " + it + "\n"
    if r["float_shares"]:
        msg += "📦 Float: <code>" + str(round(r["float_shares"]/1000000, 2)) + "M</code>\n"
    msg += "📊 RVOL: <code>" + str(r["rvol"]) + "</code>\n\n"
    if r["support"]:
        msg += "📏 الدعم: <code>$" + str(round(r["support"], 3)) + "</code> (" + str(r["dist_support"]) + "%)\n"
    if r["resistance"]:
        msg += "🚀 المقاومة: <code>$" + str(round(r["resistance"], 3)) + "</code>\n"
    msg += "\n<b>النقاط:</b>\n"
    for k, v in r["breakdown"].items():
        msg += "• " + k + ": " + str(v) + "\n"
    msg += "\n🎯 <b>المجموع: " + str(r["total"]) + "/100</b>\n⭐ " + r["verdict"] + "\n"
    await update.message.reply_text(msg, parse_mode="HTML")


async def cmd_setup(update, ctx):
    if not ctx.args:
        await update.message.reply_text("استخدم: /setup SYMBOL")
        return
    sym = ctx.args[0].upper()
    await update.message.reply_text("🎯 تحليل " + sym + "...")
    hist, info = get_stock_data(sym)
    if hist.empty:
        await update.message.reply_text("❌ لا بيانات لـ " + sym)
        return
    price = float(hist["Close"].iloc[-1])
    support, resistance = find_sr(hist, 20)
    if not support:
        await update.message.reply_text("❌ لا دعم واضح")
        return
    sweep = support * 0.90
    e1 = round(support * 0.98, 3)
    e2 = round(support * 0.96, 3)
    e3 = round(support * 0.92, 3)
    stop = round(support * 0.86, 3)
    dist = round((price - support) / price * 100, 2) if support else None
    rsi = calc_rsi(hist["Close"])
    stoch_k, _ = calc_stoch(hist["High"], hist["Low"], hist["Close"])
    msg = "🎯 <b>خطة " + sym + "</b>\n\n"
    msg += "💰 السعر: <code>$" + str(round(price, 3)) + "</code>\n"
    msg += "📊 RSI: <code>" + str(round(rsi, 2)) + "</code>\n\n"
    msg += "📍 <b>المستويات:</b>\n"
    msg += "• الدعم: <code>$" + str(round(support, 3)) + "</code>\n"
    msg += "• سحب السيولة: <code>$" + str(round(sweep, 3)) + "</code>\n"
    if resistance:
        msg += "• المقاومة: <code>$" + str(round(resistance, 3)) + "</code>\n"
    msg += "\n📋 <b>خطة الدخول:</b>\n"
    msg += "• طلب 1: <code>$" + str(e1) + "</code>\n"
    msg += "• طلب 2: <code>$" + str(e2) + "</code>\n"
    msg += "• طلب 3: <code>$" + str(e3) + "</code>\n"
    msg += "🛑 وقف: <code>$" + str(stop) + "</code>\n"
    msg += "\n⚠️ تعليمي فقط"
    await update.message.reply_text(msg, parse_mode="HTML")


async def post_init(app):
    await app.bot.set_my_commands([
        BotCommand("start", "Help"),
        BotCommand("top", "أفضل 10"),
        BotCommand("scan", "فحص سريع"),
        BotCommand("hunt", "رادار الاكتشاف"),
        BotCommand("analyze", "تحليل سهم"),
        BotCommand("setup", "خطة دخول"),
    ])


def main():
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask started")

    if not TELEGRAM_BOT_TOKEN:
        logger.error("No token!")
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("top", cmd_top))
    app.add_handler(CommandHandler("scan", cmd_scan))
    app.add_handler(CommandHandler("hunt", cmd_hunt))
    app.add_handler(CommandHandler("analyze", cmd_analyze))
    app.add_handler(CommandHandler("setup", cmd_setup))

    logger.info("🚀 Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
