import os
import json
import time
import datetime

CACHE_DIR = os.path.join(os.path.dirname(__file__), "data", "cache")

def get_cached_prices(symbol: str) -> list:
    """로컬 캐시 확인"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(CACHE_DIR, f"{symbol.upper()}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if len(data) >= 10:
                    return data
        except Exception:
            pass
    return []

def save_cached_prices(symbol: str, daily_records: list):
    """일봉 데이터 로컬 캐싱"""
    if not daily_records:
        return
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(CACHE_DIR, f"{symbol.upper()}.json")
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(daily_records, f, ensure_ascii=False)
    except Exception:
        pass

def fetch_historical_daily_prices(symbol: str) -> list:
    """캐시 -> yfinance 라이브러리 -> 직접 API 세션 순으로 데이터 수집 (429 차단 원천 방지)"""
    cached = get_cached_prices(symbol)
    if cached:
        return cached

    clean_sym = symbol.replace(".", "-")
    records = []

    # 방법 1. yfinance 라이브러리 (공식 크럼/쿠키 자동 관리로 429 차단 없음)
    try:
        import yfinance as yf
        ticker = yf.Ticker(clean_sym)
        hist = ticker.history(period="max")
        if not hist.empty:
            for idx, row in hist.iterrows():
                close_val = float(row.get("Close", 0))
                if close_val > 0:
                    d_str = idx.strftime("%Y-%m-%d")
                    records.append({"date": d_str, "close": close_val})
            if len(records) >= 10:
                save_cached_prices(symbol, records)
                return records
    except Exception:
        pass

    # 방법 2. 직접 requests 호출 (10y 주봉/일봉 축소 요청)
    import requests
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "*/*"
    }
    for interval in ["1d", "1wk"]:
        try:
            url = f"https://query2.finance.yahoo.com/v8/finance/chart/{clean_sym}?interval={interval}&range=10y"
            res = requests.get(url, headers=headers, timeout=8)
            if res.status_code == 200:
                data = res.json()
                res_list = data.get("chart", {}).get("result", [])
                if res_list:
                    timestamps = res_list[0].get("timestamp", [])
                    indicators = res_list[0].get("indicators", {}).get("quote", [{}])[0]
                    closes = indicators.get("close", [])
                    for ts, c in zip(timestamps, closes):
                        if c is not None and c > 0:
                            d_str = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                            records.append({"date": d_str, "close": float(c)})
                    if len(records) >= 10:
                        save_cached_prices(symbol, records)
                        return records
        except Exception:
            pass

    return records

def calculate_mdd(daily_prices: list) -> dict:
    """일봉 리스트로부터 MDD(최대 낙폭) 및 고점/저점 일자 계산"""
    if not daily_prices or len(daily_prices) < 5:
        return {
            "mdd_pct": 0.0,
            "peak_date": "-",
            "peak_price": 0.0,
            "trough_date": "-",
            "trough_price": 0.0,
            "all_time_high": 0.0,
            "ath_date": "-",
            "current_price": 0.0,
            "current_dd_from_ath": 0.0
        }

    peak_price = daily_prices[0]["close"]
    peak_date = daily_prices[0]["date"]
    ath_price = daily_prices[0]["close"]
    ath_date = daily_prices[0]["date"]

    max_drawdown = 0.0
    mdd_peak_date = peak_date
    mdd_peak_price = peak_price
    mdd_trough_date = peak_date
    mdd_trough_price = peak_price

    running_peak = peak_price
    running_peak_date = peak_date

    for item in daily_prices:
        p = item["close"]
        d = item["date"]

        if p > running_peak:
            running_peak = p
            running_peak_date = d

        if p > ath_price:
            ath_price = p
            ath_date = d

        dd = (p - running_peak) / running_peak
        if dd < max_drawdown:
            max_drawdown = dd
            mdd_peak_price = running_peak
            mdd_peak_date = running_peak_date
            mdd_trough_price = p
            mdd_trough_date = d

    current_price = daily_prices[-1]["close"]
    current_dd_from_ath = ((current_price - ath_price) / ath_price) * 100

    return {
        "mdd_pct": round(max_drawdown * 100, 2),
        "peak_date": mdd_peak_date,
        "peak_price": round(mdd_peak_price, 2),
        "trough_date": mdd_trough_date,
        "trough_price": round(mdd_trough_price, 2),
        "all_time_high": round(ath_price, 2),
        "ath_date": ath_date,
        "current_price": round(current_price, 2),
        "current_dd_from_ath": round(current_dd_from_ath, 2)
    }

def analyze_ticker_mdd(symbol: str, name: str = "", sector: str = "") -> dict:
    """종목의 10년 및 20년 MDD를 종합 산출"""
    all_prices = fetch_historical_daily_prices(symbol)
    if not all_prices:
        return {
            "symbol": symbol,
            "name": name if name else symbol,
            "sector": sector,
            "current_price": 0.0,
            "ath_price": 0.0,
            "current_dd": "-",
            "mdd_10y": "-",
            "mdd_10y_period": "-",
            "mdd_20y": "-",
            "mdd_20y_period": "-",
            "proximity_to_10y_mdd": "-",
            "status": "데이터 없음",
            "updated_at": datetime.date.today().strftime("%Y-%m-%d")
        }

    now = datetime.datetime.now()
    date_10y_ago = (now - datetime.timedelta(days=365 * 10)).strftime("%Y-%m-%d")
    date_20y_ago = (now - datetime.timedelta(days=365 * 20)).strftime("%Y-%m-%d")

    prices_20y = [x for x in all_prices if x["date"] >= date_20y_ago]
    prices_10y = [x for x in all_prices if x["date"] >= date_10y_ago]

    mdd_20 = calculate_mdd(prices_20y if prices_20y else all_prices)
    mdd_10 = calculate_mdd(prices_10y if prices_10y else all_prices)

    cur_price = mdd_20["current_price"]
    cur_dd = mdd_20["current_dd_from_ath"]

    mdd_10_target = abs(mdd_10["mdd_pct"])
    cur_dd_abs = abs(cur_dd) if cur_dd < 0 else 0.0
    proximity_ratio = (cur_dd_abs / mdd_10_target * 100) if mdd_10_target > 0 else 0.0

    status = "정상/상승권"
    if proximity_ratio >= 90.0:
        status = "🚨 역사적 MDD 근접 (바닥권)"
    elif proximity_ratio >= 70.0:
        status = "⚠️ 과매도 조정권 (관심)"
    elif cur_dd <= -20.0:
        status = "📉 기술적 약세장 (-20% 이상)"

    return {
        "symbol": symbol,
        "name": name if name else symbol,
        "sector": sector,
        "current_price": cur_price,
        "ath_price": mdd_20["all_time_high"],
        "current_dd": f"{cur_dd:+.2f}%",
        "mdd_10y": f"{mdd_10['mdd_pct']:.2f}%",
        "mdd_10y_period": f"{mdd_10['peak_date']} ~ {mdd_10['trough_date']}",
        "mdd_20y": f"{mdd_20['mdd_pct']:.2f}%",
        "mdd_20y_period": f"{mdd_20['peak_date']} ~ {mdd_20['trough_date']}",
        "proximity_to_10y_mdd": f"{proximity_ratio:.1f}%",
        "status": status,
        "updated_at": datetime.date.today().strftime("%Y-%m-%d")
    }
