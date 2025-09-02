# ABC사 KPI 목표 대비 실적 현황 분석 데이터베이스 명세서

## 1. SQLite 테이블 생성 SQL

```sql
CREATE TABLE kpi_target_actual_trends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kpi_name VARCHAR(50) NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    target_or_actual VARCHAR(10) NOT NULL,
    category_large VARCHAR(20) NOT NULL,
    category_small VARCHAR(30) NOT NULL,
    value DECIMAL(12,2) NOT NULL,
    unit VARCHAR(10) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- KPI 성과 분석을 위한 뷰
CREATE VIEW monthly_kpi_performance AS
SELECT 
    kpi_name,
    year,
    month,
    category_large,
    category_small,
    MAX(CASE WHEN target_or_actual = '목표' THEN value END) as target_value,
    MAX(CASE WHEN target_or_actual = '실적' THEN value END) as actual_value,
    ROUND(
        (MAX(CASE WHEN target_or_actual = '실적' THEN value END) / 
         MAX(CASE WHEN target_or_actual = '목표' THEN value END) * 100), 2
    ) as achievement_rate,
    unit
FROM kpi_target_actual_trends 
GROUP BY kpi_name, year, month, category_large, category_small, unit;

-- 연간 KPI 요약 뷰
CREATE VIEW yearly_kpi_summary AS
SELECT 
    kpi_name,
    year,
    category_large,
    AVG(CASE WHEN target_or_actual = '목표' THEN value END) as avg_target,
    AVG(CASE WHEN target_or_actual = '실적' THEN value END) as avg_actual,
    COUNT(DISTINCT month) as data_months,
    unit
FROM kpi_target_actual_trends 
GROUP BY kpi_name, year, category_large, unit;

-- 인덱스 생성
CREATE INDEX idx_kpi_name ON kpi_target_actual_trends(kpi_name);
CREATE INDEX idx_year_month ON kpi_target_actual_trends(year, month);
CREATE INDEX idx_target_actual ON kpi_target_actual_trends(target_or_actual);
CREATE INDEX idx_category_large ON kpi_target_actual_trends(category_large);
CREATE INDEX idx_category_small ON kpi_target_actual_trends(category_small);
```

## 2. 테이블 및 컬럼 상세 설명

### 테이블 개요
- **테이블명**: `kpi_target_actual_trends`
- **목적**: ABC사의 다양한 KPI에 대한 월별 목표 대비 실적 현황을 관리하고 분석
- **데이터 구조**: 11개 KPI × 12개월 × 2(목표/실적) × 2년 = 약 528건 데이터
- **분석 기능**: 목표 달성률, 월별/연도별 트렌드, 품종별 성과 비교

### 컬럼 상세 설명

| 컬럼명 | 데이터타입 | 설명 | 예시 |
|--------|------------|------|------|
| `id` | INTEGER | 기본키, 자동증가 | 1, 2, 3... |
| `kpi_name` | VARCHAR(50) | KPI 명칭 | '총매출금액현황', '고객만족도지수평가' |
| `year` | INTEGER | 연도 | 2024, 2025 |
| `month` | INTEGER | 월 (1-12) | 1, 6, 12 |
| `target_or_actual` | VARCHAR(10) | 목표/실적 구분 | '목표', '실적' |
| `category_large` | VARCHAR(20) | 대분류 (품종1) | '전자', '일용품', '곡물', '음료' |
| `category_small` | VARCHAR(30) | 소분류 (품종2) | '태블릿', '휴지', '쌀', '주스' |
| `value` | DECIMAL(12,2) | KPI 수치값 | 144.79, 124.81, 8.5 |
| `unit` | VARCHAR(10) | 측정 단위 | '억원', '%', '만명', '점' |

### KPI별 상세 정보

| KPI명 | 측정단위 | 값 범위 | 설명 |
|-------|----------|---------|------|
| 총매출금액현황 | 억원 | 50~200 | 월별 총 매출액 |
| 고객만족도지수평가 | 점 | 7~10 | 고객 만족도 점수 |
| 고객이용자수현황 | 만명 | 10~50 | 월 활성 고객 수 |
| 광고클릭집계횟수 | 만회 | 5~25 | 월 광고 클릭 수 |
| 구매전환비율통계 | % | 2~8 | 방문자 대비 구매 전환율 |
| 방문자접속횟수 | 만명 | 20~100 | 월 웹사이트 방문자 수 |
| 상품재고보유현황 | 억원 | 30~150 | 월말 기준 재고 금액 |
| 운영비용합계액 | 억원 | 15~80 | 월별 총 운영비용 |
| 이용자수현황 | 만명 | 8~40 | 서비스 이용자 수 |
| 제품불량발생비율 | % | 0.1~2.0 | 생산 제품 중 불량률 |
| 회원이탈발생비율 | % | 1~5 | 월 회원 이탈률 |

## 3. 예상 질문과 SQL 쿼리

### 자주 묻는 질문들과 해당 SQL 쿼리

| 번호 | 질문 | SQL 쿼리 | 예상 결과 |
|------|------|----------|----------|
| 1 | 2024년 1월 전자 태블릿의 총매출금액 실적은 얼마야? | `SELECT value FROM kpi_target_actual_trends WHERE kpi_name='총매출금액현황' AND year=2024 AND month=1 AND target_or_actual='실적' AND category_large='전자' AND category_small='태블릿';` | 144.79 억원 |
| 2 | 2024년 음료 주스의 매출 목표와 실적을 비교해줘 | `SELECT month, target_value, actual_value, achievement_rate FROM monthly_kpi_performance WHERE kpi_name='총매출금액현황' AND year=2024 AND category_large='음료' AND category_small='주스';` | 1월: 목표150 실적144.79 등 |
| 3 | 2024년 1월~6월 동안 곡물(쌀)의 매출 추이를 보여줘 | `SELECT month, actual_value FROM monthly_kpi_performance WHERE kpi_name='총매출금액현황' AND year=2024 AND month BETWEEN 1 AND 6 AND category_large='곡물' AND category_small='쌀';` | 1월: 111.18, 2월: 115.28 등 |
| 4 | 총매출금액현황에서 2024년 2월 실적 상위 3개 품종은? | `SELECT category_large, category_small, value FROM kpi_target_actual_trends WHERE kpi_name='총매출금액현황' AND year=2024 AND month=2 AND target_or_actual='실적' ORDER BY value DESC LIMIT 3;` | 전자-태블릿: 144.79 등 |
| 5 | 2024년 1분기 일용품(휴지)의 목표 대비 실적 달성률은? | `SELECT AVG(achievement_rate) as avg_achievement FROM monthly_kpi_performance WHERE kpi_name='총매출금액현황' AND year=2024 AND month BETWEEN 1 AND 3 AND category_large='일용품' AND category_small='휴지';` | 95.2% |
| 6 | 2024년 전체 매출에서 품종1이 '전자'인 항목의 합계는? | `SELECT SUM(value) FROM kpi_target_actual_trends WHERE kpi_name='총매출금액현황' AND year=2024 AND target_or_actual='실적' AND category_large='전자';` | 1,850.5 억원 |
| 7 | 2024년 7월까지 모든 KPI별 목표와 실적 차이를 요약해줘 | `SELECT kpi_name, SUM(CASE WHEN target_or_actual='목표' THEN value END) as total_target, SUM(CASE WHEN target_or_actual='실적' THEN value END) as total_actual FROM kpi_target_actual_trends WHERE year=2024 AND month <= 7 GROUP BY kpi_name;` | 총매출: 목표 1200, 실적 1150 등 |
| 8 | 이용자수현황 KPI에서 2024년 가장 높은 실적을 기록한 월은? | `SELECT month, MAX(value) as max_value FROM kpi_target_actual_trends WHERE kpi_name='이용자수현황' AND year=2024 AND target_or_actual='실적' GROUP BY month ORDER BY max_value DESC LIMIT 1;` | 7월: 38.5만명 |
| 9 | 품종2 기준으로 2024년 매출액이 가장 큰 카테고리는? | `SELECT category_small, SUM(value) as total_sales FROM kpi_target_actual_trends WHERE kpi_name='총매출금액현황' AND year=2024 AND target_or_actual='실적' GROUP BY category_small ORDER BY total_sales DESC LIMIT 1;` | 태블릿: 980.5 억원 |
| 10 | 총매출금액현황 KPI에서 월별 목표 대비 실적이 가장 낮았던 달은? | `SELECT month, MIN(achievement_rate) as min_rate FROM monthly_kpi_performance WHERE kpi_name='총매출금액현황' AND year=2024 GROUP BY month ORDER BY min_rate ASC LIMIT 1;` | 3월: 85.2% |

## 4. 데이터 활용 가이드

### KPI 성과 분석
```sql
-- 월별 KPI 달성률 분석
SELECT 
    kpi_name,
    month,
    AVG(achievement_rate) as avg_achievement_rate,
    COUNT(*) as data_count
FROM monthly_kpi_performance 
WHERE year = 2024
GROUP BY kpi_name, month
ORDER BY kpi_name, month;
```

### 품종별 성과 비교
```sql
-- 대분류별 연간 성과 요약
SELECT 
    category_large,
    kpi_name,
    AVG(CASE WHEN target_or_actual = '목표' THEN value END) as avg_target,
    AVG(CASE WHEN target_or_actual = '실적' THEN value END) as avg_actual,
    ROUND(AVG(CASE WHEN target_or_actual = '실적' THEN value END) / 
          AVG(CASE WHEN target_or_actual = '목표' THEN value END) * 100, 2) as achievement_rate
FROM kpi_target_actual_trends 
WHERE year = 2024 AND kpi_name = '총매출금액현황'
GROUP BY category_large, kpi_name
ORDER BY achievement_rate DESC;
```

### 트렌드 분석
```sql
-- 월별 성장률 분석
SELECT 
    kpi_name,
    month,
    AVG(value) as monthly_avg,
    LAG(AVG(value)) OVER (PARTITION BY kpi_name ORDER BY month) as prev_month_avg,
    ROUND((AVG(value) - LAG(AVG(value)) OVER (PARTITION BY kpi_name ORDER BY month)) / 
          LAG(AVG(value)) OVER (PARTITION BY kpi_name ORDER BY month) * 100, 2) as growth_rate
FROM kpi_target_actual_trends 
WHERE year = 2024 AND target_or_actual = '실적'
GROUP BY kpi_name, month
ORDER BY kpi_name, month;
```

### 이상치 탐지
```sql
-- 목표 달성률이 비정상적인 데이터 탐지
WITH achievement_stats AS (
    SELECT 
        kpi_name,
        AVG(achievement_rate) as avg_rate,
        STDEV(achievement_rate) as std_rate
    FROM monthly_kpi_performance 
    WHERE year = 2024
    GROUP BY kpi_name
)
SELECT 
    mp.kpi_name,
    mp.month,
    mp.category_large,
    mp.category_small,
    mp.achievement_rate,
    CASE 
        WHEN mp.achievement_rate > (as.avg_rate + 2 * as.std_rate) THEN '이상 높음'
        WHEN mp.achievement_rate < (as.avg_rate - 2 * as.std_rate) THEN '이상 낮음'
        ELSE '정상'
    END as status
FROM monthly_kpi_performance mp
JOIN achievement_stats as ON mp.kpi_name = as.kpi_name
WHERE mp.year = 2024
  AND (mp.achievement_rate > (as.avg_rate + 2 * as.std_rate) 
       OR mp.achievement_rate < (as.avg_rate - 2 * as.std_rate))
ORDER BY mp.kpi_name, mp.month;
```

---
*생성일: 2024년*  
*문서 버전: 1.0*  
*담당: ABC사 경영관리팀*
*용도: KPI 목표 대비 실적 분석 및 경영 성과 관리*
