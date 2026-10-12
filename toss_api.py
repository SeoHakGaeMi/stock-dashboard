import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://openapi.tossinvest.com"

def load_credentials():
    client_id = os.getenv("TOSS_CLIENT_ID", "").strip()
    client_secret = os.getenv("TOSS_CLIENT_SECRET", "").strip()

    txt_path = os.path.join(os.path.dirname(__file__), "api_key.txt")
    if os.path.exists(txt_path):
        try:
            with open(txt_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("TOSS_CLIENT_ID="):
                        val = line.split("=", 1)[1].strip()
                        if val:
                            client_id = val
                    elif line.startswith("TOSS_CLIENT_SECRET="):
                        val = line.split("=", 1)[1].strip()
                        if val:
                            client_secret = val
        except Exception:
            pass

    return client_id, client_secret

def format_num(val, is_currency=False):
    if val is None or val == "" or str(val).strip() == "-":
        return "-"
    try:
        clean = str(val).replace(",", "").replace("$", "").replace("원", "").strip()
        f = float(clean)
        if f.is_integer() and not is_currency:
            return f"{int(f):,}"
        return f"{f:,.2f}" if is_currency else f"{f:,.0f}"
    except Exception:
        return str(val)

def compute_intraday_trend(open_val, current_val):
    """시가(장초반) 대비 현재가(장막판)의 흐름 계산"""
    try:
        if not open_val or str(open_val).strip() == "-" or not current_val or str(current_val).strip() == "-":
            return "-", "시가 미제공"
        o = float(str(open_val).replace(",", "").replace("$", "").replace("원", "").strip())
        c = float(str(current_val).replace(",", "").replace("$", "").replace("원", "").strip())
        if o <= 0:
            return "-", "시가 미제공"
        diff_pct = ((c - o) / o) * 100
        if diff_pct >= 1.5:
            trend = "장중 급등(강세 🔥)"
        elif diff_pct > 0.15:
            trend = "장중 상승(우상향 📈)"
        elif diff_pct <= -1.5:
            trend = "장중 급락(차익실현 ⚠️)"
        elif diff_pct < -0.15:
            trend = "장중 반락(하방압력 📉)"
        else:
            trend = "시가선 유지(횡보 ➡️)"
        return f"{diff_pct:+.2f}%", trend
    except Exception:
        return "-", "판단불가"

def fetch_ohlc_fallback(symbol: str, is_kr: bool = False) -> dict:
    """시가(Open), 고가(High), 저가(Low) 정밀 보완"""
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

    if is_kr:
        # 방법 1: 네이버 실시간 polling API (초고속 JSON 응답)
        try:
            url = f"https://polling.finance.naver.com/api/realtime/domestic/stock/{symbol}"
            res = requests.get(url, headers=headers, timeout=4)
            if res.status_code == 200:
                data = res.json()
                datas = data.get("datas", [])
                if datas:
                    d = datas[0]
                    open_p = d.get("openPrice")
                    high_p = d.get("highPrice")
                    low_p = d.get("lowPrice")
                    price = d.get("closePrice")
                    rate = d.get("fluctuationsRatio")
                    if open_p:
                        return {
                            "open": format_num(open_p),
                            "high": format_num(high_p),
                            "low": format_num(low_p),
                            "price": format_num(price),
                            "rate": f"{float(rate):+.2f}%" if rate else None
                        }
        except Exception:
            pass

        # 방법 2: 네이버 모바일 integration API (totalInfos 파싱)
        try:
            url = f"https://m.stock.naver.com/api/stock/{symbol}/integration"
            res = requests.get(url, headers=headers, timeout=4)
            if res.status_code == 200:
                d = res.json()
                total_infos = d.get("totalInfos", [])
                info_dict = {item.get("code"): item.get("value") for item in total_infos if isinstance(item, dict)}
                deal_trend = d.get("dealTrend", {})
                open_p = info_dict.get("openPrice") or deal_trend.get("openPrice")
                high_p = info_dict.get("highPrice") or deal_trend.get("highPrice")
                low_p = info_dict.get("lowPrice") or deal_trend.get("lowPrice")
                price = d.get("closePrice") or info_dict.get("closePrice")
                if open_p:
                    return {
                        "open": format_num(open_p),
                        "high": format_num(high_p),
                        "low": format_num(low_p),
                        "price": format_num(price),
                        "rate": None
                    }
        except Exception:
            pass

    else:
        # 미국 주식: 야후 파이낸스 차트 API
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200:
                chart = res.json()["chart"]["result"][0]
                meta = chart.get("meta", {})
                quote = chart.get("indicators", {}).get("quote", [{}])[0]

                price = meta.get("regularMarketPrice")
                prev_close = meta.get("chartPreviousClose")

                opens = [x for x in quote.get("open", []) if x is not None]
                highs = [x for x in quote.get("high", []) if x is not None]
                lows = [x for x in quote.get("low", []) if x is not None]

                open_p = opens[-1] if opens else meta.get("regularMarketOpen")
                high_p = highs[-1] if highs else meta.get("regularMarketDayHigh")
                low_p = lows[-1] if lows else meta.get("regularMarketDayLow")

                rate_str = None
                if price and prev_close:
                    rate_str = f"{((price - prev_close) / prev_close) * 100:+.2f}%"

                return {
                    "open": format_num(open_p, is_currency=True),
                    "high": format_num(high_p, is_currency=True),
                    "low": format_num(low_p, is_currency=True),
                    "price": format_num(price, is_currency=True),
                    "rate": rate_str
                }
        except Exception:
            pass

    return {}

class TossAPIClient:
    def __init__(self):
        self.client_id, self.client_secret = load_credentials()
        self.token = None
        self.token_expiry = 0

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def get_token(self) -> str:
        """토스증권 OAuth2 액세스 토큰 발급/갱신 (POST /oauth2/token)"""
        self.client_id, self.client_secret = load_credentials()
        if not self.is_configured():
            return None

        if self.token and time.time() < (self.token_expiry - 60):
            return self.token

        url = f"{BASE_URL}/oauth2/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        try:
            res = requests.post(url, data=payload, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                self.token = data.get("access_token")
                expires_in = data.get("expires_in", 86400)
                self.token_expiry = time.time() + expires_in
                return self.token
            else:
                return None
        except Exception:
            return None

    def get_quotes_batch(self, symbols: list) -> dict:
        """토스증권 시세 배치 조회"""
        token = self.get_token()
        if not token:
            return {}

        url = f"{BASE_URL}/api/v1/prices"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        params = {"symbols": ",".join(symbols)}

        results = {}
        try:
            res = requests.get(url, headers=headers, params=params, timeout=10)
            if res.status_code == 200:
                data = res.json()
                items = data if isinstance(data, list) else data.get("prices", data.get("items", []))
                if isinstance(items, list):
                    for it in items:
                        sym = it.get("symbol")
                        price = it.get("price") or it.get("currentPrice") or it.get("closePrice") or it.get("close")
                        open_p = it.get("open") or it.get("openPrice") or it.get("firstPrice")
                        high_p = it.get("high") or it.get("highPrice")
                        low_p = it.get("low") or it.get("lowPrice")
                        rate = it.get("rate") or it.get("changeRate") or it.get("fluctuationsRatio")

                        if sym:
                            results[sym] = {
                                "price": price,
                                "open": open_p,
                                "high": high_p,
                                "low": low_p,
                                "rate": rate,
                                "source": "Toss API",
                            }
        except Exception:
            pass

        return results

    def get_enriched_quote(self, symbol: str, is_kr: bool = False, batch_data: dict = None) -> dict:
        """토스 API 시세에 시가(Open), 고가(High), 저가(Low)를 결합"""
        toss_item = (batch_data or {}).get(symbol)
        ohlc = {}

        raw_price = None
        raw_rate = None
        raw_open = None
        raw_high = None
        raw_low = None

        if toss_item:
            raw_price = toss_item.get("price")
            raw_rate = toss_item.get("rate")
            raw_open = toss_item.get("open")
            raw_high = toss_item.get("high")
            raw_low = toss_item.get("low")

        # 시가나 고가/저가가 누락된 경우 즉시 보완 조회
        if not raw_open or str(raw_open).strip() == "-" or not raw_high or str(raw_high).strip() == "-":
            ohlc = fetch_ohlc_fallback(symbol, is_kr=is_kr)

        # 최종 값 결정
        final_price = format_num(raw_price, is_currency=not is_kr) if raw_price else (ohlc.get("price") or "-")
        final_open = format_num(raw_open, is_currency=not is_kr) if raw_open else (ohlc.get("open") or "-")
        final_high = format_num(raw_high, is_currency=not is_kr) if raw_high else (ohlc.get("high") or "-")
        final_low = format_num(raw_low, is_currency=not is_kr) if raw_low else (ohlc.get("low") or "-")

        final_rate = "-"
        if raw_rate is not None:
            try:
                final_rate = f"{float(raw_rate):+.2f}%"
            except Exception:
                final_rate = str(raw_rate)
        elif ohlc.get("rate"):
            final_rate = ohlc.get("rate")

        # 장중 추세 계산
        intraday_pct, trend = compute_intraday_trend(final_open, final_price)

        return {
            "symbol": symbol,
            "price": final_price,
            "open": final_open,
            "high": final_high,
            "low": final_low,
            "change_rate": final_rate,
            "intraday_change": intraday_pct,
            "trend": trend,
            "source": "Toss API + OHLC Engine",
        }
