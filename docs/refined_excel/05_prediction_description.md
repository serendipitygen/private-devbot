# ABC사 제품 판매량 및 가격 예측 분석 데이터베이스 명세서

## 1. SQLite 테이블 생성 SQL

```sql
CREATE TABLE sales_prediction_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subsidiary VARCHAR(20) NOT NULL,
    year_scm INTEGER NOT NULL,
    year_month_scm VARCHAR(10) NOT NULL,
    year_week VARCHAR(10) NOT NULL,
    brand VARCHAR(20) NOT NULL,
    segment VARCHAR(20) NOT NULL,
    item_model VARCHAR(50) NOT NULL,
    inch_size INTEGER NOT NULL,
    sellout_amount DECIMAL(15,2),
    sellout_quantity INTEGER,
    average_selling_price DECIMAL(10,2),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 예측 분석을 위한 집계 뷰
CREATE VIEW weekly_sales_summary AS
SELECT 
    year_week,
    brand,
    segment,
    SUM(sellout_amount) as total_amount,
    SUM(sellout_quantity) as total_quantity,
    AVG(average_selling_price) as avg_price,
    COUNT(DISTINCT item_model) as model_count
FROM sales_prediction_data 
GROUP BY year_week, brand, segment;

-- 월별 트렌드 분석 뷰
CREATE VIEW monthly_trend_analysis AS
SELECT 
    year_month_scm,
    brand,
    segment,
    AVG(sellout_amount) as avg_amount,
    AVG(sellout_quantity) as avg_quantity,
    AVG(average_selling_price) as avg_price,
    COUNT(*) as data_points
FROM sales_prediction_data 
GROUP BY year_month_scm, brand, segment;

-- 인덱스 생성
CREATE INDEX idx_year_week ON sales_prediction_data(year_week);
CREATE INDEX idx_brand ON sales_prediction_data(brand);
CREATE INDEX idx_segment ON sales_prediction_data(segment);
CREATE INDEX idx_item_model ON sales_prediction_data(item_model);
CREATE INDEX idx_year_month ON sales_prediction_data(year_month_scm);
```

## 2. 테이블 및 컬럼 상세 설명

### 테이블 개요
- **테이블명**: `sales_prediction_data`
- **목적**: 북미 지역 제품의 주간별 판매 데이터를 기반으로 향후 판매량 및 가격을 예측
- **데이터 구조**: 2023년 1주차~2025년 33주차 (137주) × 15개 브랜드 × 6개 제품군 × 평균 12개 모델
- **총 데이터 규모**: 약 140,000건

### 컬럼 상세 설명

| 컬럼명 | 데이터타입 | 설명 | 예시 |
|--------|------------|------|------|
| `id` | INTEGER | 기본키, 자동증가 | 1, 2, 3... |
| `subsidiary` | VARCHAR(20) | 판매 지역 (현재 북미만) | '북미' |
| `year_scm` | INTEGER | SCM 연도 | 2023, 2024, 2025 |
| `year_month_scm` | VARCHAR(10) | SCM 연월 표기 | '23M01', '24M12' |
| `year_week` | VARCHAR(10) | SCM 연주차 표기 | '23W01', '25W33' |
| `brand` | VARCHAR(20) | 브랜드명 | 'A사', 'B사', 'C사' |
| `segment` | VARCHAR(20) | GfK 전략적 제품군 구분 | 'SEG-01', 'SEG-02' |
| `item_model` | VARCHAR(50) | 제품 모델명 | 'Model-A01-001' |
| `inch_size` | INTEGER | 제품 인치 크기 | 5, 8, 12, 15 |
| `sellout_amount` | DECIMAL(15,2) | 주간 셀아웃 총 금액 | 6000.00, -500.00 |
| `sellout_quantity` | INTEGER | 주간 셀아웃 수량 (양수/음수) | 100, -20 |
| `average_selling_price` | DECIMAL(10,2) | 평균 판매 가격 (ASP) | 500.00, 750.50 |

## 3. 판매량 및 가격 예측 알고리즘

### 3.1 선형 회귀 (Linear Regression)

**이론**: 시계열 데이터의 선형 트렌드를 파악하여 미래값을 예측

**핵심 아이디어**:
- 과거 주차별 판매 데이터를 X축(시간), Y축(판매량/가격)으로 설정
- 최소제곱법으로 최적의 직선을 찾아 미래 시점의 값을 예측
- R² 스코어로 모델의 설명력을 측정하여 신뢰도 계산

**구현 요소**:
- sklearn.linear_model.LinearRegression 사용
- 주차를 연속된 숫자로 변환 (23W01=1, 24W01=53 등)
- 판매량과 가격 각각에 대해 별도 모델 구축
- 결과: 예측값 + R² 기반 신뢰도 + 트렌드 분석 근거

### 3.2 이동평균 (Moving Average)

**이론**: 최근 N주간의 평균값을 계산하여 단기 변동을 평활화한 예측

**핵심 아이디어**:
- 최근 8주간 데이터의 가중평균으로 미래값 예측
- 계절성 보정: 동일 분기 데이터에 1.5배 가중치 적용
- 변동성 기반 신뢰도: 표준편차가 작을수록 높은 신뢰도

**구현 요소**:
- numpy 기반 가중평균 계산
- 계절성 탐지: (주차-1)//13으로 분기 계산
- 신뢰도 계산: max(0, 1 - std/평균)
- 결과: 예측값 + 변동성 기반 신뢰도 + 계절성 보정 근거

### 3.3 ARIMA (AutoRegressive Integrated Moving Average)

**이론**: 시계열의 자기상관성과 이동평균을 결합한 고급 예측 모델

**핵심 아이디어**:
- AR(p): p개 과거 시점의 자기회귀 성분
- I(d): d번 차분하여 시계열 안정화  
- MA(q): q개 과거 오차의 이동평균 성분
- AIC 최소화와 Ljung-Box 잔차 검증으로 모델 평가

**구현 요소**:
- statsmodels.tsa.arima.model.ARIMA 사용
- 기본 차수 (2,1,2) 적용, 데이터에 따라 조정
- 신뢰구간 제공하여 예측 범위 표시
- AIC와 잔차 검증 p-value로 신뢰도 산정
- 결과: 예측값 + 신뢰구간 + AIC 기반 적합도 평가

### 3.4 예측 결과 종합 분석

**종합 예측 방법론**:
- 3개 알고리즘 각각의 신뢰도를 가중치로 사용
- 신뢰도 기반 가중평균으로 최종 예측값 산출
- 개별 결과와 종합 결과 모두 제공
- 평균 신뢰도에 따른 활용 권장사항 자동 생성

**추천 시스템**:
- 신뢰도 > 0.7: "높은 신뢰도, 예측값 적극 활용 권장"
- 신뢰도 0.4~0.7: "보통 신뢰도, 추가 데이터 수집 권장" 
- 신뢰도 < 0.4: "낮은 신뢰도, 전문가 판단 병행 필요"

## 4. 이상치 탐지 알고리즘

### 4.1 IQR (Interquartile Range) 방법

**이론**: 사분위수 범위를 이용한 통계적 이상치 탐지

**핵심 아이디어**:
- Q1(25%), Q3(75%) 사분위수 계산
- IQR = Q3 - Q1 (사분위수 범위)  
- 이상치 기준: Q1 - 1.5×IQR 미만 또는 Q3 + 1.5×IQR 초과
- 심각도: 3×IQR 초과시 'high', 그 외 'medium'

**구현 요소**:
- 판매량, 판매금액, 평균가격 각각 독립적으로 분석
- 브랜드별 이상치 탐지 및 분류
- 모델명, 주차, 메트릭, 예상범위 정보 제공
- 결과: 이상치 리스트 + 심각도 + 정상범위 기준값

## 5. 예상 질문과 SQL 쿼리

| 번호 | 질문 | SQL 쿼리 | 기대 결과 |
|------|------|----------|----------|
| 1 | Model-A01-015 모델의 25W35주차 예상가격과 판매량은? | `SELECT * FROM sales_prediction_data WHERE item_model='Model-A01-015' ORDER BY year_week DESC LIMIT 10;` | 과거 트렌드 기반 예측 |
| 2 | A사 모델들의 판매 이상치를 찾아줘 | `WITH brand_stats AS (SELECT AVG(sellout_quantity) as avg_qty, STDDEV(sellout_quantity) as std_qty FROM sales_prediction_data WHERE brand='A사') SELECT * FROM sales_prediction_data s, brand_stats bs WHERE s.brand='A사' AND ABS(s.sellout_quantity - bs.avg_qty) > 2 * bs.std_qty;` | 이상치 데이터 목록 |
| 3 | 2024년 4분기 브랜드별 평균 판매량 순위는? | `SELECT brand, AVG(sellout_quantity) as avg_qty FROM sales_prediction_data WHERE year_week LIKE '24W%' AND CAST(SUBSTR(year_week,4) AS INT) >= 40 GROUP BY brand ORDER BY avg_qty DESC;` | 브랜드 성과 랭킹 |

---
*생성일: 2024년*  
*문서 버전: 1.0*  
*담당: ABC사 데이터분석팀*
*용도: 제품 판매 예측 및 이상치 탐지*
