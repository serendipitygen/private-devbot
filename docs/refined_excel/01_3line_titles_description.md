# ABC사 스마트폰 AI 기능 데이터베이스 명세서

## 1. SQLite 테이블 생성 SQL

```sql
CREATE TABLE ai_functions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ai_category VARCHAR(50) NOT NULL,
    ai_function_name VARCHAR(100) NOT NULL,
    ai_description TEXT NOT NULL,
    introduction_year VARCHAR(10) NOT NULL,
    application_scope VARCHAR(200),
    target_region VARCHAR(200),
    uses_npu CHAR(1) DEFAULT '',
    uses_cpu CHAR(1) DEFAULT '',
    uses_dsp CHAR(1) DEFAULT '',
    uses_cloud CHAR(1) DEFAULT '',
    ddr_usage_kb INTEGER,
    flash_usage_kb INTEGER,
    is_generative CHAR(1) DEFAULT '',
    lineup VARCHAR(100),
    development_team VARCHAR(100),
    related_links VARCHAR(500),
    responsible_department VARCHAR(100),
    responsible_manager VARCHAR(50),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스 생성
CREATE INDEX idx_ai_category ON ai_functions(ai_category);
CREATE INDEX idx_introduction_year ON ai_functions(introduction_year);
CREATE INDEX idx_lineup ON ai_functions(lineup);
CREATE INDEX idx_responsible_department ON ai_functions(responsible_department);
```

## 2. 테이블 및 컬럼 상세 설명

### 테이블 개요
- **테이블명**: `ai_functions`
- **목적**: ABC사 스마트폰에 탑재되는 AI 기능들의 상세 정보를 관리
- **데이터 구조**: 각 AI 기능별로 기술적 세부사항, 적용 범위, 담당자 정보 등을 포함

### 컬럼 상세 설명

| 컬럼명 | 데이터타입 | 설명 | 예시 |
|--------|------------|------|------|
| `id` | INTEGER | 기본키, 자동증가 | 1, 2, 3... |
| `ai_category` | VARCHAR(50) | AI 기능의 대분류 | '카메라 AI', '음성 AI', '보안 AI' |
| `ai_function_name` | VARCHAR(100) | 구체적인 AI 기능명 | '스마트 HDR', '음성 인식', '얼굴 인식' |
| `ai_description` | TEXT | AI 기능의 상세 설명 | '딥러닝 알고리즘을 활용하여...' |
| `introduction_year` | VARCHAR(10) | 해당 기능이 도입된 연도 | '23년', '24년' |
| `application_scope` | VARCHAR(200) | 적용 범위 및 지원 모델 | '24년 플래그십 전용', '23년 이후 모든 제품' |
| `target_region` | VARCHAR(200) | 출시 지역 | '글로벌', 'KR/US/UK' |
| `uses_npu` | CHAR(1) | NPU 사용 여부 | 'O' 또는 공백 |
| `uses_cpu` | CHAR(1) | CPU 사용 여부 | 'O' 또는 공백 |
| `uses_dsp` | CHAR(1) | DSP 사용 여부 | 'O' 또는 공백 |
| `uses_cloud` | CHAR(1) | 클라우드 사용 여부 | 'O' 또는 공백 |
| `ddr_usage_kb` | INTEGER | DDR 메모리 사용량 (KB) | 1024, 2048 |
| `flash_usage_kb` | INTEGER | Flash 메모리 사용량 (KB) | 512, 1024 |
| `is_generative` | CHAR(1) | 생성형 AI 여부 | 'O' 또는 공백 |
| `lineup` | VARCHAR(100) | 적용 제품 라인업 | 'LINE-P', 'LINEP/LINEM' |
| `development_team` | VARCHAR(100) | 개발 주체 | '본사', '해외연 A' |
| `related_links` | VARCHAR(500) | 관련 자료 URL | 'https://abc-tech.com/...' |
| `responsible_department` | VARCHAR(100) | 담당 부서 | 'AI플랫폼팀', '카메라AI팀' |
| `responsible_manager` | VARCHAR(50) | 담당자 | '김태현', '이수민' |
| `created_at` | DATETIME | 데이터 생성일시 | 2024-01-15 10:30:00 |
| `updated_at` | DATETIME | 데이터 수정일시 | 2024-01-15 10:30:00 |

## 3. 예상 질문과 SQL 쿼리

### 자주 묻는 질문들과 해당 SQL 쿼리

| 번호 | 질문 | SQL 쿼리 | 예상 결과 |
|------|------|----------|----------|
| 1 | 카메라 AI 기능은 총 몇 개인가요? | `SELECT COUNT(*) FROM ai_functions WHERE ai_category = '카메라 AI';` | 예: 15개 |
| 2 | 2024년에 도입된 AI 기능들은? | `SELECT ai_function_name, ai_category FROM ai_functions WHERE introduction_year = '24년';` | 스마트 HDR, 실시간 번역 등 |
| 3 | NPU를 사용하는 AI 기능은? | `SELECT ai_function_name FROM ai_functions WHERE uses_npu = 'O';` | 얼굴 인식, 음성 인식 등 |
| 4 | 메모리 사용량이 가장 높은 기능은? | `SELECT ai_function_name, ddr_usage_kb FROM ai_functions ORDER BY ddr_usage_kb DESC LIMIT 5;` | AI 줌: 2048KB 등 |
| 5 | AI플랫폼팀에서 담당하는 기능들은? | `SELECT ai_function_name, ai_category FROM ai_functions WHERE responsible_department = 'AI플랫폼팀';` | 개인화 AI, 성능 최적화 등 |
| 6 | 생성형 AI 기능은 몇 개인가요? | `SELECT COUNT(*) FROM ai_functions WHERE is_generative = 'O';` | 예: 8개 |
| 7 | 글로벌 출시된 기능 중 LINE-P 적용 기능은? | `SELECT ai_function_name FROM ai_functions WHERE target_region = '글로벌' AND lineup LIKE '%LINE-P%';` | 스마트 콜, 야간 모드 등 |
| 8 | 각 카테고리별 평균 메모리 사용량은? | `SELECT ai_category, AVG(ddr_usage_kb) as avg_ddr FROM ai_functions GROUP BY ai_category;` | 카메라 AI: 1024KB 등 |
| 9 | 본사에서 개발한 보안 AI 기능들은? | `SELECT ai_function_name FROM ai_functions WHERE ai_category = '보안 AI' AND development_team = '본사';` | 얼굴 인식, 지문 인식 등 |
| 10 | 2023년 이후 도입된 클라우드 기반 기능은? | `SELECT ai_function_name, introduction_year FROM ai_functions WHERE uses_cloud = 'O' AND introduction_year >= '23년';` | 실시간 번역, 음성 명령 등 |

## 4. 데이터 활용 가이드

### 성능 최적화 팁
- 자주 사용되는 검색 조건에 대해 인덱스 활용
- 대용량 데이터 조회 시 LIMIT 사용 권장
- 메모리 사용량 기반 분석 시 숫자형 컬럼 활용

### 보고서 작성 예시
```sql
-- 연도별 AI 기능 도입 현황
SELECT introduction_year, COUNT(*) as feature_count, 
       AVG(ddr_usage_kb) as avg_memory_usage
FROM ai_functions 
GROUP BY introduction_year 
ORDER BY introduction_year;

-- 부서별 담당 기능 분포
SELECT responsible_department, COUNT(*) as function_count
FROM ai_functions 
GROUP BY responsible_department 
ORDER BY function_count DESC;
```

---
*생성일: 2024년*  
*문서 버전: 1.0*  
*담당: ABC사 AI개발팀*
