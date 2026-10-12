import requests
import xml.etree.ElementTree as ET

def fetch_historical_closes(symbol: str, is_kr: bool = False, days: int = 250) -> list:
    """최근 N 영업일의 일봉 종가 리스트 수집"""
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    closes = []

    if is_kr:
        # 방법 1: 네이버 증권 250일 일봉 차트 XML API
        try:
            url = f"https://fchart.stock.naver.com/sise.nhn?symbol={symbol}&timeframe=day&count={days}&requestType=0"
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200:
                root = ET.fromstring(res.content)
                for item in root.findall(".//item"):
                    data_str = item.get("data", "")
                    parts = data_str.split("|")
                    if len(parts) >= 5:
                        c = float(parts[4])
                        closes.append(c)
                if len(closes) >= 10:
                    return closes
        except Exception:
            pass

        # 방법 2: 야후 파이낸스 (.KS / .KQ)
        for suffix in [".KS", ".KQ"]:
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}{suffix}?interval=1d&range=1y"
                res = requests.get(url, headers=headers, timeout=5)
                if res.status_code == 200:
                    quote = res.json()["chart"]["result"][0]["indicators"]["quote"][0]
                    c_list = [float(x) for x in quote.get("close", []) if x is not None]
                    if len(c_list) >= 10:
                        return c_list
            except Exception:
                pass

    else:
        # 미국 주식: 야후 파이낸스 1년 일봉
        try:
            clean_sym = symbol.replace(".", "-")
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{clean_sym}?interval=1d&range=1y"
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200:
                quote = res.json()["chart"]["result"][0]["indicators"]["quote"][0]
                c_list = [float(x) for x in quote.get("close", []) if x is not None]
                if len(c_list) >= 10:
                    return c_list
        except Exception:
            pass

    return closes

def calculate_mas(closes: list) -> dict:
    """10일, 20일, 50일, 100일, 200일 단순 이동평균선(SMA) 산출"""
    mas = {}
    periods = [10, 20, 50, 100, 200]
    for p in periods:
        if len(closes) >= p:
            mas[p] = sum(closes[-p:]) / p
        else:
            mas[p] = None
    return mas

def check_ma_touch_events(symbol: str, name: str, current_price, low_price, high_price, is_kr: bool = False) -> list:
    """
    당일 가격 범위(저가~고가)가 10, 20, 50, 100, 200일 이평선에 닿았거나 근접한 이벤트 탐색
    """
    try:
        c = float(str(current_price).replace(",", "").replace("$", "").replace("원", "").strip())
        l = float(str(low_price).replace(",", "").replace("$", "").replace("원", "").strip())
        h = float(str(high_price).replace(",", "").replace("$", "").replace("원", "").strip())
    except Exception:
        return []

    if c <= 0 or l <= 0 or h <= 0:
        return []

    closes = fetch_historical_closes(symbol, is_kr=is_kr, days=250)
    if not closes:
        return []

    mas = calculate_mas(closes)
    events = []

    for period, ma_val in mas.items():
        if not ma_val or ma_val <= 0:
            continue

        # 1. 당일 캔들(저가~고가)이 이평선을 직접 관통하거나 터치한 경우
        is_range_touch = (l <= ma_val <= h)
        # 2. 현재가가 이평선 기준 ±0.8% 이내 초근접한 경우
        diff_pct = ((c - ma_val) / ma_val) * 100
        is_close_proximity = abs(diff_pct) <= 0.8

        if is_range_touch or is_close_proximity:
            if c >= ma_val and l <= ma_val:
                action = f"{period}일선 하단 터치 후 지지 반등 (+{diff_pct:.2f}% 상회)"
                tag = "지지 반등"
            elif c <= ma_val and h >= ma_val:
                action = f"{period}일선 상단 터치 후 저항 반락 ({diff_pct:.2f}% 하회)"
                tag = "저항 반락"
            elif diff_pct >= 0:
                action = f"{period}일선 바로 위 안착 (이격 +{diff_pct:.2f}%)"
                tag = "이평선 지지권"
            else:
                action = f"{period}일선 바로 아래 근접 (이격 {diff_pct:.2f}%)"
                tag = "저항선 접근"

            currency = "원" if is_kr else "$"
            ma_str = f"{int(ma_val):,}{currency}" if is_kr else f"${ma_val:,.2f}"

            events.append({
                "period": period,
                "name": name,
                "symbol": symbol,
                "ma_val": ma_str,
                "action": action,
                "tag": tag,
                "diff_pct": diff_pct
            })

    return events
