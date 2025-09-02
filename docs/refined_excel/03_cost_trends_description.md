# ABC사 제품 재료비 트렌드 분석 데이터베이스 명세서

## 1. SQLite 테이블 생성 SQL

```sql
CREATE TABLE product_cost_trends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name VARCHAR(50) NOT NULL,
    extract_date VARCHAR(20) NOT NULL,
    region VARCHAR(10) NOT NULL,
    inch_size INTEGER NOT NULL,
    total_cost DECIMAL(10,2) NOT NULL,
    core_cost DECIMAL(10,2) NOT NULL,
    cell_cost DECIMAL(8,2),
    blu_cost DECIMAL(8,2),
    light_source_cost DECIMAL(8,2),
    optical_cost DECIMAL(8,2),
    blu_circuit_cost DECIMAL(8,2),
    lcm_mechanism_cost DECIMAL(8,2),
    heat_dissipation_cost DECIMAL(8,2),
    circuit_cost DECIMAL(8,2),
    main_cost DECIMAL(8,2),
    oc_woc_box_cost DECIMAL(8,2),
    smps_cost DECIMAL(8,2),
    spk_cost DECIMAL(8,2),
    circuit_etc_cost DECIMAL(8,2),
    set_mechanism_cost DECIMAL(8,2),
    series VARCHAR(10) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 월별 트렌드 분석을 위한 뷰
CREATE VIEW monthly_cost_trends AS
SELECT 
    substr(extract_date, 1, 7) as year_month,
    region,
    series,
    AVG(total_cost) as avg_total_cost,
    AVG(core_cost) as avg_core_cost,
    COUNT(*) as model_count
FROM product_cost_trends 
GROUP BY substr(extract_date, 1, 7), region, series;

-- 인덱스 생성
CREATE INDEX idx_model_name ON product_cost_trends(model_name);
CREATE INDEX idx_extract_date ON product_cost_trends(extract_date);
CREATE INDEX idx_region ON product_cost_trends(region);
CREATE INDEX idx_series ON product_cost_trends(series);
CREATE INDEX idx_inch_size ON product_cost_trends(inch_size);
CREATE INDEX idx_total_cost ON product_cost_trends(total_cost);
```

## 2. 테이블 및 컬럼 상세 설명

### 테이블 개요
- **테이블명**: `product_cost_trends`
- **목적**: ABC사 제품의 월별 재료비 변동 추이를 관리하고 분석
- **데이터 구조**: 50개 제품 모델 × 6개월(2025년 2월~7월) = 총 300건 데이터
- **추출 방식**: 매월 말일 기준, 해당 월의 모든 모델이 동일한 추출날짜 보유

### 컬럼 상세 설명

| 컬럼명 | 데이터타입 | 설명 | 예시 |
|--------|------------|------|------|
| `id` | INTEGER | 기본키, 자동증가 | 1, 2, 3... |
| `model_name` | VARCHAR(50) | 제품 모델명 | 'model-A1-001', 'model-B2-150' |
| `extract_date` | VARCHAR(20) | 데이터 추출 날짜 (매월 말일) | '2025년 07월 31일' |
| `region` | VARCHAR(10) | 판매/생산 지역 | '북미', '국내', '독일', '영국' |
| `inch_size` | INTEGER | 제품 인치 크기 | 3, 7, 12, 18 |
| `total_cost` | DECIMAL(10,2) | 전체 재료비 합계 | 2111.10, 3123.50 |
| `core_cost` | DECIMAL(10,2) | 핵심 부품 재료비 합계 | 2000.1, 1000.2 |
| `cell_cost` | DECIMAL(8,2) | Cell 부품 재료비 | 1005.7 |
| `blu_cost` | DECIMAL(8,2) | BLU 부품 재료비 | 300.1 |
| `light_source_cost` | DECIMAL(8,2) | 광원 부품 재료비 | 200.8 |
| `optical_cost` | DECIMAL(8,2) | 광학 부품 재료비 | 111.1 |
| `blu_circuit_cost` | DECIMAL(8,2) | BLU회로 부품 재료비 | 50.1 |
| `lcm_mechanism_cost` | DECIMAL(8,2) | LCM기구 부품 재료비 | 55.1 |
| `heat_dissipation_cost` | DECIMAL(8,2) | 방열 부품 재료비 | 0.5 |
| `circuit_cost` | DECIMAL(8,2) | 회로 부품 재료비 | 599.1 |
| `main_cost` | DECIMAL(8,2) | Main 부품 재료비 | 200.1 |
| `oc_woc_box_cost` | DECIMAL(8,2) | OC/WOC box 부품 재료비 | 15.1 |
| `smps_cost` | DECIMAL(8,2) | SMPS 부품 재료비 | 200.3 |
| `spk_cost` | DECIMAL(8,2) | SPK 부품 재료비 | 200.1 |
| `circuit_etc_cost` | DECIMAL(8,2) | 회로기타 부품 재료비 | 300.1 |
| `set_mechanism_cost` | DECIMAL(8,2) | SET기구 부품 재료비 | 102.5 |
| `series` | VARCHAR(10) | 제품 시리즈 | 'A1', 'B2', 'C1' |

## 3. 예상 질문과 SQL 쿼리

### 자주 묻는 질문들과 해당 SQL 쿼리

| 번호 | 질문 | SQL 쿼리 | 예상 결과 |
|------|------|----------|----------|
| 1 | model-A1-001 모델 재료비 얼마야? | `SELECT total_cost FROM product_cost_trends WHERE model_name = 'model-A1-001' ORDER BY extract_date DESC LIMIT 1;` | 2111.10 |
| 2 | model-B2-150 모델의 Cell 재료비는 얼마야? | `SELECT cell_cost FROM product_cost_trends WHERE model_name = 'model-B2-150' ORDER BY extract_date DESC LIMIT 1;` | 1005.7 |
| 3 | A1 시리즈의 연차별 재료비 알려줘 | `SELECT substr(extract_date, 1, 4) as year, AVG(total_cost) as avg_cost FROM product_cost_trends WHERE series = 'A1' GROUP BY substr(extract_date, 1, 4);` | 2025: 2500.30 등 |
| 4 | model-C1-200 모델의 5월 대비 7월 재료비 차분 알려줘 | `SELECT (jul.total_cost - may.total_cost) as cost_diff FROM product_cost_trends may JOIN product_cost_trends jul ON may.model_name = jul.model_name WHERE may.model_name = 'model-C1-200' AND may.extract_date LIKE '%05월%' AND jul.extract_date LIKE '%07월%';` | +150.20 |
| 5 | 북미 지역 평균 재료비는? | `SELECT AVG(total_cost) FROM product_cost_trends WHERE region = '북미';` | 2845.60 |
| 6 | Cell 부품 재료비가 가장 높은 모델은? | `SELECT model_name, cell_cost FROM product_cost_trends ORDER BY cell_cost DESC LIMIT 5;` | model-E2-450: 1200.0 등 |
| 7 | 6월 대비 7월 재료비 상승률 상위 10개 모델은? | `SELECT model_name, ((jul.total_cost - jun.total_cost) / jun.total_cost * 100) as increase_rate FROM product_cost_trends jun JOIN product_cost_trends jul ON jun.model_name = jul.model_name WHERE jun.extract_date LIKE '%06월%' AND jul.extract_date LIKE '%07월%' ORDER BY increase_rate DESC LIMIT 10;` | model-D1-300: +15.2% 등 |
| 8 | 15인치 이상 모델의 평균 재료비는? | `SELECT AVG(total_cost) FROM product_cost_trends WHERE inch_size >= 15;` | 4520.80 |
| 9 | 시리즈별 월별 재료비 트렌드는? | `SELECT series, substr(extract_date, 6, 2) as month, AVG(total_cost) FROM product_cost_trends GROUP BY series, substr(extract_date, 6, 2) ORDER BY series, month;` | A1 02월: 2300, A1 03월: 2350 등 |
| 10 | 재료비 이상치(평균대비 ±20% 초과) 모델은? | `WITH avg_cost AS (SELECT AVG(total_cost) as avg_val FROM product_cost_trends) SELECT model_name, total_cost FROM product_cost_trends, avg_cost WHERE total_cost > avg_val * 1.2 OR total_cost < avg_val * 0.8;` | model-E2-500: 5200.0 등 |

## 4. 데이터 활용 가이드

### 월별 트렌드 분석
```sql
-- 모델별 월별 재료비 변화 추이
SELECT 
    model_name,
    extract_date,
    total_cost,
    LAG(total_cost) OVER (PARTITION BY model_name ORDER BY extract_date) as prev_cost,
    total_cost - LAG(total_cost) OVER (PARTITION BY model_name ORDER BY extract_date) as cost_change
FROM product_cost_trends 
WHERE model_name = 'model-A1-001'
ORDER BY extract_date;
```

### 지역별 비교 분석
```sql
-- 지역별 평균 재료비 및 부품별 비중
SELECT 
    region,
    AVG(total_cost) as avg_total,
    AVG(cell_cost / total_cost * 100) as cell_ratio,
    AVG(blu_cost / total_cost * 100) as blu_ratio,
    AVG(circuit_cost / total_cost * 100) as circuit_ratio
FROM product_cost_trends 
GROUP BY region
ORDER BY avg_total DESC;
```

### 이상치 탐지
```sql
-- 전월 대비 재료비 급변동 모델 탐지 (±15% 이상)
WITH monthly_changes AS (
    SELECT 
        model_name,
        extract_date,
        total_cost,
        LAG(total_cost) OVER (PARTITION BY model_name ORDER BY extract_date) as prev_cost,
        ABS((total_cost - LAG(total_cost) OVER (PARTITION BY model_name ORDER BY extract_date)) / LAG(total_cost) OVER (PARTITION BY model_name ORDER BY extract_date) * 100) as change_rate
    FROM product_cost_trends
)
SELECT model_name, extract_date, total_cost, prev_cost, change_rate
FROM monthly_changes 
WHERE change_rate > 15
ORDER BY change_rate DESC;
```

### 부품별 기여도 분석
```sql
-- 시리즈별 부품 비용 구성 분석
SELECT 
    series,
    AVG(cell_cost / total_cost * 100) as cell_contribution,
    AVG(blu_cost / total_cost * 100) as blu_contribution,
    AVG(circuit_cost / total_cost * 100) as circuit_contribution,
    AVG((cell_cost + blu_cost + circuit_cost) / total_cost * 100) as top3_contribution
FROM product_cost_trends 
GROUP BY series
ORDER BY series;
```

---
*생성일: 2024년*  
*문서 버전: 1.0*  
*담당: ABC사 생산기획팀*
*용도: 제품 재료비 트렌드 분석 및 원가 관리*
