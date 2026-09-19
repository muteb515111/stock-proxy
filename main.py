from fastapi import FastAPI, HTTPException, Query
import httpx
from datetime import datetime, timezone

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Proxy v6", "status": "working"}


@app.get("/health")
async def health():
    return {"status": "ok", "version": "6"}


@app.get("/yahoo/candles")
async def yahoo_candles(symbol: str = Query(...), period: str = Query("6mo")):
    url = "https://query1.finance.yahoo.com/v8/finance/chart/" + symbol
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(url, params={"range": period, "interval": "1d"}, headers={"User-Agent": "Mozilla/5.0"})
        data = r.json()
    result = data.get("chart", {}).get("result", [])
    if not result:
        raise HTTPException(404, "No data")
    chart = result[0]
    ts = chart.get("timestamp", [])
    q = chart["indicators"]["quote"][0]
    candles = []
    for i, t in enumerate(ts):
        if i < len(q["close"]) and q["close"][i] is not None:
            candles.append({
                "date": datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d"),
                "open": q["open"][i], "high": q["high"][i],
                "low": q["low"][i], "close": q["close"][i],
                "volume": q["volume"][i] or 0,
            })
    return {"success": True, "count": len(candles), "candles": candles}


@app.get("/yahoo/quote")
async def yahoo_quote(symbol: str = Query(...)):
    url = "https://query1.finance.yahoo.com/v7/finance/quote"
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(url, params={"symbols": symbol}, headers={"User-Agent": "Mozilla/5.0"})
        data = r.json()
    res = data.get("quoteResponse", {}).get("result", [])
    if not res:
        raise HTTPException(404, "No quote")
    q = res[0]
    return {
        "success": True, "symbol": q.get("symbol"),
        "price": q.get("regularMarketPrice"),
        "volume": q.get("regularMarketVolume"),
        "avgVolume": q.get("averageDailyVolume3Month"),
        "floatShares": q.get("floatShares"),
        "marketCap": q.get("marketCap"),
        "shortPercentOfFloat": q.get("shortPercentOfFloat"),
    }