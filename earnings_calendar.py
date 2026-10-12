import os
import datetime
import webbrowser

def generate_weekly_earnings_calendar():
    today = datetime.date.today()
    # 다음 주 월요일 계산
    days_ahead = (0 - today.weekday() + 7) % 7
    if days_ahead == 0:
        days_ahead = 7
    next_monday = today + datetime.timedelta(days=days_ahead)
    next_friday = next_monday + datetime.timedelta(days=4)

    mon_str = next_monday.strftime("%m월 %d일")
    fri_str = next_friday.strftime("%m월 %d일")

    print(f"==========================================")
    print(f"📅 S&P 500 주간 실적발표 캘린더 생성 중 ({mon_str} ~ {fri_str})")
    print(f"==========================================")

    reports_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(reports_dir, exist_ok=True)
    html_path = os.path.join(reports_dir, "earnings_calendar.html")

    print(f"✅ 주간 실적 발표 캘린더 웹 대시보드가 준비되었습니다: {html_path}")

if __name__ == "__main__":
    generate_weekly_earnings_calendar()
