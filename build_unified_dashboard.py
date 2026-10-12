import base64
import os
import json
import csv
import time
import datetime
import email.utils
import urllib.parse
import xml.etree.ElementTree as ET
import concurrent.futures
import requests

from sp100_list import SP100_COMPANIES

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAT_IMG_PATH = os.path.join(BASE_DIR, "assets", "cat_mascot.jpg")
if not os.path.exists(CAT_IMG_PATH) and os.path.exists("/Users/jinwoo_0610/Downloads/고양이.jpg"):
    import shutil
    shutil.copy2("/Users/jinwoo_0610/Downloads/고양이.jpg", CAT_IMG_PATH)

def get_cat_base64():
    if os.path.exists(CAT_IMG_PATH):
        try:
            with open(CAT_IMG_PATH, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception:
            pass
    return ""
CACHE_DIR = os.path.join(BASE_DIR, "data", "cache")
NEWS_CACHE_DIR = os.path.join(BASE_DIR, "data", "cache", "news")
os.makedirs(NEWS_CACHE_DIR, exist_ok=True)
OUTPUT_HTML = os.path.join(BASE_DIR, "reports", "unified_market_dashboard.html")
OUTPUT_INDEX_HTML = os.path.join(BASE_DIR, "index.html")
OUTPUT_JSON = os.path.join(BASE_DIR, "data", "unified_dashboard_data.json")

# 국내 반도체 핵심주 8개 (.KS: 코스피, .KQ: 코스닥 야후 티커 명시)
KR_EXTRA_STOCKS = [
    {"sym": "005930", "yahoo_sym": "005930.KS", "name": "삼성전자", "sector": "국내 반도체", "is_kr": True},
    {"sym": "000660", "yahoo_sym": "000660.KS", "name": "SK하이닉스", "sector": "국내 반도체", "is_kr": True},
    {"sym": "042700", "yahoo_sym": "042700.KS", "name": "한미반도체", "sector": "국내 반도체", "is_kr": True},
    {"sym": "058470", "yahoo_sym": "058470.KQ", "name": "리노공업", "sector": "국내 반도체", "is_kr": True},
    {"sym": "036930", "yahoo_sym": "036930.KQ", "name": "주성엔지니어링", "sector": "국내 반도체", "is_kr": True},
    {"sym": "131970", "yahoo_sym": "131970.KQ", "name": "두산테스나", "sector": "국내 반도체", "is_kr": True},
    {"sym": "240810", "yahoo_sym": "240810.KQ", "name": "원익IPS", "sector": "국내 반도체", "is_kr": True},
    {"sym": "403870", "yahoo_sym": "403870.KQ", "name": "HPSP", "sector": "국내 반도체", "is_kr": True},
]

# S&P 100 (102개) + 국내 반도체 (8개) = 총 110개 종목 유니버스
ALL_STOCKS = []
for c in SP100_COMPANIES:
    c_copy = dict(c)
    c_copy["is_kr"] = False
    c_copy["yahoo_sym"] = c["sym"].replace(".", "-")
    ALL_STOCKS.append(c_copy)
ALL_STOCKS.extend(KR_EXTRA_STOCKS)

def fetch_kr_daily_prices_naver(symbol: str, count: int = 2500) -> list:
    """네이버 금융 10년치 일봉 수집 (HTTP 프로토콜)"""
    url = f"http://fchart.stock.naver.com/sise.nhn?symbol={symbol}&timeframe=day&count={count}&requestType=0"
    headers = {"User-Agent": "Mozilla/5.0"}
    records = []
    try:
        res = requests.get(url, headers=headers, timeout=6)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            for item in root.findall(".//item"):
                parts = item.get("data", "").split("|")
                if len(parts) >= 5:
                    d_raw = parts[0]
                    dt_str = f"{d_raw[:4]}-{d_raw[4:6]}-{d_raw[6:8]}"
                    c_val = float(parts[4])
                    if c_val > 0:
                        records.append({"date": dt_str, "close": c_val})
    except Exception:
        pass
    return records

def load_or_fetch_prices(item: dict) -> list:
    sym = item["sym"]
    is_kr = item.get("is_kr", False)
    yahoo_sym = item.get("yahoo_sym", sym.replace(".", "-"))
    cache_file = os.path.join(CACHE_DIR, f"{sym}.json")

    # 1. 로컬 캐시 확인
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if len(data) >= 10:
                    return data
        except Exception:
            pass

    # 2. 신규 수집 (yfinance 우선)
    records = []
    try:
        import yfinance as yf
        hist = yf.Ticker(yahoo_sym).history(period="20y" if not is_kr else "10y")
        if not hist.empty:
            for idx, row in hist.iterrows():
                c = float(row.get("Close", 0))
                if c > 0:
                    records.append({"date": idx.strftime("%Y-%m-%d"), "close": c})
    except Exception:
        pass

    # 3. 국내 주식 yfinance 실패 시 네이버 fchart 백업
    if is_kr and (not records or len(records) < 10):
        records = fetch_kr_daily_prices_naver(sym, count=2500)

    # 4. 캐시 저장
    if records:
        os.makedirs(CACHE_DIR, exist_ok=True)
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(records, f, ensure_ascii=False)
        except Exception:
            pass

    return records

def calculate_sma(closes: list, period: int) -> list:
    smas = []
    for i in range(len(closes)):
        if i + 1 < period:
            smas.append(None)
        else:
            avg_val = sum(closes[i + 1 - period : i + 1]) / period
            smas.append(round(avg_val, 2))
    return smas

def compute_profile(daily_records, min_drop=-10.0, step=1):
    if not daily_records or len(daily_records) < 5:
        return None

    peak = daily_records[0]["close"]
    ath = peak
    ath_date = daily_records[0]["date"]
    cycles = []
    cur_cycle = None
    dates = []
    closes = []
    drawdowns = []

    for item in daily_records:
        p = item["close"]
        d = item["date"]

        if p > ath:
            ath = p
            ath_date = d

        if p >= peak:
            if cur_cycle and cur_cycle["trough_dd"] <= min_drop:
                cycles.append(cur_cycle)
            cur_cycle = None
            peak = p
            peak_date = d
            dd = 0.0
        else:
            dd = ((p - peak) / peak) * 100
            if cur_cycle is None:
                cur_cycle = {
                    "peak_date": peak_date,
                    "peak_price": round(peak, 2),
                    "trough_date": d,
                    "trough_price": round(p, 2),
                    "trough_dd": round(dd, 2)
                }
            else:
                if dd < cur_cycle["trough_dd"]:
                    cur_cycle["trough_dd"] = round(dd, 2)
                    cur_cycle["trough_date"] = d
                    cur_cycle["trough_price"] = round(p, 2)

        dates.append(d)
        closes.append(round(p, 2))
        drawdowns.append(round(dd, 2))

    if cur_cycle and cur_cycle["trough_dd"] <= min_drop:
        cycles.append(cur_cycle)

    troughs = [c["trough_dd"] for c in cycles]
    avg_mdd = round(sum(troughs) / len(troughs), 2) if troughs else 0.0
    worst_mdd = round(min(troughs), 2) if troughs else 0.0
    current_dd = drawdowns[-1]
    current_price = daily_records[-1]["close"]

    ma20 = calculate_sma(closes, 20)
    ma50 = calculate_sma(closes, 50)
    ma100 = calculate_sma(closes, 100)
    ma200 = calculate_sma(closes, 200)

    return {
        "current_price": round(current_price, 2),
        "ath_price": round(ath, 2),
        "ath_date": ath_date,
        "current_dd": current_dd,
        "avg_mdd": avg_mdd,
        "worst_mdd": worst_mdd,
        "cycle_count": len(cycles),
        "dates": dates[::step],
        "closes": closes[::step],
        "drawdowns": drawdowns[::step],
        "ma20": ma20[::step],
        "ma50": ma50[::step],
        "ma100": ma100[::step],
        "ma200": ma200[::step],
    }

def fetch_rss_articles(query: str, hl: str = "ko", gl: str = "KR") -> dict:
    """구글 뉴스 RSS 호출 및 날짜별 파싱"""
    encoded = urllib.parse.quote(query)
    ceid = "KR:ko" if hl == "ko" else "US:en"
    url = f"https://news.google.com/rss/search?q={encoded}&hl={hl}&gl={gl}&ceid={ceid}"
    headers = {"User-Agent": "Mozilla/5.0"}
    news_map = {}

    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            for item in root.findall(".//item")[:8]:
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                pub_str = item.findtext("pubDate", "")

                if title:
                    date_label = "최근 소식"
                    time_label = ""
                    if pub_str:
                        try:
                            dt = email.utils.parsedate_to_datetime(pub_str)
                            weekday_kr = ["월", "화", "수", "목", "금", "토", "일"][dt.weekday()]
                            date_label = f"{dt.month}월 {dt.day}일 ({weekday_kr})"
                            time_label = dt.strftime("%H:%M")
                        except Exception:
                            pass

                    if date_label not in news_map:
                        news_map[date_label] = []

                    news_map[date_label].append({
                        "title": title,
                        "link": link,
                        "time": time_label
                    })
    except Exception:
        pass

    return news_map

def fetch_weekly_news_by_date(stock_name: str, sym: str) -> dict:
    """한국어 뉴스 우선 수집 후, 없으면 글로벌 영문 뉴스 자동 보완 (영구 로컬 캐싱 적용)"""
    cache_path = os.path.join(NEWS_CACHE_DIR, f"{sym}.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
                if cached and len(cached) > 0:
                    return cached
        except Exception:
            pass

    clean_name = stock_name.split("(")[0].strip()
    query_kr = f"{clean_name} OR {sym} 주가 OR 실적 OR 전망"
    news_map = fetch_rss_articles(query_kr, hl="ko", gl="KR")

    # 한국어 기사가 없는 미국 비인기 종목은 글로벌 금융 영문 뉴스 자동 보완
    if not news_map and not sym.isdigit():
        query_en = f"{sym} stock OR earnings OR shares"
        news_map = fetch_rss_articles(query_en, hl="en-US", gl="US")

    if news_map:
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(news_map, f, ensure_ascii=False)
        except Exception:
            pass

    return news_map

def process_single_stock(item, d10_cutoff, d20_cutoff):
    sym = item["sym"]
    name = item["name"]
    sector = item["sector"]
    is_kr = item.get("is_kr", False)

    prices = load_or_fetch_prices(item)
    if not prices:
        return None

    rec_20y = [x for x in prices if x["date"] >= d20_cutoff] or prices
    rec_10y = [x for x in prices if x["date"] >= d10_cutoff] or prices

    p20 = compute_profile(rec_20y, min_drop=-10.0, step=2)
    p10 = compute_profile(rec_10y, min_drop=-10.0, step=1)

    if not p10 or not p20:
        return None

    news_by_date = fetch_weekly_news_by_date(name, sym)

    ratio_10 = round(abs(p10["current_dd"]) / abs(p10["avg_mdd"]) * 100, 1) if p10["avg_mdd"] else 0

    return {
        "sym": sym,
        "data": {
            "name": name,
            "sector": sector,
            "is_kr": is_kr,
            "currency": "원" if is_kr else "$",
            "p10": p10,
            "p20": p20,
            "news_timeline": news_by_date
        },
        "ratio_10": ratio_10,
        "current_dd": p10["current_dd"]
    }

def build_unified_system():
    print("==========================================")
    print(f"🚀 S&P 100 + 국내 반도체 ({len(ALL_STOCKS)}개 종목) 통합 대시보드 구축 (Method A 분할 아키텍처)")
    print("==========================================\n")

    now = datetime.datetime.now()
    d10_cutoff = (now - datetime.timedelta(days=365 * 10)).strftime("%Y-%m-%d")
    d20_cutoff = (now - datetime.timedelta(days=365 * 20)).strftime("%Y-%m-%d")

    stock_data_map = {}
    total = len(ALL_STOCKS)

    # 병렬 수집 (최대 6개 스레드)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        future_map = {
            executor.submit(process_single_stock, item, d10_cutoff, d20_cutoff): item
            for item in ALL_STOCKS
        }

        completed = 0
        for future in concurrent.futures.as_completed(future_map):
            completed += 1
            item = future_map[future]
            try:
                res = future.result()
                if res:
                    stock_data_map[res["sym"]] = res["data"]
                    print(f"[{completed:03d}/{total:03d}] ✓ {item['name']} ({item['sym']}) 분석 완료 (현재낙폭 {res['current_dd']}%, 도달률 {res['ratio_10']}%)")
                else:
                    print(f"[{completed:03d}/{total:03d}] ⚠️ {item['name']} ({item['sym']}) 데이터 부족 건너뜀")
            except Exception as e:
                print(f"[{completed:03d}/{total:03d}] ⚠️ {item['sym']} 오류: {e}")

    data_dir = os.path.join(BASE_DIR, "data")
    stocks_dir = os.path.join(data_dir, "stocks")
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(stocks_dir, exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, "reports"), exist_ok=True)

    # 1. 원본 통합 데이터 저장 (호환성 백업)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(stock_data_map, f, ensure_ascii=False)

    # 2. Method A: 종목별 개별 JSON 분할 및 경량 요약본(Summary) 생성
    summary_list = []
    for sym, d in stock_data_map.items():
        # 종목별 개별 상세 파일 저장 (On-Demand Fetching 대상)
        stock_path = os.path.join(stocks_dir, f"{sym}.json")
        with open(stock_path, "w", encoding="utf-8") as sf:
            json.dump(d, sf, ensure_ascii=False)

        p10 = d.get("p10", {})
        p20 = d.get("p20", {})
        r10 = round(abs(p10.get("current_dd", 0)) / abs(p10.get("avg_mdd", 1)) * 100, 1) if p10.get("avg_mdd") else 0
        r20 = round(abs(p20.get("current_dd", 0)) / abs(p20.get("avg_mdd", 1)) * 100, 1) if p20.get("avg_mdd") else 0

        summary_item = {
            "sym": sym,
            "name": d.get("name", sym),
            "sector": d.get("sector", ""),
            "is_kr": d.get("is_kr", False),
            "currency": d.get("currency", "$"),
            "p10": {
                "current_price": p10.get("current_price", 0),
                "current_dd": p10.get("current_dd", 0),
                "avg_mdd": p10.get("avg_mdd", 0),
                "worst_mdd": p10.get("worst_mdd", 0),
                "ratio": r10
            },
            "p20": {
                "current_price": p20.get("current_price", 0),
                "current_dd": p20.get("current_dd", 0),
                "avg_mdd": p20.get("avg_mdd", 0),
                "worst_mdd": p20.get("worst_mdd", 0),
                "ratio": r20
            }
        }
        summary_list.append(summary_item)

    summary_path = os.path.join(data_dir, "stock_summary.json")
    with open(summary_path, "w", encoding="utf-8") as sf:
        json.dump(summary_list, sf, ensure_ascii=False)

    print(f"\n✓ Method A: {len(stock_data_map)}개 종목 분할 JSON 생성 완료 (저장 경로: data/stocks/)")
    print(f"✓ 경량 요약본 생성 완료: {summary_path} ({round(os.path.getsize(summary_path)/1024, 1)} KB)")

    render_unified_html(summary_list)

def render_unified_html(summary_list):
    cat_b64 = get_cat_base64()
    summary_json_str = json.dumps(summary_list, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>증시 심층 트래커 & MDD 낙폭 분석 통합 대시보드</title>
    <!-- Chart.js 및 줌/팬 플러그인 CDN -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/hammerjs@2.0.8/hammer.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-zoom@2.0.1/dist/chartjs-plugin-zoom.min.js"></script>
    <style>
        :root {{
            --bg-body: #090D14;
            --bg-sidebar: #101520;
            --bg-card: #151C2A;
            --bg-item: #171F2F;
            --bg-item-active: #1E293B;
            --border: #232D42;
            --text-main: #F1F5F9;
            --text-muted: #8E9BAE;
            --blue: #38BDF8;
            --gold: #F59E0B;
            --purple: #A78BFA;
            --red: #EF4444;
            --green: #22C55E;
            --orange: #FB923C;
        }}

        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Apple SD Gothic Neo", sans-serif; }}
        body {{ background-color: var(--bg-body); color: var(--text-main); height: 100vh; overflow: hidden; display: flex; }}

        /* 왼쪽 사이드바 */
        .sidebar {{
            width: 360px;
            background: var(--bg-sidebar);
            border-right: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            flex-shrink: 0;
            height: 100%;
        }}

        .sidebar-header {{
            padding: 16px 16px 12px 16px;
            border-bottom: 1px solid var(--border);
        }}

        .sidebar-header h2 {{
            font-size: 16px;
            font-weight: 800;
            color: #FFF;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .total-badge {{
            font-size: 11px;
            background: rgba(56, 189, 248, 0.15);
            color: var(--blue);
            padding: 2px 8px;
            border-radius: 10px;
        }}

        .search-box {{ margin-top: 10px; }}
        .search-input {{
            width: 100%;
            background: var(--bg-body);
            border: 1px solid var(--border);
            color: #FFF;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 13px;
            outline: none;
            transition: border-color 0.2s;
        }}
        .search-input:focus {{ border-color: var(--blue); }}

        .filter-chips {{
            display: flex;
            gap: 6px;
            padding: 10px 14px;
            border-bottom: 1px solid var(--border);
            overflow-x: auto;
            flex-shrink: 0;
        }}
        .chip-btn {{
            background: var(--bg-item);
            border: 1px solid var(--border);
            color: var(--text-muted);
            padding: 4px 10px;
            border-radius: 14px;
            font-size: 11px;
            font-weight: 700;
            cursor: pointer;
            white-space: nowrap;
        }}
        .chip-btn.active {{
            background: rgba(56, 189, 248, 0.15);
            border-color: var(--blue);
            color: var(--blue);
        }}

        .stock-list {{ flex: 1; overflow-y: auto; padding: 8px; }}
        .stock-item {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 9px 12px;
            border-radius: 8px;
            cursor: pointer;
            border: 1px solid transparent;
            margin-bottom: 4px;
            transition: all 0.15s;
        }}
        .stock-item:hover {{ background: var(--bg-item); }}
        .stock-item.active {{ background: var(--bg-item-active); border-color: var(--blue); }}

        .item-left {{ display: flex; align-items: center; gap: 10px; min-width: 0; }}
        .item-logo {{
            width: 28px;
            height: 28px;
            border-radius: 6px;
            background: #FFF;
            padding: 2px;
            object-fit: contain;
            flex-shrink: 0;
        }}
        .text-avatar {{
            width: 28px;
            height: 28px;
            border-radius: 6px;
            background: #1E293B;
            color: var(--blue);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 10px;
            font-weight: 800;
            border: 1px solid var(--border);
            flex-shrink: 0;
        }}
        .big-text-avatar {{
            width: 44px;
            height: 44px;
            border-radius: 8px;
            background: #1E293B;
            color: var(--blue);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            font-weight: 800;
            border: 1px solid var(--border);
            flex-shrink: 0;
        }}

        .item-info {{ display: flex; flex-direction: column; min-width: 0; }}
        .item-ticker {{ font-weight: 800; font-size: 13px; color: #FFF; }}
        .item-name {{ font-size: 11px; color: var(--text-muted); max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}

        .item-right {{ text-align: right; display: flex; flex-direction: column; align-items: flex-end; gap: 3px; flex-shrink: 0; }}
        .badge-dd {{ font-size: 11px; font-weight: 700; padding: 2px 6px; border-radius: 4px; background: rgba(239, 68, 68, 0.15); color: var(--red); }}
        .ratio-bar-wrap {{ width: 60px; height: 4px; background: rgba(255,255,255,0.1); border-radius: 2px; overflow: hidden; }}
        .ratio-bar {{ height: 100%; }}

        /* 오른쪽 메인 뷰 */
        .main-content {{
            flex: 1;
            display: flex;
            flex-direction: column;
            height: 100%;
            overflow-y: auto;
            padding: 24px 30px;
        }}

        .main-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 18px;
            border-bottom: 1px solid var(--border);
            padding-bottom: 16px;
        }}
        .current-stock-meta {{ display: flex; align-items: center; gap: 14px; }}
        .logo-container {{ display: flex; align-items: center; }}
        .big-logo {{ width: 44px; height: 44px; border-radius: 8px; background: #FFF; padding: 4px; object-fit: contain; }}
        .stock-titles h1 {{ font-size: 22px; font-weight: 800; color: #FFF; }}
        .stock-titles span {{ font-size: 13px; color: var(--text-muted); }}

        /* 상단 컨트롤러 (차트 형태 변경 & 기간 전환) */
        .controls-group {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
        .btn-group {{
            display: flex;
            background: #151C2A;
            padding: 3px;
            border-radius: 8px;
            border: 1px solid var(--border);
        }}
        .btn-toggle {{
            background: transparent;
            border: none;
            color: var(--text-muted);
            padding: 6px 13px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .btn-toggle.active {{ background: #0284C7; color: #FFF; }}

        /* 바닥권 / 패닉 알림 배너 (고양이 짤 연동) */
        .cat-alert-banner {{
            display: none;
            align-items: center;
            gap: 16px;
            background: linear-gradient(90deg, rgba(239, 68, 68, 0.22), rgba(245, 158, 11, 0.1));
            border: 1px solid rgba(239, 68, 68, 0.6);
            border-radius: 12px;
            padding: 12px 18px;
            margin-bottom: 20px;
            animation: fadeIn 0.25s ease-in-out;
        }}
        .cat-alert-img {{
            width: 52px;
            height: 52px;
            border-radius: 10px;
            object-fit: cover;
            border: 2px solid rgba(239, 68, 68, 0.6);
            box-shadow: 0 0 10px rgba(239, 68, 68, 0.35);
            flex-shrink: 0;
        }}
        .cat-alert-content {{ display: flex; flex-direction: column; }}
        .cat-alert-title {{ font-size: 14px; font-weight: 800; color: #F87171; display: flex; align-items: center; gap: 6px; }}
        .cat-alert-desc {{ font-size: 12px; color: var(--text-main); margin-top: 3px; line-height: 1.4; }}

        /* 4대 지표 카드 */
        .stats-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 20px; }}
        .stat-card {{ background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px; padding: 16px; }}
        .stat-label {{ font-size: 11px; color: var(--text-muted); font-weight: 600; text-transform: uppercase; }}
        .stat-val {{ font-size: 22px; font-weight: 800; margin-top: 4px; }}
        .stat-desc {{ font-size: 11px; color: var(--text-muted); margin-top: 4px; }}

        /* 차트 박스 */
        .chart-box {{ background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; padding: 20px; margin-bottom: 24px; position: relative; }}
        .chart-canvas-wrapper {{
            position: relative;
            width: 100%;
            height: 380px;
            max-height: 380px;
            overflow: hidden;
        }}
        .chart-canvas-wrapper canvas {{
            max-height: 380px !important;
            height: 380px !important;
        }}
        .chart-top {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
            flex-wrap: wrap;
            gap: 10px;
        }}
        .chart-title {{ font-size: 15px; font-weight: 700; }}

        /* 차트 확대/축소 툴바 */
        .zoom-toolbar {{
            display: flex;
            align-items: center;
            gap: 6px;
            background: #151C2A;
            padding: 3px 8px;
            border-radius: 8px;
            border: 1px solid var(--border);
        }}
        .zoom-label {{ font-size: 11px; color: var(--text-muted); font-weight: 700; margin-right: 4px; }}
        .zoom-btn {{
            background: #1E2738;
            border: 1px solid rgba(255,255,255,0.08);
            color: var(--text-main);
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s;
        }}
        .zoom-btn:hover {{ background: #0284C7; color: #FFF; }}
        .zoom-btn.active {{ background: #0284C7; color: #FFF; }}
        .btn-reset-zoom {{
            background: rgba(239, 68, 68, 0.2);
            border-color: rgba(239, 68, 68, 0.4);
            color: #F87171;
        }}
        .btn-reset-zoom:hover {{ background: #EF4444; color: #FFF; }}

        .legend-box {{ display: flex; gap: 14px; font-size: 11px; color: var(--text-muted); flex-wrap: wrap; }}
        .legend-item {{ display: flex; align-items: center; gap: 6px; }}
        .line-swatch {{ width: 14px; height: 3px; border-radius: 2px; }}

        /* 하단 일주일 뉴스 타임라인 섹션 */
        .news-timeline-section {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 30px;
        }}
        .timeline-header {{
            font-size: 15px;
            font-weight: 800;
            color: #FFF;
            margin-bottom: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
            border-bottom: 1px solid rgba(35, 45, 66, 0.6);
            padding-bottom: 10px;
        }}

        .timeline-container {{ display: flex; flex-direction: column; gap: 12px; }}
        .day-group {{
            background: rgba(23, 31, 47, 0.6);
            border-radius: 8px;
            border: 1px solid rgba(35, 45, 66, 0.8);
            padding: 12px 16px;
        }}
        .day-label {{
            font-size: 12px;
            font-weight: 800;
            color: var(--blue);
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .news-item {{
            margin-bottom: 6px;
            padding-left: 8px;
            border-left: 2px solid rgba(56, 189, 248, 0.4);
            display: flex;
            align-items: baseline;
            gap: 8px;
        }}
        .news-item:last-child {{ margin-bottom: 0; }}
        .news-time {{ font-size: 11px; color: var(--text-muted); font-weight: 600; min-width: 40px; }}
        .news-link {{
            color: var(--text-main);
            text-decoration: none;
            font-size: 12px;
            line-height: 1.4;
            transition: color 0.15s;
        }}
        .news-link:hover {{ color: var(--blue); text-decoration: underline; }}
        .empty-news {{ color: var(--text-muted); font-size: 12px; padding: 10px 0; }}
    </style>
</head>
<body>

<!-- 왼쪽 사이드바 -->
<div class="sidebar">
    <div class="sidebar-header">
        <h2>
            <span>📊 종목 탐색 & 랭킹</span>
            <span class="total-badge" id="totalBadge">0개</span>
        </h2>
        <div class="search-box">
            <input type="text" id="searchInput" class="search-input" placeholder="티커 또는 기업명 검색 (예: NVDA, 삼성전자)..." oninput="filterStocks()">
        </div>
    </div>
    <div class="filter-chips">
        <button class="chip-btn active" onclick="setFilter('ALL')">전체 (<span id="cntAll">0</span>)</button>
        <button class="chip-btn" onclick="setFilter('BOTTOM')">🚨 바닥권 (<span id="cntBottom">0</span>)</button>
        <button class="chip-btn" onclick="setFilter('CORRECT')">⚠️ 조정권 (<span id="cntCorrect">0</span>)</button>
        <button class="chip-btn" onclick="setFilter('SAFE')">🟢 정상 (<span id="cntSafe">0</span>)</button>
    </div>
    <div class="stock-list" id="stockList"></div>
</div>

<!-- 오른쪽 메인 뷰 -->
<div class="main-content">
    <div class="main-header">
        <div class="current-stock-meta">
            <div class="logo-container" id="mainLogoContainer"></div>
            <div class="stock-titles">
                <h1 id="mainTitle">-</h1>
                <span id="mainMeta">-</span>
            </div>
        </div>
        <div class="controls-group">
            <!-- 차트 형태 변경 토글 (MDD 낙폭 차트 vs 일반 주가/이평선) -->
            <div class="btn-group">
                <button class="btn-toggle active" id="btnChartMDD" onclick="setChartType('MDD')">📉 MDD 낙폭 차트</button>
                <button class="btn-toggle" id="btnChartPrice" onclick="setChartType('PRICE')">📈 일반 주가 & 이평선</button>
            </div>
            <!-- 기간 전환 토글 (10년 vs 20년) -->
            <div class="btn-group">
                <button class="btn-toggle active" id="btn10y" onclick="setPeriod('p10')">10년</button>
                <button class="btn-toggle" id="btn20y" onclick="setPeriod('p20')">20년</button>
            </div>
        </div>
    </div>

    <!-- 바닥권 / 패닉 알림 배너 (고양이 짤 연동 - MDD 바닥권 종목에만 조건부 노출) -->
    <div id="catAlertBanner" class="cat-alert-banner">
        <img src="data:image/jpeg;base64,{cat_b64}" class="cat-alert-img" alt="Panic Cat">
        <div class="cat-alert-content">
            <div class="cat-alert-title" id="catAlertTitle">🙀 으아악! 역사적 평균 MDD 바닥권 도달!</div>
            <div class="cat-alert-desc" id="catAlertDesc">현재 고점 대비 낙폭이 과거 평균 MDD 수준에 도달하여 패닉 매수 관점을 점검할 구간입니다.</div>
        </div>
    </div>

    <!-- 4대 핵심 지표 카드 -->
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-label">현재 고점 대비 낙폭</div>
            <div class="stat-val" id="statCurDD" style="color: var(--blue);">-</div>
            <div class="stat-desc" id="statPrice">현재가: -</div>
        </div>
        <div class="stat-card">
            <div class="stat-label" id="labelAvg">선택 기간 고유 평균 MDD</div>
            <div class="stat-val" id="statAvgMDD" style="color: var(--gold);">-</div>
            <div class="stat-desc" id="statAvgDesc">과거 주요 하락 사이클 바닥 평균</div>
        </div>
        <div class="stat-card">
            <div class="stat-label" id="labelWorst">선택 기간 역사적 최대 MDD</div>
            <div class="stat-val" id="statWorstMDD" style="color: var(--purple);">-</div>
            <div class="stat-desc">해당 기간 최악의 폭락 바닥</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">평균 바닥 도달률</div>
            <div class="stat-val" id="statRatio">-</div>
            <div class="stat-desc" id="statStatus">상태 진단</div>
        </div>
    </div>

    <!-- 차트 박스 -->
    <div class="chart-box">
        <div class="chart-top">
            <div>
                <span class="chart-title" id="chartTitle">Chart View</span>
            </div>
            
            <!-- 차트 확대/축소 및 줌 툴바 -->
            <div class="zoom-toolbar">
                <span class="zoom-label">🔍 차트 확대:</span>
                <button class="zoom-btn" onclick="zoomPreset('3M')">3개월</button>
                <button class="zoom-btn" onclick="zoomPreset('6M')">6개월</button>
                <button class="zoom-btn" onclick="zoomPreset('1Y')">1년</button>
                <button class="zoom-btn" onclick="zoomPreset('3Y')">3년</button>
                <button class="zoom-btn active" id="btnZoomAll" onclick="zoomPreset('ALL')">전체</button>
                <button class="zoom-btn btn-reset-zoom" onclick="resetChartZoom()">줌 리셋</button>
            </div>

            <div class="legend-box" id="legendBox"></div>
        </div>
        <div class="chart-canvas-wrapper">
            <canvas id="mainCanvas"></canvas>
        </div>
    </div>

    <!-- 하단 일주일 뉴스 타임라인 섹션 -->
    <div class="news-timeline-section">
        <div class="timeline-header">
            <span>📰 <span id="newsStockName">-</span> 최근 일주일간 주요 소식 및 뉴스 타임라인</span>
        </div>
        <div class="timeline-container" id="newsTimelineContainer"></div>
    </div>
</div>

<script>
    // Method A: 초경량 요약본 인메모리 탑재 (초기 로딩 0.05초)
    const summaryList = {summary_json_str};
    const summaryMap = {{}};
    summaryList.forEach(item => {{ summaryMap[item.sym] = item; }});

    let activeSym = "NVDA";
    let activePeriod = "p10";
    let activeChartType = "MDD";
    let currentFilter = "ALL";
    let chartInstance = null;
    const stockCache = {{}}; // 개별 종목 상세 데이터 비동기 캐시

    function renderLogo(sym, is_kr, isBig) {{
        const cls = isBig ? "big-logo" : "item-logo";
        const avatarCls = isBig ? "big-text-avatar" : "text-avatar";
        const shortTxt = sym.replace(".KS", "").replace(".KQ", "").slice(0, 3);

        if (is_kr) {{
            return `<img class="${{cls}}" src="https://ssl.pstatic.net/imgfinance/chart/mobile/mini/${{sym}}_small.png" onerror="this.outerHTML='<div class=\'${{avatarCls}}\'>${{shortTxt}}</div>'">`;
        }}
        const cleanSym = sym.replace("-B", ".B");
        return `<img class="${{cls}}" src="https://assets.parqet.com/logos/symbol/${{cleanSym}}?format=png" onerror="this.outerHTML='<div class=\'${{avatarCls}}\'>${{shortTxt}}</div>'">`;
    }}

    function updateCounts() {{
        let all = 0, bottom = 0, correct = 0, safe = 0;
        summaryList.forEach(item => {{
            all++;
            const p = item[activePeriod] || {{ ratio: 0 }};
            const ratio = p.ratio;
            if (ratio >= 90) bottom++;
            else if (ratio >= 60) correct++;
            else safe++;
        }});
        document.getElementById("cntAll").innerText = all;
        document.getElementById("cntBottom").innerText = bottom;
        document.getElementById("cntCorrect").innerText = correct;
        document.getElementById("cntSafe").innerText = safe;
        document.getElementById("totalBadge").innerText = all + "개 종목";
    }}

    function renderSidebar() {{
        const listEl = document.getElementById("stockList");
        listEl.innerHTML = "";
        const query = document.getElementById("searchInput").value.trim().toLowerCase();

        const sortedList = [...summaryList].sort((a, b) => {{
            const pA = a[activePeriod] || {{ ratio: 0 }};
            const pB = b[activePeriod] || {{ ratio: 0 }};
            return pB.ratio - pA.ratio;
        }});

        sortedList.forEach(item => {{
            const sym = item.sym;
            const p = item[activePeriod] || {{ current_dd: 0, avg_mdd: 0, ratio: 0 }};
            const ratio = p.ratio;

            if (query && !sym.toLowerCase().includes(query) && !item.name.toLowerCase().includes(query)) return;
            if (currentFilter === "BOTTOM" && ratio < 90) return;
            if (currentFilter === "CORRECT" && (ratio < 60 || ratio >= 90)) return;
            if (currentFilter === "SAFE" && ratio >= 60) return;

            const div = document.createElement("div");
            div.className = `stock-item ${{sym === activeSym ? "active" : ""}}`;
            div.onclick = () => selectStock(sym);

            const barWidth = Math.min(ratio, 100);
            const barColor = ratio >= 90 ? "#22C55E" : (ratio >= 60 ? "#F59E0B" : "#38BDF8");

            div.innerHTML = `
                <div class="item-left">
                    ${{renderLogo(sym, item.is_kr, false)}}
                    <div class="item-info">
                        <span class="item-ticker">${{sym}}</span>
                        <span class="item-name">${{item.name}}</span>
                    </div>
                </div>
                <div class="item-right">
                    <span class="badge-dd">${{p.current_dd}}%</span>
                    <div class="ratio-bar-wrap">
                        <div class="ratio-bar" style="width: ${{barWidth}}%; background: ${{barColor}};"></div>
                    </div>
                </div>
            `;
            listEl.appendChild(div);
        }});
    }}

    function setFilter(f) {{
        currentFilter = f;
        const chips = document.querySelectorAll(".chip-btn");
        chips.forEach(c => c.classList.remove("active"));
        event.target.classList.add("active");
        renderSidebar();
    }}

    function filterStocks() {{ renderSidebar(); }}

    function setPeriod(p) {{
        activePeriod = p;
        document.getElementById("btn10y").className = `btn-toggle ${{p === 'p10' ? 'active' : ''}}`;
        document.getElementById("btn20y").className = `btn-toggle ${{p === 'p20' ? 'active' : ''}}`;
        document.getElementById("labelAvg").innerText = p === 'p10' ? "10년 고유 평균 MDD" : "20년 고유 평균 MDD";
        document.getElementById("labelWorst").innerText = p === 'p10' ? "10년 역사적 최대 MDD" : "20년 역사적 최대 MDD";
        updateCounts();
        renderSidebar();
        if (stockCache[activeSym]) {{
            renderDetail(stockCache[activeSym]);
        }} else {{
            loadAndRenderDetail(activeSym);
        }}
    }}

    function setChartType(type) {{
        activeChartType = type;
        document.getElementById("btnChartMDD").className = `btn-toggle ${{type === 'MDD' ? 'active' : ''}}`;
        document.getElementById("btnChartPrice").className = `btn-toggle ${{type === 'PRICE' ? 'active' : ''}}`;
        if (stockCache[activeSym]) {{
            renderChart(stockCache[activeSym], stockCache[activeSym][activePeriod]);
        }}
    }}

    function selectStock(sym) {{
        activeSym = sym;
        renderSidebar();
        loadAndRenderDetail(sym);
    }}

    function loadAndRenderDetail(sym) {{
        if (stockCache[sym]) {{
            renderDetail(stockCache[sym]);
            return;
        }}

        const s = summaryMap[sym] || {{}};
        const curSym = s.currency || "$";
        const p = s[activePeriod] || {{ current_price: 0, current_dd: 0, avg_mdd: 0, worst_mdd: 0, ratio: 0 }};

        document.getElementById("mainLogoContainer").innerHTML = renderLogo(sym, s.is_kr, true);
        document.getElementById("mainTitle").innerText = `${{s.name || sym}} (${{sym}})`;
        document.getElementById("mainMeta").innerText = `${{s.sector || ""}} · 현재가: ${{curSym}}${{Number(p.current_price || 0).toLocaleString()}} (상세 데이터 불러오는 중...)`;

        document.getElementById("statCurDD").innerText = p.current_dd + "%";
        document.getElementById("statPrice").innerText = `현재가: ${{curSym}}${{Number(p.current_price || 0).toLocaleString()}}`;
        document.getElementById("statAvgMDD").innerText = p.avg_mdd + "%";
        document.getElementById("statAvgDesc").innerText = "과거 조정 평균 바닥선";
        document.getElementById("statWorstMDD").innerText = p.worst_mdd + "%";

        const rEl = document.getElementById("statRatio");
        rEl.innerText = p.ratio.toFixed(1) + "%";
        const stEl = document.getElementById("statStatus");
        const catBanner = document.getElementById("catAlertBanner");

        if (p.ratio >= 90) {{
            rEl.style.color = "#22C55E";
            stEl.innerText = "🚨 역사적 평균 바닥권 도달 (매수 관심)";
            if (catBanner) {{
                catBanner.style.display = "flex";
                document.getElementById("catAlertTitle").innerText = `🙀 으아악! 역사적 평균 MDD 바닥권 도달! (평균 MDD 도달률 ${{p.ratio.toFixed(1)}}%)`;
                document.getElementById("catAlertDesc").innerText = `현재 고점 대비 낙폭(${{p.current_dd}}%)이 과거 평균 MDD(${{p.avg_mdd}}%)의 90% 이상 도달했습니다. 역사적 분할 매수 찬스 구간인지 점검해보세요!`;
            }}
        }} else if (p.ratio >= 60) {{
            rEl.style.color = "#F59E0B";
            stEl.innerText = "⚠️ 평균 조정선 접근 중 (60%+ 진행)";
            if (catBanner) catBanner.style.display = "none";
        }} else {{
            rEl.style.color = "#38BDF8";
            stEl.innerText = "🟢 정상 / 상승 추세권";
            if (catBanner) catBanner.style.display = "none";
        }}

        document.getElementById("chartTitle").innerText = `⏳ ${{s.name || sym}} 상세 차트 로딩 중...`;

        // Method A: 개별 종목 JSON을 비동기로 로드
        fetch(`./data/stocks/${{sym}}.json`)
            .then(res => {{
                if (!res.ok) throw new Error("데이터를 불러오지 못했습니다 (HTTP " + res.status + ")");
                return res.json();
            }})
            .then(data => {{
                stockCache[sym] = data;
                if (activeSym === sym) {{
                    renderDetail(data);
                }}
            }})
            .catch(err => {{
                console.error("상세 데이터 로드 실패:", err);
                document.getElementById("chartTitle").innerText = `⚠️ ${{s.name || sym}} 차트 데이터를 불러올 수 없습니다.`;
            }});
    }}

    function renderDetail(stock) {{
        if (!stock) return;
        const p = stock[activePeriod];
        if (!p) return;

        document.getElementById("mainLogoContainer").innerHTML = renderLogo(activeSym, stock.is_kr, true);
        document.getElementById("mainTitle").innerText = `${{stock.name}} (${{activeSym}})`;
        const curSym = stock.currency;
        document.getElementById("mainMeta").innerText = `${{stock.sector}} · 현재가: ${{curSym}}${{p.current_price.toLocaleString()}} · 최고점(ATH): ${{curSym}}${{p.ath_price.toLocaleString()}} (${{p.ath_date}})`;

        document.getElementById("statCurDD").innerText = p.current_dd + "%";
        document.getElementById("statPrice").innerText = `현재가: ${{curSym}}${{p.current_price.toLocaleString()}}`;
        document.getElementById("statAvgMDD").innerText = p.avg_mdd + "%";
        document.getElementById("statAvgDesc").innerText = `과거 주요 ${{p.cycle_count}}회 조정 평균 바닥선`;
        document.getElementById("statWorstMDD").innerText = p.worst_mdd + "%";

        const ratio = (Math.abs(p.current_dd) / Math.abs(p.avg_mdd)) * 100;
        const rEl = document.getElementById("statRatio");
        rEl.innerText = ratio.toFixed(1) + "%";
        const stEl = document.getElementById("statStatus");

        const catBanner = document.getElementById("catAlertBanner");
        if (ratio >= 90) {{
            rEl.style.color = "#22C55E";
            stEl.innerText = "🚨 역사적 평균 바닥권 도달 (매수 관심)";
            if (catBanner) {{
                catBanner.style.display = "flex";
                document.getElementById("catAlertTitle").innerText = `🙀 으아악! 역사적 평균 MDD 바닥권 도달! (평균 MDD 도달률 ${{ratio.toFixed(1)}}%)`;
                document.getElementById("catAlertDesc").innerText = `현재 고점 대비 낙폭(${{p.current_dd}}%)이 과거 평균 MDD(${{p.avg_mdd}}%)의 90% 이상 도달했습니다. 역사적 분할 매수 찬스 구간인지 점검해보세요!`;
            }}
        }} else if (ratio >= 60) {{
            rEl.style.color = "#F59E0B";
            stEl.innerText = "⚠️ 평균 조정선 접근 중 (60%+ 진행)";
            if (catBanner) catBanner.style.display = "none";
        }} else {{
            rEl.style.color = "#38BDF8";
            stEl.innerText = "🟢 정상 / 상승 추세권";
            if (catBanner) catBanner.style.display = "none";
        }}

        renderChart(stock, p);
        renderNewsTimeline(stock);
    }}

    function renderChart(stock, p) {{
        const ctx = document.getElementById("mainCanvas").getContext("2d");
        const legendBox = document.getElementById("legendBox");
        if (chartInstance) chartInstance.destroy();

        const periodName = activePeriod === 'p10' ? "10년" : "20년";

        if (activeChartType === "MDD") {{
            document.getElementById("chartTitle").innerText = `${{stock.name}} [${{periodName}}] MDD 낙폭 차트 (마우스 휠/드래그 확대 지원)`;
            legendBox.innerHTML = `
                <div class="legend-item"><div class="line-swatch" style="background:#EF4444;"></div> 낙폭 곡선</div>
                <div class="legend-item"><div class="line-swatch" style="background:#F59E0B;"></div> 평균 MDD (${{p.avg_mdd}}%)</div>
                <div class="legend-item"><div class="line-swatch" style="background:#A78BFA;"></div> 최대 MDD (${{p.worst_mdd}}%)</div>
                <div class="legend-item"><div class="line-swatch" style="background:#38BDF8;"></div> 현재 낙폭 (${{p.current_dd}}%)</div>
            `;

            chartInstance = new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: p.dates,
                    datasets: [
                        {{
                            label: 'MDD 낙폭 (%)',
                            data: p.drawdowns,
                            borderColor: '#EF4444',
                            borderWidth: 1.5,
                            fill: true,
                            backgroundColor: 'rgba(239, 68, 68, 0.12)',
                            pointRadius: 0,
                            tension: 0.1
                        }},
                        {{
                            label: '평균 MDD',
                            data: Array(p.dates.length).fill(p.avg_mdd),
                            borderColor: '#F59E0B',
                            borderWidth: 1.5,
                            borderDash: [5, 4],
                            pointRadius: 0,
                            fill: false
                        }},
                        {{
                            label: '최대 MDD',
                            data: Array(p.dates.length).fill(p.worst_mdd),
                            borderColor: '#A78BFA',
                            borderWidth: 1.5,
                            borderDash: [2, 3],
                            pointRadius: 0,
                            fill: false
                        }},
                        {{
                            label: '현재 낙폭',
                            data: Array(p.dates.length).fill(p.current_dd),
                            borderColor: '#38BDF8',
                            borderWidth: 1.2,
                            borderDash: [4, 4],
                            pointRadius: 0,
                            fill: false
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {{ mode: 'index', intersect: false }},
                    plugins: {{
                        legend: {{ display: false }},
                        tooltip: {{
                            callbacks: {{
                                label: function(context) {{
                                    return context.dataset.label + ': ' + context.parsed.y + '%';
                                }}
                            }}
                        }},
                        zoom: {{
                            pan: {{ enabled: true, mode: 'x' }},
                            zoom: {{
                                wheel: {{ enabled: true }},
                                pinch: {{ enabled: true }},
                                mode: 'x'
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{
                            grid: {{ color: '#1E293B' }},
                            ticks: {{ color: '#8E9BAE', maxTicksLimit: 10 }}
                        }},
                        y: {{
                            grid: {{ color: '#1E293B' }},
                            max: 0,
                            ticks: {{
                                color: '#8E9BAE',
                                callback: function(val) {{ return val + '%'; }}
                            }}
                        }}
                    }}
                }}
            }});
        }} else {{
            const curSym = stock.currency;
            document.getElementById("chartTitle").innerText = `${{stock.name}} [${{periodName}}] 주가 및 주요 이동평균선 (마우스 휠/드래그 확대 지원)`;
            legendBox.innerHTML = `
                <div class="legend-item"><div class="line-swatch" style="background:#38BDF8;"></div> 종가 (${{curSym}})</div>
                <div class="legend-item"><div class="line-swatch" style="background:#22C55E;"></div> 20일선</div>
                <div class="legend-item"><div class="line-swatch" style="background:#F59E0B;"></div> 50일선</div>
                <div class="legend-item"><div class="line-swatch" style="background:#FB923C;"></div> 100일선</div>
                <div class="legend-item"><div class="line-swatch" style="background:#A78BFA;"></div> 200일선</div>
            `;

            chartInstance = new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: p.dates,
                    datasets: [
                        {{
                            label: '종가',
                            data: p.closes,
                            borderColor: '#38BDF8',
                            borderWidth: 1.8,
                            fill: true,
                            backgroundColor: 'rgba(56, 189, 248, 0.08)',
                            pointRadius: 0,
                            tension: 0.1
                        }},
                        {{
                            label: '20일선',
                            data: p.ma20,
                            borderColor: '#22C55E',
                            borderWidth: 1.2,
                            pointRadius: 0,
                            fill: false
                        }},
                        {{
                            label: '50일선',
                            data: p.ma50,
                            borderColor: '#F59E0B',
                            borderWidth: 1.2,
                            pointRadius: 0,
                            fill: false
                        }},
                        {{
                            label: '100일선',
                            data: p.ma100,
                            borderColor: '#FB923C',
                            borderWidth: 1.2,
                            pointRadius: 0,
                            fill: false
                        }},
                        {{
                            label: '200일선',
                            data: p.ma200,
                            borderColor: '#A78BFA',
                            borderWidth: 1.5,
                            pointRadius: 0,
                            fill: false
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {{ mode: 'index', intersect: false }},
                    plugins: {{
                        legend: {{ display: false }},
                        tooltip: {{
                            callbacks: {{
                                label: function(context) {{
                                    return context.dataset.label + ': ' + curSym + context.parsed.y.toLocaleString();
                                }}
                            }}
                        }},
                        zoom: {{
                            pan: {{ enabled: true, mode: 'x' }},
                            zoom: {{
                                wheel: {{ enabled: true }},
                                pinch: {{ enabled: true }},
                                mode: 'x'
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{
                            grid: {{ color: '#1E293B' }},
                            ticks: {{ color: '#8E9BAE', maxTicksLimit: 10 }}
                        }},
                        y: {{
                            grid: {{ color: '#1E293B' }},
                            ticks: {{
                                color: '#8E9BAE',
                                callback: function(val) {{ return curSym + val.toLocaleString(); }}
                            }}
                        }}
                    }}
                }}
            }});
        }}
    }}

    function zoomPreset(range) {{
        if (!chartInstance) return;
        const total = chartInstance.data.labels.length;
        if (total === 0) return;

        let count = total;
        if (range === '3M') count = Math.min(65, total);
        else if (range === '6M') count = Math.min(130, total);
        else if (range === '1Y') count = Math.min(252, total);
        else if (range === '3Y') count = Math.min(756, total);
        else if (range === 'ALL') count = total;

        const minIdx = total - count;
        const maxIdx = total - 1;

        chartInstance.resetZoom();
        chartInstance.options.scales.x.min = chartInstance.data.labels[minIdx];
        chartInstance.options.scales.x.max = chartInstance.data.labels[maxIdx];
        chartInstance.update();

        document.querySelectorAll('.zoom-btn').forEach(b => b.classList.remove('active'));
        if (event && event.target) event.target.classList.add('active');
    }}

    function resetChartZoom() {{
        if (chartInstance) {{
            chartInstance.resetZoom();
            delete chartInstance.options.scales.x.min;
            delete chartInstance.options.scales.x.max;
            chartInstance.update();
            document.querySelectorAll('.zoom-btn').forEach(b => b.classList.remove('active'));
            document.getElementById('btnZoomAll').classList.add('active');
        }}
    }}

    function renderNewsTimeline(stock) {{
        document.getElementById("newsStockName").innerText = stock.name;
        const container = document.getElementById("newsTimelineContainer");
        container.innerHTML = "";

        const timeline = stock.news_timeline;
        if (!timeline || Object.keys(timeline).length === 0) {{
            container.innerHTML = "<div class='empty-news'>최근 일주일 동안 집계된 주요 뉴스가 없습니다.</div>";
            return;
        }}

        Object.keys(timeline).forEach(day => {{
            const items = timeline[day];
            const dayBox = document.createElement("div");
            dayBox.className = "day-group";

            let itemsHtml = "";
            items.forEach(n => {{
                itemsHtml += `
                    <div class="news-item">
                        <span class="news-time">${{n.time || ""}}</span>
                        <a class="news-link" href="${{n.link}}" target="_blank" rel="noopener noreferrer">${{n.title}}</a>
                    </div>
                `;
            }});

            dayBox.innerHTML = `
                <div class="day-label">
                    <span>📅</span> ${{day}}
                </div>
                ${{itemsHtml}}
            `;
            container.appendChild(dayBox);
        }});
    }}

    // 초기 실행
    updateCounts();
    renderSidebar();
    selectStock("NVDA");
</script>
</body>
</html>
"""

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    with open(OUTPUT_INDEX_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n==========================================")
    print(f"✅ Method A 대시보드 경량 HTML 생성 완료:")
    print(f" - {OUTPUT_HTML} ({round(os.path.getsize(OUTPUT_HTML)/1024, 1)} KB)")
    print(f" - {OUTPUT_INDEX_HTML} ({round(os.path.getsize(OUTPUT_INDEX_HTML)/1024, 1)} KB)")
    print(f"==========================================")

if __name__ == "__main__":
    build_unified_system()
