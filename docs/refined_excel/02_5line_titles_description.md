# ABC사 스마트폰 AI 기능 제품 적용 현황 데이터베이스 명세서

## 1. SQLite 테이블 생성 SQL

```sql
CREATE TABLE ai_product_application (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ai_category VARCHAR(50) NOT NULL,
    ai_function_name VARCHAR(100) NOT NULL,
    lineup_ab101 CHAR(1) DEFAULT '',
    lineup_ab102 CHAR(1) DEFAULT '',
    lineup_ab103 CHAR(1) DEFAULT '',
    lineup_c20 CHAR(1) DEFAULT '',
    lineup_d40 CHAR(1) DEFAULT '',
    lineup_ab104 CHAR(1) DEFAULT '',
    lineup_ab105 CHAR(1) DEFAULT '',
    lineup_ab107 CHAR(1) DEFAULT '',
    lineup_ab108 CHAR(1) DEFAULT '',
    lineup_xyz CHAR(1) DEFAULT '',
    responsible_department VARCHAR(100),
    responsible_manager VARCHAR(100),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 칩셋 정보 테이블
CREATE TABLE lineup_chipsets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lineup_name VARCHAR(20) NOT NULL,
    soc_year VARCHAR(10) NOT NULL,
    chipset_name VARCHAR(20),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스 생성
CREATE INDEX idx_ai_category_app ON ai_product_application(ai_category);
CREATE INDEX idx_responsible_department_app ON ai_product_application(responsible_department);
CREATE INDEX idx_lineup_chipset ON lineup_chipsets(lineup_name, soc_year);
```

## 2. 테이블 및 컬럼 상세 설명

### 테이블 개요
- **메인 테이블**: `ai_product_application`
- **목적**: ABC사 스마트폰 AI 기능이 각 제품 라인업에 적용된 현황을 연도별로 관리
- **데이터 구조**: 각 AI 기능별로 10개 라인업의 24년/25년 적용 여부를 매트릭스 형태로 관리

### 메인 테이블 컬럼 설명

| 컬럼명 | 데이터타입 | 설명 | 예시 |
|--------|------------|------|------|
| `id` | INTEGER | 기본키, 자동증가 | 1, 2, 3... |
| `ai_category` | VARCHAR(50) | AI 기능의 대분류 | '카메라 AI', '음성 AI' |
| `ai_function_name` | VARCHAR(100) | 구체적인 AI 기능명 | '스마트 HDR', '음성 인식' |
| `lineup_ab101` | CHAR(1) | AB101 라인업 적용 여부 | 'O' 또는 공백 |
| `lineup_ab102` | CHAR(1) | AB102 라인업 적용 여부 | 'O' 또는 공백 |
| `lineup_ab103` | CHAR(1) | AB103 라인업 적용 여부 | 'O' 또는 공백 |
| `lineup_c20` | CHAR(1) | C20 라인업 적용 여부 | 'O' 또는 공백 |
| `lineup_d40` | CHAR(1) | D40 라인업 적용 여부 | 'O' 또는 공백 |
| `lineup_ab104` | CHAR(1) | AB104 라인업 적용 여부 | 'O' 또는 공백 |
| `lineup_ab105` | CHAR(1) | AB105 라인업 적용 여부 | 'O' 또는 공백 |
| `lineup_ab107` | CHAR(1) | AB107 라인업 적용 여부 | 'O' 또는 공백 |
| `lineup_ab108` | CHAR(1) | AB108 라인업 적용 여부 | 'O' 또는 공백 |
| `lineup_xyz` | CHAR(1) | XYZ 라인업 적용 여부 | 'O' 또는 공백 |
| `responsible_department` | VARCHAR(100) | 담당 부서 | 'AI플랫폼팀', '카메라AI팀' |
| `responsible_manager` | VARCHAR(100) | 담당자 (주담당자, 부담당자) | '김태현(이수민)' |

### 칩셋 정보 테이블 컬럼 설명

| 컬럼명 | 데이터타입 | 설명 | 예시 |
|--------|------------|------|------|
| `id` | INTEGER | 기본키, 자동증가 | 1, 2, 3... |
| `lineup_name` | VARCHAR(20) | 제품 라인업명 | 'AB101', 'AB102', 'C20' |
| `soc_year` | VARCHAR(10) | SoC 연도 구분 | '25 SoC', '24 SoC' |
| `chipset_name` | VARCHAR(20) | 칩셋명 | 'Chip-A', 'Chip-B', 'N/A' |

## 3. 예상 질문과 SQL 쿼리

### 자주 묻는 질문들과 해당 SQL 쿼리

| 번호 | 질문 | SQL 쿼리 | 예상 결과 |
|------|------|----------|----------|
| 1 | 카메라 AI 기능은 총 몇 개인가요? | `SELECT COUNT(*) FROM ai_product_application WHERE ai_category = '카메라 AI';` | 예: 12개 |
| 2 | AB101 라인업에 적용된 AI 기능들은? | `SELECT ai_function_name, ai_category FROM ai_product_application WHERE lineup_ab101 = 'O';` | 스마트 HDR, 얼굴 인식 등 |
| 3 | 전체 라인업에 공통으로 적용된 AI 기능은? | `SELECT ai_function_name FROM ai_product_application WHERE lineup_ab101='O' AND lineup_ab102='O' AND lineup_c20='O' AND lineup_d40='O';` | 얼굴 인식, 음성 명령 등 |
| 4 | AI플랫폼팀에서 담당하는 기능들은? | `SELECT ai_function_name, ai_category FROM ai_product_application WHERE responsible_department='AI플랫폼팀';` | 개인화 AI, 성능최적화 등 |
| 5 | C20 라인업 전용 AI 기능은? | `SELECT ai_function_name FROM ai_product_application WHERE lineup_c20='O' AND lineup_ab101='' AND lineup_ab102='';` | 프리미엄 카메라 AI 등 |
| 6 | 각 라인업별 AI 기능 탑재 수는? | `SELECT 'AB101' as lineup, COUNT(*) FROM ai_product_application WHERE lineup_ab101='O' UNION ALL SELECT 'AB102', COUNT(*) FROM ai_product_application WHERE lineup_ab102='O';` | AB101: 15개, AB102: 18개 등 |
| 7 | 음성 AI 기능이 적용된 라인업들은? | `SELECT DISTINCT CASE WHEN lineup_ab101='O' THEN 'AB101' END FROM ai_product_application WHERE ai_category='음성 AI' AND lineup_ab101='O';` | AB101, AB104, C20 등 |
| 8 | 각 부서별 담당 기능 수는? | `SELECT responsible_department, COUNT(*) as total_functions FROM ai_product_application GROUP BY responsible_department ORDER BY total_functions DESC;` | AI플랫폼팀: 8개 등 |
| 9 | 특정 칩셋을 사용하는 라인업의 AI 기능은? | `SELECT DISTINCT app.ai_function_name FROM ai_product_application app JOIN lineup_chipsets lc ON lc.chipset_name='Chip-A';` | 고성능 AI 기능들 |
| 10 | 가장 많은 AI 기능이 적용된 라인업은? | `SELECT lineup, feature_count FROM (SELECT COUNT(*) as feature_count, 'AB101' as lineup FROM ai_product_application WHERE lineup_ab101='O') ORDER BY feature_count DESC LIMIT 1;` | AB104: 22개 기능 |

## 4. 데이터 활용 가이드

### 제품 로드맵 분석
```sql
-- 라인업별 AI 기능 적용 현황
SELECT 
    ai_category,
    SUM(CASE WHEN lineup_ab101='O' THEN 1 ELSE 0 END) as ab101_count,
    SUM(CASE WHEN lineup_ab102='O' THEN 1 ELSE 0 END) as ab102_count,
    SUM(CASE WHEN lineup_c20='O' THEN 1 ELSE 0 END) as c20_count
FROM ai_product_application 
GROUP BY ai_category;
```

### 경쟁력 분석
```sql
-- 라인업별 AI 기능 탑재 현황
SELECT 
    'AB101' as lineup,
    COUNT(CASE WHEN lineup_ab101='O' THEN 1 END) as ai_features
FROM ai_product_application
UNION ALL
SELECT 
    'AB102' as lineup,
    COUNT(CASE WHEN lineup_ab102='O' THEN 1 END) as ai_features
FROM ai_product_application
UNION ALL
SELECT 
    'C20' as lineup,
    COUNT(CASE WHEN lineup_c20='O' THEN 1 END) as ai_features
FROM ai_product_application;
```

### 개발 리소스 관리
```sql
-- 부서별 담당 기능과 적용 범위
SELECT 
    responsible_department,
    COUNT(*) as total_functions,
    SUM(CASE WHEN lineup_ab101='O' OR lineup_ab102='O' THEN 1 ELSE 0 END) as premium_lineup_functions,
    SUM(CASE WHEN lineup_c20='O' OR lineup_d40='O' THEN 1 ELSE 0 END) as mid_range_functions
FROM ai_product_application 
GROUP BY responsible_department
ORDER BY total_functions DESC;
```

---
*생성일: 2024년*  
*문서 버전: 1.0*  
*담당: ABC사 AI개발팀*
*용도: 제품 라인업별 AI 기능 적용 현황 관리 및 분석*
