"""
시장 및 섹터 모니터링 대상 설정 파일 (S&P 500 매크로 & 섹터 확장판)
- 미국 주요 지수 및 대표 ETF
- 미국 빅테크 & 글로벌 반도체
- [신규] S&P 500 매크로 섹터별 대표 대장주 (금융, 산업재, 헬스케어, 필수소비재/가치주, 에너지, 리츠, AI전력/유틸리티)
- 국내 대형 반도체
- 국내 반도체 소재·부품·장비(소부장) 및 디자인하우스 (공정별 세분화)
"""

# 1. 미국 시장 지수 및 대표 ETF
US_INDICES = [
    {"symbol": "SPY", "name": "S&P 500 (SPY)"},
    {"symbol": "QQQ", "name": "나스닥 100 (QQQ)"},
    {"symbol": "SOXX", "name": "필라델피아 반도체 (SOXX)"},
    {"symbol": "SMH", "name": "반도체 대표 ETF (SMH)"},
    {"symbol": "XLK", "name": "기술주 ETF (XLK)"},
]

# 2. 미국 빅테크 & 글로벌 반도체 생태계
US_STOCKS = [
    # 빅테크 & AI 플랫폼
    {"symbol": "NVDA", "name": "엔비디아 (NVIDIA)", "sub": "AI 가속기/GPU"},
    {"symbol": "AAPL", "name": "애플 (Apple)", "sub": "빅테크/온디바이스"},
    {"symbol": "MSFT", "name": "마이크로소프트 (MSFT)", "sub": "클라우드/AI"},
    {"symbol": "GOOGL", "name": "알파벳 (Google)", "sub": "클라우드/AI모델"},
    {"symbol": "AMZN", "name": "아마존 (Amazon)", "sub": "AWS/클라우드"},
    {"symbol": "META", "name": "메타 (Meta)", "sub": "오픈소스AI/플랫폼"},
    {"symbol": "TSLA", "name": "테슬라 (Tesla)", "sub": "FSD/로보틱스"},
    # 글로벌 팹리스 & 파운드리
    {"symbol": "TSM", "name": "TSMC", "sub": "파운드리 1위"},
    {"symbol": "AVGO", "name": "브로드컴 (Broadcom)", "sub": "커스텀 ASIC/네트워킹"},
    {"symbol": "AMD", "name": "AMD", "sub": "AI 칩/CPU"},
    {"symbol": "QCOM", "name": "퀄컴 (Qualcomm)", "sub": "모바일/NPU"},
    {"symbol": "MU", "name": "마이크론 (Micron)", "sub": "HBM/DRAM"},
    {"symbol": "ARM", "name": "ARM Holdings", "sub": "반도체 IP"},
    # 글로벌 반도체 전/후공정 장비
    {"symbol": "ASML", "name": "ASML", "sub": "EUV 노광장비"},
    {"symbol": "AMAT", "name": "어플라이드 머티어리얼즈", "sub": "종합 전공정 장비"},
    {"symbol": "LRCX", "name": "램리서치 (Lam Research)", "sub": "식각/증착 장비"},
    {"symbol": "KLAC", "name": "KLA", "sub": "공정 제어/검사장비"},
]

# 3. [신규] S&P 500 섹터별 대표 대장주 (가치주, 산업재, 금융, 리츠 등)
US_SECTOR_LEADERS = [
    # [금융 / Financials]
    {"symbol": "JPM", "name": "JP모건 체이스 (JPM)", "sector": "금융", "sub": "미국 1위 투자은행"},
    {"symbol": "BRK-B", "name": "버크셔 해서웨이 (BRK.B)", "sector": "금융/가치", "sub": "워런 버핏 복합기업"},
    {"symbol": "V", "name": "비자 (Visa)", "sector": "금융", "sub": "글로벌 결제 네트워크"},

    # [산업재 / Industrials]
    {"symbol": "CAT", "name": "캐터필러 (Caterpillar)", "sector": "산업재", "sub": "글로벌 중장비/인프라 1위"},
    {"symbol": "GE", "name": "GE 에어로스페이스 (GE)", "sector": "산업재/항공", "sub": "항공기 제트엔진 독점력"},
    {"symbol": "LMT", "name": "록히드 마틴 (LMT)", "sector": "산업재/방산", "sub": "미국 최대 방위산업체"},

    # [헬스케어 / Healthcare]
    {"symbol": "LLY", "name": "일라이 릴리 (Eli Lilly)", "sector": "헬스케어", "sub": "GLP-1 비만치료제 선두"},
    {"symbol": "UNH", "name": "유나이티드헬스 (UNH)", "sector": "헬스케어", "sub": "미국 최대 건강보험"},
    {"symbol": "JNJ", "name": "존슨앤드존슨 (J&J)", "sector": "헬스케어", "sub": "전통 제약/의료기기 가치주"},

    # [필수소비재 / Consumer Staples (대표 가치주)]
    {"symbol": "WMT", "name": "월마트 (Walmart)", "sector": "필수소비재", "sub": "글로벌 유통 1위/배당"},
    {"symbol": "COST", "name": "코스트코 (Costco)", "sector": "필수소비재", "sub": "창고형 회원제 유통"},
    {"symbol": "PG", "name": "프록터 앤 갬블 (P&G)", "sector": "필수소비재", "sub": "대표 배당왕 가치주"},
    {"symbol": "KO", "name": "코카콜라 (Coca-Cola)", "sector": "필수소비재", "sub": "버핏 포트폴리오 가치주"},

    # [에너지 / Energy]
    {"symbol": "XOM", "name": "엑슨모빌 (ExxonMobil)", "sector": "에너지", "sub": "미국 최대 석유/가스 메이저"},
    {"symbol": "CVX", "name": "셰브론 (Chevron)", "sector": "에너지", "sub": "정유/가스 대장주"},

    # [리츠 & 부동산 / Real Estate & REITs]
    {"symbol": "PLD", "name": "프로롤로지스 (Prologis)", "sector": "리츠", "sub": "글로벌 물류센터 1위 리츠"},
    {"symbol": "AMT", "name": "아메리칸 타워 (American Tower)", "sector": "리츠", "sub": "5G 통신탑 인프라 리츠"},
    {"symbol": "EQIX", "name": "에퀴닉스 (Equinix)", "sector": "리츠", "sub": "AI 데이터센터 리츠"},
    {"symbol": "O", "name": "리얼티 인컴 (Realty Income)", "sector": "리츠", "sub": "대표 상업용 월배당 리츠"},

    # [유틸리티 & AI 전력 인프라 / Utilities & AI Power]
    {"symbol": "NEE", "name": "넥스테라 에너지 (NextEra)", "sector": "유틸리티", "sub": "미국 최대 전력/신재생"},
    {"symbol": "CEG", "name": "콘스텔레이션 에너지 (CEG)", "sector": "AI전력", "sub": "원자력 발전/MS 장기계약"},
    {"symbol": "VST", "name": "비스트라 (Vistra)", "sector": "AI전력", "sub": "독립 발전/원전 AI 전력"},
]

# 4. 국내 대형 반도체
KR_LARGE_SEMI = [
    {"symbol": "005930", "name": "삼성전자", "sub": "메모리/파운드리"},
    {"symbol": "000660", "name": "SK하이닉스", "sub": "HBM/DRAM 선두"},
]

# 5. 국내 반도체 소재·부품·장비(소부장) 및 디자인하우스 (공정/역할별)
KR_SOBUJANG = [
    # [A] HBM & 어드밴스드 패키징/후공정 장비
    {"symbol": "042700", "name": "한미반도체", "category": "HBM 패키징 (TC본더)"},
    {"symbol": "039030", "name": "이오테크닉스", "category": "레이저 그루빙/마커"},
    {"symbol": "067310", "name": "하나마이크론", "category": "OSAT 패키징/테스트"},
    {"symbol": "252050", "name": "디아이티", "category": "레이저 어닐링"},
    {"symbol": "039440", "name": "에스티아이", "category": "리플로우/CCSS"},
    {"symbol": "064290", "name": "인텍플러스", "category": "3D 외관 검사"},

    # [B] 테스트 / 소켓 / 검사
    {"symbol": "058470", "name": "리노공업", "category": "테스트 핀/소켓"},
    {"symbol": "089030", "name": "테크윙", "category": "테스트 핸들러 (메모리)"},
    {"symbol": "095340", "name": "ISC", "category": "실리콘 러버 소켓"},
    {"symbol": "131970", "name": "두산테스나", "category": "웨이퍼 테스트 외주"},
    {"symbol": "232140", "name": "와이씨", "category": "고속 메모리 테스터"},
    {"symbol": "098460", "name": "고영", "category": "3D 검사장비"},

    # [C] 전공정 핵심 장비 (증착/식각/열처리/세정)
    {"symbol": "036930", "name": "주성엔지니어링", "category": "ALD 증착 장비"},
    {"symbol": "403870", "name": "HPSP", "category": "고압 수소 열처리"},
    {"symbol": "240810", "name": "원익IPS", "category": "증착(CVD/ALD)/식각"},
    {"symbol": "084370", "name": "유진테크", "category": "저압 화학기상증착(LPCVD)"},
    {"symbol": "319660", "name": "피에스케이", "category": "PR 스트립 장비 세계 1위"},
    {"symbol": "079370", "name": "제우스", "category": "반도체 세정 장비"},

    # [D] 핵심 소재 및 소모성 부품
    {"symbol": "357780", "name": "솔브레인", "category": "고순도 식각액/전구체"},
    {"symbol": "005290", "name": "동진쎄미켐", "category": "EUV 포토레지스트(PR)"},
    {"symbol": "014680", "name": "한솔케미칼", "category": "과산화수소/특수가스"},
    {"symbol": "064760", "name": "티씨케이", "category": "SiC 링 (식각 소모품)"},
    {"symbol": "074600", "name": "원익QnC", "category": "쿼츠웨어 부품"},

    # [E] AI 반도체 디자인하우스(DSP) & 팹리스
    {"symbol": "399720", "name": "가온칩스", "category": "삼성 파운드리 디자인솔루션"},
    {"symbol": "200710", "name": "에이디테크놀로지", "category": "TSMC/삼성 DSP"},
    {"symbol": "394280", "name": "오픈엣지테크놀로지", "category": "AI 반도체 NPU/메모리 IP"},
]

# 뉴스 검색 키워드
NEWS_KEYWORDS = [
    {"topic": "미국 증시 및 매크로/빅테크", "query": "미국 증시 S&P500 빅테크 금리 인플레이션"},
    {"topic": "S&P 500 가치주 & 산업재/에너지/금융", "query": "미국 주식 가치주 산업재 에너지 금융 캐터필러 JP모건 엑슨모빌"},
    {"topic": "글로벌 반도체 및 AI 전력", "query": "글로벌 반도체 AI전력 콘스텔레이션 TSMC 엔비디아"},
    {"topic": "국내 대형 반도체 (삼성전자/SK하이닉스)", "query": "삼성전자 SK하이닉스 HBM D램 실적"},
    {"topic": "반도체 소부장 및 패키징", "query": "반도체 소부장 한미반도체 리노공업 주성엔지니어링 HPSP 테크윙"},
]
