#!/bin/bash
cd "$(dirname "$0")"

# Xcode Command Line Tools 및 python3 확인
if ! python3 --version >/dev/null 2>&1; then
    echo "⚠️ Python 실행 환경이 준비되지 않았습니다."
    echo "터미널에서 아래 명령어를 실행하여 개발자 도구를 먼저 설치해 주세요:"
    echo "  xcode-select --install"
    exit 1
fi

# 1. 가상환경 확인 및 생성
if [ ! -d "venv" ]; then
    echo "📦 파이썬 가상환경(venv)을 생성합니다..."
    python3 -m venv venv
fi

# 2. 가상환경 활성화
source venv/bin/activate

# 3. 필수 패키지 설치
echo "🔍 필수 라이브러리(requests, python-dotenv) 확인 및 설치 중..."
pip install -q -r requirements.txt

# 4. 메인 트래커 실행
python main.py
