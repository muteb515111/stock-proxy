from fastapi import FastAPI, HTTPException, Query
from bs4 import BeautifulSoup
import httpx
import re
from datetime import datetime, timezone

VERSION = "3.0"

app = FastAPI(title="Stock Proxy", version=VERSION)

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

@app.get("/")
async def root():
    return {"message": "Proxy is working", "version": VERSION}

@app.get("/health")
async def health():
    return {"status": "ok", "version": VERSION}

@app.get("/yahoo/candles")
async def yahoo_candles(
    symbol: str = Query(...),
    period: str = Query("6mo"),
    interval: str = Query("1d"),
):
    url = "https://query1.finance.yahoo.com/v8/finance/chart/" + symbol
    params = {
        "range": period,
        "interval": interval,
        "includePrePost": "false",
    }
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            r = await client.get(url, params=params, headers=BROWSER_HEADERS)
            if r.status_code != 200:
                raise HTTPException(
                    status_code=r.status_code,
                    detail="Yahoo returned " + str(r.status_code),
                )
            data = r.json()
            result = data.get("chart", {}).get("result", [])
            if not result:
                raise HTTPException(status_code=404, detail="No data from Yahoo")

            chart = result[0]
            timestamps = chart.get("timestamp", [])
            quote = chart["indicators"]["quote"][0]
            opens = quote.get("open", [])
            highs = quote.get("high", [])
            lows = quote.get("low", [])
            closes = quote.get("close", [])
            volumes = quote.get("volume", [])

            candles = []
            for i, ts in enumerate(timestamps):
                if (
                    i < len(opens)
                    and opens[i] is not None
                    and i < len(closes)
                    and closes[i] is not None
                ):
                    candles.append({
                        "date": datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d"),
                        "open": opens[i],
                        "high": highs[i] if i < len(highs) else opens[i],
                        "low": lows[i] if i < len(lows) else opens[i],
                        "close": closes[i],
                        "volume": volumes[i] if i < len(volumes) and volumes[i] is not None else 0,
                    })

            return {"success": True, "symbol": symbol, "count": len(candles), "candles": candles}
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Yahoo timeout")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/yahoo/quote")
async def yahoo_quote(symbol: str = Query(...)):
    url = "https://query1.finance.yahoo.com/v7/finance/quote"
    params = {"symbols": symbol}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(url, params=params, headers=BROWSER_HEADERS)
            if r.status_code != 200:
                raise HTTPException(
                    status_code=r.status_code,
                    detail="Yahoo returned " + str(r.status_code),
                )
            data = r.json()
            results = data.get("quoteResponse", {}).get("result", [])
            if not results:
                raise HTTPException(status_code=404, detail="No quote data")
            q = results[0]
            return {
                "success": True,
                "symbol": q.get("symbol"),
                "price": q.get("regularMarketPrice"),
                "volume": q.get("regularMarketVolume"),
                "avgVolume": q.get("averageDailyVolume3Month"),
                "floatShares": q.get("floatShares"),
                "sharesOutstanding": q.get("sharesOutstanding"),
                "marketCap": q.get("marketCap"),
                "shortPercentOfFloat": q.get("shortPercentOfFloat"),
                "fiftyTwoWeekHigh": q.get("fiftyTwoWeekHigh"),
                "fiftyTwoWeekLow": q.get("fiftyTwoWeekLow"),
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/finviz/screener")
async def finviz_screener(
    filters: str = Query(""),
    tickers: str = Query(""),
):
    if tickers:
        url = "https://finviz.com/quote.ashx?t=" + tickers
    else:
        url = "https://finviz.com/screener.ashx?v=111"
        if filters:
            url += "&f=" + filters

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            r = await client.get(url, headers=BROWSER_HEADERS)
            if r.status_code != 200:
                raise HTTPException(
                    status_code=r.status_code,
                    detail="Finviz returned " + str(r.status_code),
                )

            soup = BeautifulSoup(r.text, "lxml")
            rows = []
            table = soup.find("table", class_=re.compile("screener|table"))
            if table:
                trs = table.find_all("tr")
                for tr in trs:
                    tds = tr.find_all("td")
                    if len(tds) >= 11:
                        ticker_link = tr.find("a", class_="tab-link")
                        if not ticker_link:
                            continue
                        row = {
                            "ticker": ticker_link.text.strip(),
                            "company": tds[2].text.strip() if len(tds) > 2 else "",
                            "sector": tds[3].text.strip() if len(tds) > 3 else "",
                            "market_cap": tds[6].text.strip() if len(tds) > 6 else "",
                            "price": tds[8].text.strip() if len(tds) > 8 else "",
                            "change": tds[9].text.strip() if len(tds) > 9 else "",
                            "volume": tds[10].text.strip() if len(tds) > 10 else "",
                        }
                        rows.append(row)

            return {"success": True, "count": len(rows), "results": rows}
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Finviz timeout")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/finviz/ticker")
async def finviz_ticker(symbol: str = Query(...)):
    url = "https://finviz.com/quote.ashx?t=" + symbol
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            r = await client.get(url, headers=BROWSER_HEADERS)
            if r.status_code != 200:
                raise HTTPException(
                    status_code=r.status_code,
                    detail="Finviz returned " + str(r.status_code),
                )

            soup = BeautifulSoup(r.text, "lxml")
            metrics = {}
            tables = soup.find_all("table", class_="snapshot-table2")
            for table in tables:
                trs = table.find_all("tr")
                for tr in trs:
                    tds = tr.find_all("td")
                    for i in range(0, len(tds) - 1, 2):
                        key = tds[i].text.strip()
                        val = tds[i + 1].text.strip()
                        if key and val:
                            metrics[key] = val

            return {"success": True, "symbol": symbol, "metrics": metrics}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
