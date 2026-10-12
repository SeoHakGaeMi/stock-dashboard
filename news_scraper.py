import urllib.parse
import xml.etree.ElementTree as ET
import requests
from config import NEWS_KEYWORDS

def fetch_stock_specific_news(stock_name: str, max_items: int = 2) -> list:
    """특이 종목(급등/급락)의 개별 원인 분석을 위한 맞춤형 최신 뉴스 수집"""
    clean_name = stock_name.split("(")[0].strip()
    query = f"{clean_name} 주가 급등 OR 급락 OR 실적"
    return fetch_rss_news(query, max_items=max_items)

def fetch_toss_news(limit: int = 6) -> list:
    """토스증권 실시간 헤드라인 및 주요 뉴스 수집"""
    url = "https://wts-info-api.tossinvest.com/api/v2/forum/news/headline"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
    }

    toss_news = []
    try:
        res = requests.get(url, headers=headers, timeout=6)
        if res.status_code == 200:
            data = res.json()
            items = data if isinstance(data, list) else data.get("result", data.get("articles", data.get("items", [])))
            if isinstance(items, list):
                for art in items[:limit]:
                    title = art.get("title") or art.get("headline") or art.get("subject")
                    link = art.get("link") or art.get("url") or art.get("outLink")
                    publisher = art.get("publisher") or art.get("mediaName") or art.get("sourceName", "토스증권")
                    date = art.get("createdAt") or art.get("publishedAt", "")
                    if title:
                        toss_news.append({
                            "title": title,
                            "link": link if link else "https://tossinvest.com",
                            "publisher": publisher,
                            "date": date
                        })
    except Exception:
        pass

    if not toss_news:
        toss_news = fetch_rss_news("토스증권 시장 이슈 증시 헤드라인", max_items=limit)

    return toss_news

def fetch_rss_news(query: str, max_items: int = 4) -> list:
    """구글 뉴스 RSS를 통해 특정 키워드의 최신 뉴스 헤드라인과 링크를 가져옵니다."""
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)"
    }

    news_list = []
    try:
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            channel = root.find("channel")
            if channel is not None:
                items = channel.findall("item")
                for item in items[:max_items]:
                    title_elem = item.find("title")
                    link_elem = item.find("link")
                    pub_elem = item.find("pubDate")

                    title = title_elem.text if title_elem is not None else ""
                    link = link_elem.text if link_elem is not None else ""
                    pub_date = pub_elem.text if pub_elem is not None else ""

                    if title:
                        news_list.append({
                            "title": title,
                            "link": link,
                            "date": pub_date
                        })
    except Exception:
        pass

    return news_list

def get_all_sector_news() -> dict:
    """설정된 모든 관심 섹터의 뉴스와 토스증권 헤드라인을 함께 수집합니다."""
    results = {}

    toss_items = fetch_toss_news(limit=5)
    results["토스증권 실시간 주요 뉴스"] = toss_items

    for kw in NEWS_KEYWORDS:
        topic = kw["topic"]
        query = kw["query"]
        items = fetch_rss_news(query, max_items=4)
        results[topic] = items

    return results

if __name__ == "__main__":
    news = get_all_sector_news()
    for topic, items in news.items():
        print(f"=== {topic} ===")
        for it in items:
            print(f"- {it['title']} ({it['link']})")
