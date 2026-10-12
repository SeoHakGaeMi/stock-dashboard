import os
import datetime
from config import US_INDICES, US_STOCKS, US_SECTOR_LEADERS, KR_LARGE_SEMI, KR_SOBUJANG
from toss_api import TossAPIClient
from news_scraper import get_all_sector_news, fetch_stock_specific_news
from technical import check_ma_touch_events

def build_markdown_table(headers: list, rows: list) -> str:
    """마크다운 테이블 문자열 생성"""
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(val)))

    header_line = "| " + " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers)) + " |"
    sep_line = "| " + " | ".join("-" * col_widths[i] for i in range(len(headers))) + " |"
    data_lines = []
    for row in rows:
        line = "| " + " | ".join(str(val).ljust(col_widths[i]) for i, val in enumerate(row)) + " |"
        data_lines.append(line)

    return "\n".join([header_line, sep_line] + data_lines)

def analyze_intraday_dynamics(all_records: list) -> dict:
    """장초반(시가) 대비 장막판(종가/현재가)의 수급 흐름 심층 분류"""
    strong_finish = []   # 장중 매수세 유입 (양봉)
    faded_finish = []    # 장중 차익실현 (음봉/윗꼬리)
    top_gainers = []     # 전일비 급등주 (+2.0% 이상)
    top_losers = []      # 전일비 하락주 (-2.0% 이하)

    for r in all_records:
        name = r["name"]
        change_rate_str = r.get("change_rate", "0%").replace("%", "").replace("+", "").strip()
        intraday_str = r.get("intraday_change", "0%").replace("%", "").replace("+", "").strip()

        try:
            chg = float(change_rate_str)
            intra = float(intraday_str)
            if intra >= 0.5:
                strong_finish.append(f"**{name}** (장중 {intra:+.2f}%, 최종 {chg:+.2f}%)")
            elif intra <= -0.5:
                faded_finish.append(f"**{name}** (장중 {intra:+.2f}%, 최종 {chg:+.2f}%)")

            if chg >= 2.0:
                top_gainers.append({"name": name, "chg": chg, "intra": intra, "rec": r})
            elif chg <= -2.0:
                top_losers.append({"name": name, "chg": chg, "intra": intra, "rec": r})
        except Exception:
            pass

    # 정렬
    top_gainers.sort(key=lambda x: x["chg"], reverse=True)
    top_losers.sort(key=lambda x: x["chg"])

    return {
        "strong": strong_finish,
        "faded": faded_finish,
        "gainers": [f"**{x['name']}** ({x['chg']:+.2f}%)" for x in top_gainers],
        "losers": [f"**{x['name']}** ({x['chg']:+.2f}%)" for x in top_losers],
        "raw_gainers": top_gainers,
        "raw_losers": top_losers,
    }

def run_market_tracker():
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")

    client = TossAPIClient()
    api_status = "토스증권 Open API + 정밀 OHLC 연동" if client.is_configured() else "공개 금융 데이터(Fallback)"

    print(f"\n==========================================")
    print(f"📊 S&P 500 전 섹터 & 반도체 심층 브리핑 생성 시작 ({now_str})")
    print(f"연동 상태: {api_status}")
    print(f"==========================================\n")

    all_stock_records = []

    # 1. 미국 지수 및 ETF
    print(f"▶ 1/6. 미국 주요 지수 및 ETF 시세 수집 중... ({len(US_INDICES)}개 종목)")
    us_indices_symbols = [item["symbol"] for item in US_INDICES]
    us_indices_batch = client.get_quotes_batch(us_indices_symbols)
    us_indices_table = []
    for item in US_INDICES:
        sym = item["symbol"]
        q = client.get_enriched_quote(sym, is_kr=False, batch_data=us_indices_batch)
        q["name"] = item["name"]
        q["is_kr"] = False
        all_stock_records.append(q)
        us_indices_table.append([
            item["name"], sym, q["open"], q["price"], f"{q['low']} ~ {q['high']}",
            q["change_rate"], q["intraday_change"], q["trend"]
        ])

    # 2. 미국 빅테크 & 글로벌 반도체
    print(f"▶ 2/6. 미국 빅테크 & 글로벌 반도체 시세 수집 중... ({len(US_STOCKS)}개 종목)")
    us_stocks_symbols = [item["symbol"] for item in US_STOCKS]
    us_stocks_batch = client.get_quotes_batch(us_stocks_symbols)
    us_stocks_table = []
    for item in US_STOCKS:
        sym = item["symbol"]
        q = client.get_enriched_quote(sym, is_kr=False, batch_data=us_stocks_batch)
        q["name"] = item["name"]
        q["is_kr"] = False
        all_stock_records.append(q)
        us_stocks_table.append([
            item["name"], item.get("sub", "-"), sym, q["open"], q["price"],
            f"{q['low']} ~ {q['high']}", q["change_rate"], q["intraday_change"], q["trend"]
        ])

    # 3. S&P 500 가치주 & 주요 섹터 대장주
    print(f"▶ 3/6. S&P 500 섹터별 대장주(가치주·산업재·리츠 등) 수집 중... ({len(US_SECTOR_LEADERS)}개 종목)")
    us_sector_symbols = [item["symbol"] for item in US_SECTOR_LEADERS]
    us_sector_batch = client.get_quotes_batch(us_sector_symbols)
    us_sector_table = []
    for item in US_SECTOR_LEADERS:
        sym = item["symbol"]
        q = client.get_enriched_quote(sym, is_kr=False, batch_data=us_sector_batch)
        q["name"] = item["name"]
        q["is_kr"] = False
        all_stock_records.append(q)
        us_sector_table.append([
            item["name"], item["sector"], item.get("sub", "-"), sym, q["open"], q["price"],
            f"{q['low']} ~ {q['high']}", q["change_rate"], q["intraday_change"], q["trend"]
        ])

    # 4. 국내 대형 반도체
    print(f"▶ 4/6. 국내 대형 반도체 시세 수집 중... ({len(KR_LARGE_SEMI)}개 종목)")
    kr_large_symbols = [item["symbol"] for item in KR_LARGE_SEMI]
    kr_large_batch = client.get_quotes_batch(kr_large_symbols)
    kr_large_table = []
    for item in KR_LARGE_SEMI:
        sym = item["symbol"]
        q = client.get_enriched_quote(sym, is_kr=True, batch_data=kr_large_batch)
        q["name"] = item["name"]
        q["is_kr"] = True
        all_stock_records.append(q)
        kr_large_table.append([
            item["name"], item.get("sub", "-"), sym, q["open"], q["price"],
            f"{q['low']} ~ {q['high']}", q["change_rate"], q["intraday_change"], q["trend"]
        ])

    # 5. 국내 반도체 소부장
    print(f"▶ 5/6. 국내 반도체 소부장 및 디자인하우스 시세 수집 중... ({len(KR_SOBUJANG)}개 종목)")
    kr_sobujang_symbols = [item["symbol"] for item in KR_SOBUJANG]
    kr_sobujang_batch = client.get_quotes_batch(kr_sobujang_symbols)
    kr_sobujang_table = []
    for item in KR_SOBUJANG:
        sym = item["symbol"]
        q = client.get_enriched_quote(sym, is_kr=True, batch_data=kr_sobujang_batch)
        q["name"] = item["name"]
        q["is_kr"] = True
        all_stock_records.append(q)
        kr_sobujang_table.append([
            item["name"], item["category"], sym, q["open"], q["price"],
            f"{q['low']} ~ {q['high']}", q["change_rate"], q["intraday_change"], q["trend"]
        ])

    # 6. 이동평균선(10일, 20일, 50일, 100일, 200일) 터치 이벤트 탐색
    print("\n▶ 6/6. 주요 이동평균선(10, 20, 50, 100, 200일선) 변곡점 및 터치 분석 중...")
    ma_touch_events = []
    for r in all_stock_records:
        events = check_ma_touch_events(
            symbol=r["symbol"],
            name=r["name"],
            current_price=r["price"],
            low_price=r.get("low", r["price"]),
            high_price=r.get("high", r["price"]),
            is_kr=r.get("is_kr", False)
        )
        ma_touch_events.extend(events)

    # 뉴스 수집
    print("▶ 토스증권 실시간 뉴스 및 섹터별 헤드라인 수집 중...")
    news_dict = get_all_sector_news()

    # 장중 동적 흐름 분석 및 특이 종목 추출
    dynamics = analyze_intraday_dynamics(all_stock_records)

    # 특이 종목 맞춤형 뉴스 수집 (급등 상위 3개 + 급락 상위 3개)
    standout_movers = dynamics["raw_gainers"][:3] + dynamics["raw_losers"][:3]
    standout_news_dict = {}
    print(f"▶ 특이 종목 {len(standout_movers)}개 개별 맞춤 뉴스 수집 중...")
    for mover in standout_movers:
        s_name = mover["name"]
        s_news = fetch_stock_specific_news(s_name, max_items=2)
        standout_news_dict[s_name] = {
            "chg": mover["chg"],
            "intra": mover["intra"],
            "news": s_news
        }

    # 마크다운 리포트 생성
    os.makedirs("reports", exist_ok=True)
    report_path = f"reports/{date_str}_market_brief.md"

    md_content = []
    md_content.append(f"# 📈 S&P 500 전 섹터 & 반도체 심층 일일 브리핑 ({date_str})")
    md_content.append(f"- **생성 일시**: {now_str}")
    md_content.append(f"- **데이터 수집 출처**: {api_status}")
    md_content.append(f"- **모니터링 종목 수**: 총 {len(all_stock_records)}개 (미국 {len(US_INDICES)+len(US_STOCKS)+len(US_SECTOR_LEADERS)}개 / 국내 {len(KR_LARGE_SEMI)+len(KR_SOBUJANG)}개)")
    md_content.append("")

    # 핵심 요약 박스
    md_content.append("## 🔍 [핵심 요약] 장초반 대비 장막판 수급 흐름 및 모멘텀 분석")
    md_content.append("> **장중 흐름 해석**: 장초반 시가 대비 장막판으로 갈수록 주가가 강하게 매수되었는지(양봉/뒷심), 갭상승 후 차익실현 매물로 밀렸는지(윗꼬리/차익)를 분석한 결과입니다.")
    md_content.append("")
    if dynamics["strong"]:
        md_content.append(f"- **🔥 장중 매수세 집중 (장초반 대비 뒷심 발휘 종목)**: {', '.join(dynamics['strong'][:8])}")
    if dynamics["faded"]:
        md_content.append(f"- **⚠️ 장중 차익실현 출회 (장초반 대비 반락/윗꼬리 종목)**: {', '.join(dynamics['faded'][:8])}")
    if dynamics["gainers"]:
        md_content.append(f"- **🚀 당일 섹터 주도 급등주 (+2.0% 이상)**: {', '.join(dynamics['gainers'][:8])}")
    if dynamics["losers"]:
        md_content.append(f"- **📉 당일 섹터 조정 하락주 (-2.0% 이하)**: {', '.join(dynamics['losers'][:8])}")
    md_content.append("")

    # [신규] 특이 종목(급등/급락주) 개별 원인 뉴스 섹션
    if standout_news_dict:
        md_content.append("## 🚨 [특이 종목 분석] 당일 급등·급락 종목과 핵심 관련 뉴스")
        md_content.append("> 당일 시장 대비 크게 튀었거나(-2.0% 이하, +2.0% 이상) 장중 변동폭이 컸던 종목들의 개별 이슈를 추적한 결과입니다.")
        md_content.append("")
        for s_name, s_info in standout_news_dict.items():
            icon = "🚀" if s_info["chg"] >= 0 else "📉"
            md_content.append(f"### {icon} {s_name} (전일비 {s_info['chg']:+.2f}%, 장중 {s_info['intra']:+.2f}%)")
            if s_info["news"]:
                for n in s_info["news"]:
                    md_content.append(f"- [{n['title']}]({n['link']})")
            else:
                md_content.append("- 최근 개별 뉴스가 없습니다.")
            md_content.append("")

    # [신규] 이동평균선(10일, 20일, 50일, 100일, 200일) 터치 종목 분석
    md_content.append("## 📐 [기술적 분석] 주요 이동평균선(10일·20일·50일·100일·200일) 터치 종목")
    md_content.append("> **이평선 매매 가이드**: 20일선(단기 생명선), 50일선/100일선(중기 수급선), 200일선(장기 대세선)에 당일 가격 봉이 닿았거나 근접(±0.8%)한 종목들로, 주요 변곡점(지지 반등 또는 저항 돌파)이 발생할 가능성이 높은 종목입니다.")
    md_content.append("")

    if ma_touch_events:
        ma_table_rows = []
        for ev in ma_touch_events:
            ma_table_rows.append([
                ev["name"], ev["symbol"], f"{ev['period']}일선", ev["ma_val"], ev["tag"], ev["action"]
            ])
        md_content.append(build_markdown_table(
            ["종목명", "코드/티커", "해당 이평선", "이평선 가격", "유형", "장중 이평선 반응 및 이격"],
            ma_table_rows
        ))
    else:
        md_content.append("- 당일 주요 이평선에 인접하거나 터치한 종목이 없습니다.")
    md_content.append("")

    # 1. 미국 지수
    md_content.append("## 1. 🇺🇸 미국 주요 지수 및 대표 ETF")
    md_content.append(build_markdown_table(
        ["종목명", "티커", "시가 ($)", "현재가 ($)", "장중 저가~고가 ($)", "전일비", "장중변동(시가대비)", "장중 추세"],
        us_indices_table
    ))
    md_content.append("")

    # 2. 미국 빅테크 & 반도체
    md_content.append("## 2. 🤖 미국 빅테크 & 글로벌 반도체 생태계")
    md_content.append(build_markdown_table(
        ["종목명", "주요 분야", "티커", "시가 ($)", "현재가 ($)", "장중 저가~고가 ($)", "전일비", "장중변동(시가대비)", "장중 추세"],
        us_stocks_table
    ))
    md_content.append("")

    # 3. S&P 500 가치주 및 매크로 섹터 대장주
    md_content.append("## 3. 🏛️ S&P 500 가치주 & 주요 섹터 대장주 (금융·산업재·헬스케어·필수소비·에너지·리츠·AI전력)")
    md_content.append(build_markdown_table(
        ["종목명", "섹터", "핵심 역할/사업", "티커", "시가 ($)", "현재가 ($)", "장중 저가~고가 ($)", "전일비", "장중변동(시가대비)", "장중 추세"],
        us_sector_table
    ))
    md_content.append("")

    # 4. 국내 대형 반도체
    md_content.append("## 4. 🇰🇷 국내 대형 반도체 (투톱)")
    md_content.append(build_markdown_table(
        ["종목명", "주요 분야", "코드", "시가 (원)", "현재가 (원)", "장중 저가~고가 (원)", "전일비", "장중변동(시가대비)", "장중 추세"],
        kr_large_table
    ))
    md_content.append("")

    # 5. 국내 소부장
    md_content.append("## 5. ⚙️ 국내 반도체 소재·부품·장비(소부장) 및 디자인하우스")
    md_content.append(build_markdown_table(
        ["기업명", "공정/핵심역할", "코드", "시가 (원)", "현재가 (원)", "장중 저가~고가 (원)", "전일비", "장중변동(시가대비)", "장중 추세"],
        kr_sobujang_table
    ))
    md_content.append("")

    # 6. 토스증권 및 섹터별 뉴스
    md_content.append("## 6. 📰 토스증권 실시간 주요 뉴스 & 분야별 헤드라인")
    for topic, items in news_dict.items():
        md_content.append(f"### 📌 {topic}")
        if items:
            for it in items:
                pub_info = f" ({it.get('publisher', '')})" if it.get("publisher") else ""
                md_content.append(f"- [{it['title']}]({it['link']}){pub_info}")
        else:
            md_content.append("- 최근 관련 뉴스가 없습니다.")
        md_content.append("")

    report_text = "\n".join(md_content)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    print(f"\n✅ 심층 리포트가 성공적으로 생성되었습니다: {report_path}")
    print(f"👉 Finder에서 확인: {os.path.abspath(report_path)}\n")

if __name__ == "__main__":
    run_market_tracker()
