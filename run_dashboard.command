#!/bin/bash
cd "$(dirname "$0")"

echo "=========================================="
echo "🚀 S&P 100 & 국내 반도체 증시 대시보드 데이터 수집 및 실행"
echo "=========================================="

if [ -f "venv/bin/python3" ]; then
    ./venv/bin/python3 build_unified_dashboard.py
elif [ -d "venv" ]; then
    source venv/bin/activate
    python3 build_unified_dashboard.py
else
    python3 build_unified_dashboard.py
fi

if [ -f "reports/unified_market_dashboard.html" ]; then
    open reports/unified_market_dashboard.html
fi

echo ""
echo "브라우저에서 통합 대시보드가 열렸습니다."
echo "엔터(Enter) 키를 누르면 창이 닫힙니다."
read
