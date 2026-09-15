# TEP Digital Twin — 프로젝트 전체 컨텍스트 (웹 Claude 이관용)

이 문서는 로컬 저장소 `C:\TEP-DigitalTwin` (git branch: `dev`, remote 협업자: `yuudong123/TEP-DigitalTwin`)의
문서·설정·소스코드·산출물을 빠짐없이 한 파일로 정리한 것이다. 웹 Claude 등 로컬 파일시스템에
접근할 수 없는 환경에서 이 프로젝트의 맥락을 그대로 이어받기 위해 만들었다.

용량이 매우 큰 반복적 데이터 테이블(수백 행짜리 trajectory/feature 목록 CSV)은 전체를 그대로
옮기는 대신 스키마와 대표 행, 총 행수를 기록했다. 필요하면 로컬 저장소의 해당 경로에서 원본을
그대로 확인할 수 있다.

---

## 목차

1. 프로젝트 개요
2. 디렉터리 구조
3. 현재 개발 상태 (완료/준비/미완료)
4. 프로젝트 문서 원문 (docs/00~10)
5. 설정 및 인프라 파일 (env, requirements, Docker, Compose, Jenkins, 배포 스크립트, gitignore)
6. 소스코드 전체 (src/)
7. 모델 산출물 및 리포트 (models/, reports/)
8. 데이터 메타데이터 스키마 (data/metadata/)
9. 다음 작업자를 위한 핵심 요약

---

## 1. 프로젝트 개요

TEP Run-to-Failure 화학공정 데이터를 실시간으로 스트리밍하고, AI를 이용해 공정의 고장 위험과
잔여수명(RUL)을 예측하며, 데이터 드리프트에 따른 자동 재학습과 디지털트윈 모니터링까지 구현하는
예지보전 시스템이다. 3인 팀 프로젝트이며 `dev`가 팀 통합 브랜치다.

### 주요 기능

- TEP Run-to-Failure 데이터 처리
- XGBoost 기반 RUL 예측
- 4시간 / 2시간 / 1시간 고장 위험 예측
- 시계열 Feature 기반 예측
- TreeSHAP 기반 위험 요인 설명
- Kafka 기반 실시간 데이터 스트리밍
- FastAPI 기반 예측 API
- Web 모니터링 / Unity 디지털트윈
- Drift Detection / 자동 재학습
- Candidate 모델 평가 및 Production 승격
- Docker 기반 서비스 구성 / Jenkins 기반 CI/CD

### 시스템 구조

```text
TEP CSV → Kafka Producer → Kafka → Inference Service → XGBoost Model → FastAPI → Web / Unity
```

MLOps 흐름:

```text
Real-time Data → Drift Monitor → Drift Confirmed → Retraining → Candidate Model
→ Candidate Evaluation → Production Promotion → Inference Model Update
```

CI/CD:

```text
Git Push → GitHub → Jenkins → Docker Build → Development Server Deploy
```

### 현재 Production AI 모델

```text
Version: v1.0.0
Model: XGBoost
Feature Set: Temporal
Feature Count: 728
```

예측 Task: RUL(`rul_hours`), 4시간/2시간/1시간 이내 고장 위험. 모델 위치: `models/production/v1.0.0/`.

### 개발환경

- 권장 Python 3.11
- `python -m venv .venv` → PowerShell: `.\.venv\Scripts\Activate.ps1`
- `python -m pip install -r requirements.txt`
- `Copy-Item .env.example .env` (`.env`는 Git 미포함)
- 공통 Python 설정은 `src/common/config.py`에서 `.env`를 로드

### 데이터/로그 정책

- `data/raw/`, `data/processed/`는 Git 미포함 (용량 문제, 재생성 가능). 데이터 구조/Feature 정의 metadata는 `data/metadata/`에 보관.
- 실행 로그는 `logs/`에 저장(내용은 Git 미포함, `.gitkeep`만 유지). 공통 Logger는 `src/common/logger.py`.

### Git 브랜치 전략

- `main`: 안정 버전
- `dev`: 팀 통합 브랜치이자 기본 개발 기준 브랜치. 실제 기능 개발은 최신 `dev`에서 feature branch 생성 후 PR로 병합.
- 예시 브랜치명: `feat/docker`, `feat/kafka-replay`, `feat/inference`, `feat/web`, `feat/retraining`

---

## 2. 디렉터리 구조

실제 저장소의 전체 파일 트리(`.git` 제외):

```text
TEP-DigitalTwin/
├─ .env.example
├─ .gitignore
├─ compose.yaml
├─ Jenkinsfile
├─ README.md
├─ requirements.txt
├─ data/
│  └─ metadata/
│     ├─ column_summary.csv
│     ├─ feature_schema.csv
│     ├─ split_manifest.csv
│     ├─ temporal_dataset_summary.csv
│     ├─ temporal_feature_schema.csv
│     └─ trajectory_summary.csv
├─ deploy/
│  └─ 09-manual-deploy.sh
├─ docker/
│  ├─ Dockerfile.api
│  ├─ Dockerfile.inference
│  └─ Dockerfile.monitor
├─ docs/
│  ├─ 00-team-roles.md
│  ├─ 01-project-plan.md
│  ├─ 02-tep-data-overview.md
│  ├─ 03-dataset-design.md
│  ├─ 04-baseline-model.md
│  ├─ 05-temporal-features.md
│  ├─ 06-final-model.md
│  ├─ 07-project-structure.md
│  ├─ 08-docker-development.md
│  ├─ 09-manual-deployment.md
│  └─ 10-jenkins-cicd.md
├─ logs/
│  └─ .gitkeep
├─ models/
│  ├─ candidates/
│  │  ├─ 04-baseline/
│  │  │  ├─ model_a/ (rul_hours.json, failure_within_{1,2,4}h.json)
│  │  │  └─ model_b/ (rul_hours.json, failure_within_{1,2,4}h.json)
│  │  └─ 05-temporal/ (rul_hours.json, failure_within_{1,2,4}h.json)
│  └─ production/
│     └─ v1.0.0/
│        ├─ rul_hours.json, failure_within_{1,2,4}h.json
│        ├─ feature_list.json
│        ├─ feature_schema.csv
│        ├─ metadata.json
│        ├─ prediction_schema.json
│        └─ thresholds.json
├─ reports/
│  ├─ 04-baseline/baseline_metrics.csv
│  ├─ 05-temporal/ (comparison_vs_baseline.csv, temporal_metrics.csv, thresholds.json)
│  └─ 06-final-model/sample_prediction.json
└─ src/
   ├─ common/
   │  ├─ 06-create_production_version.py
   │  ├─ 06-save_feature_list.py
   │  ├─ 06-save_prediction_schema.py
   │  ├─ 06-shap_explainer.py
   │  ├─ config.py
   │  └─ logger.py
   ├─ data/
   │  ├─ 02-compare_extra_cases.py
   │  ├─ 02-inspect_tep_h5.py
   │  ├─ 03-build_dataset_manifest.py
   │  ├─ 03-build_processed_dataset.py
   │  ├─ 04-build_feature_schema.py
   │  ├─ 04-inspect_feature_columns.py
   │  └─ 05-build_temporal_features.py
   ├─ evaluation/
   │  ├─ 05-compare_temporal.py
   │  └─ 06-validate_final_prediction.py
   └─ training/
      ├─ 04-train_baseline.py
      └─ 05-train_temporal.py
```

README에 제시된 **최종 목표 구조**(아직 미구현 디렉터리 포함):

```text
TEP_DigitalTwin/
├─ config/
├─ data/ (metadata / processed / raw)
├─ docker/
├─ docs/
├─ logs/
├─ models/ (candidates / production)
├─ notebooks/
├─ reports/
├─ src/
│  ├─ api/         # 미구현
│  ├─ common/
│  ├─ data/
│  ├─ evaluation/
│  ├─ inference/   # 미구현
│  ├─ mlops/       # 미구현
│  ├─ monitoring/  # 미구현
│  ├─ streaming/   # 미구현
│  └─ training/
├─ tests/          # 미구현
├─ unity/          # 미구현
└─ web/            # 미구현
```

`src/api`, `src/inference`, `src/monitoring`, `src/streaming`, `src/mlops`, `tests/`, `unity/`, `web/`,
`config/`, `notebooks/`는 앞으로의 작업(11번 이후 체크리스트)에서 추가될 예정이며 현재 저장소에는 없다.

---

## 3. 현재 개발 상태

완료:

```text
01. 프로젝트 기획
02. TEP 데이터 분석
03. 모델 검증 데이터셋
04. Baseline 모델
05. Temporal Feature 모델
06. 최종 모델 및 설명 기능
07. 프로젝트 기본 구조
```

준비 완료(문서/스크립트/설정 수준, 실제 운영 검증 전):

```text
08. Docker 개발환경 구성
09. 수동 배포 절차 문서·스크립트
10. Jenkins 파이프라인 파일·설정 문서
```

08~10번은 API·inference·monitor 서비스 구현과 배포 대상 컴퓨터(Oracle 무료 서버가 회수되어
현재는 팀원 개인 컴퓨터를 배포 대상으로 대체 예정)에서의 검증이 아직 필요하다.

담당 체크리스트 의존관계(팀 역할 문서 기준):

```text
11 Kafka 재생 → 12 Inference → 13 FastAPI → 14 Web / 15 Unity
                    │
                    └────→ 17 Drift → 18 재학습 → 19 평가·승격 → 20 적용

08 Docker → 16 통합 → 09 수동 배포 → 10 Jenkins
```

역할 분담(3인 팀):

| 담당 | 영역 | 시작 작업 | 이후 작업 |
| --- | --- | --- | --- |
| A | Backend | 11 Kafka 실시간 데이터 재생 | 12 실시간 추론, 13 FastAPI, 16 일부 통합 |
| B | Infrastructure / Operations | 08 Docker 개발환경 유지·보완, 17 Drift 감지 설계 | 09 수동 배포 검증, 10 Jenkins 실운영 설정, 20 모델 적용, 21·16 일부 통합 |
| C | Visualization + Model Lifecycle | 14 Web 화면·모의 데이터 기반 UI, 15 Unity 설계 | 18 자동 재학습, 19 후보 모델 평가·승격, 16 일부 통합 |
| 공통 | 품질·마무리 | 22 테스트 및 장애 대응 | 23 최종 통합, 24 문서화 |

공유해야 하는 산출물:

- A: Kafka topic, 메시지 schema, inference 입력·출력 schema, API contract
- B: Compose 환경변수, 로그·배포 규칙, drift event와 모델 적용 규칙
- C: Web·Unity가 필요한 API 필드, 화면 상태 정의, 재학습·모델 승격 결과 schema

공통 파일(`src/common/config.py`, `src/common/logger.py` 등)을 수정할 때는 영향 범위를 PR에 적고
담당자에게 알린다. 공통 schema, Kafka topic, API contract처럼 다른 작업에 영향을 주는 결정은
문서와 PR에서 먼저 공유한다. 다른 feature branch를 기반으로 새 작업을 시작하지 않는다.

---

## 4. 프로젝트 문서 원문 (docs/00~10)

아래는 `docs/` 디렉터리의 11개 문서 원문을 그대로 옮긴 것이다.

### 4.0 docs/00-team-roles.md — 팀 역할 분담 및 작업 시작 기준

#### 1. 공통 원칙

이 프로젝트는 3인 팀 프로젝트이며, `dev`가 통합 브랜치다.
각 담당자는 최신 `dev`에서 독립 feature branch를 만든 뒤 Pull Request로
병합한다. 다른 feature branch를 기반으로 새 작업을 시작하지 않는다.

공통 schema, Kafka topic, API contract처럼 다른 작업에 영향을 주는 결정은
문서와 Pull Request에서 먼저 공유한다.

#### 2. 담당 범위

| 담당 | 영역 | 시작 작업 | 이후 작업 |
| --- | --- | --- | --- |
| A | Backend | 11 Kafka 실시간 데이터 재생 | 12 실시간 추론, 13 FastAPI, 16 일부 통합 |
| B | Infrastructure / Operations | 08 Docker 개발환경 유지·보완, 17 Drift 감지 설계 | 09 수동 배포 검증, 10 Jenkins 실운영 설정, 20 모델 적용, 21·16 일부 통합 |
| C | Visualization + Model Lifecycle | 14 Web 화면·모의 데이터 기반 UI, 15 Unity 설계 | 18 자동 재학습, 19 후보 모델 평가·승격, 16 일부 통합 |
| 공통 | 품질·마무리 | 22 테스트 및 장애 대응 | 23 최종 통합, 24 문서화 |

#### 3. 바로 시작할 수 있는 작업

**A — Kafka 재생**

- `feat/kafka-replay`에서 11번을 시작한다.
- sensor topic, 메시지 schema, trajectory·case 선택 방식은 구현 전에 문서로 확정한다.
- 12번 inference와 13번 API가 같은 메시지 schema를 사용한다.

**B — 운영 기반 및 Drift 설계**

- Docker Compose는 구성 완료 상태이며, API·inference·monitor 실행 모듈이 구현되면 전체 기동을 다시 검증한다.
- 17번에서는 drift event schema와 재학습 trigger 조건을 먼저 정한다.
- 09·10번의 실제 서버 배포와 Jenkins 검증은 집 컴퓨터를 배포 대상으로 준비한 뒤 진행한다.

**C — Web·Unity 및 모델 생명주기 준비**

- `feat/web-monitoring`, `feat/unity-digital-twin`처럼 작업 단위별 branch에서 UI·레이아웃·모의 데이터 기반 화면을 먼저 구현한다.
- FastAPI endpoint와 응답 schema는 A와 합의한 뒤 실시간 연결한다.
- 18·19번은 B의 drift event와 A의 inference 결과 schema가 확정된 뒤 본격 구현한다.

#### 4. 주요 의존성

```text
11 Kafka 재생 ──→ 12 Inference ──→ 13 FastAPI ──→ 14 Web / 15 Unity
                     │
                     └──────────→ 17 Drift ──→ 18 재학습 ──→ 19 평가·승격 ──→ 20 적용

08 Docker ──→ 16 통합 ──→ 09 수동 배포 ──→ 10 Jenkins
```

09·10번은 배포 대상 컴퓨터가 준비될 때까지 문서·스크립트 수준으로만 완료된 상태다. 08번도 API·inference·monitor 구현 전에는 전체 기동 완료로 체크하지 않는다.

#### 5. 공유해야 하는 산출물

- A: Kafka topic, 메시지 schema, inference 입력·출력 schema, API contract
- B: Compose 환경변수, 로그·배포 규칙, drift event와 모델 적용 규칙
- C: Web·Unity가 필요한 API 필드, 화면 상태 정의, 재학습·모델 승격 결과 schema

공통 파일(`src/common/config.py`, `src/common/logger.py` 등)을 수정할 때는 영향 범위를 Pull Request에 적고 담당자에게 알린다.

---

### 4.1 docs/01-project-plan.md — TEP Digital Twin 프로젝트 기획서

**1. 프로젝트 개요**

TEP Run-to-Failure 화학공정 데이터를 Kafka로 실시간 스트리밍하고, AI를 이용해 공정의 고장 위험과 잔여수명을 예측하며, 데이터 드리프트에 따른 자동 재학습과 Unity 디지털트윈 모니터링까지 구현하는 예지보전 3인 팀 프로젝트.

**2. 프로젝트 목표**

- 공정 센서 데이터 실시간 재생
- 고장 위험 예측 / 잔여수명(RUL) 예측 / 주요 위험 요인 설명
- 데이터 드리프트 감지 / 자동 재학습 / 후보 모델 평가 및 자동 교체
- Unity 기반 공정 시각화
- Git push 기반 개발서버 자동배포

**3. 대상 공정**

TEP 화학공정 전체를 하나의 공정으로 표현한다. 주요 상태 표현 대상: 반응기, 분리기, 정제기.

공정 흐름: 원료 투입 → 반응기 → 응축/냉각 → 분리기 → 정제기 → 제품 생산 (일부 물질은 압축 후 반응기로 재순환).

**4. 사용자 흐름**

1. 사용할 TEP trajectory 선택
2. 시뮬레이션 시작
3. Kafka로 센서값 순차 전송
4. AI 모델 실시간 추론
5. 고장 위험도와 RUL 계산
6. FastAPI를 통해 결과 제공
7. Web과 Unity에서 상태 확인

**5. 시스템 구조**

```text
TEP CSV → Kafka Producer → Kafka → Inference Service → AI Model → FastAPI → Web / Unity
```

별도 MLOps 흐름: 실시간 데이터 → Drift Monitor → Drift 감지 → 재학습 → Candidate Model → 기존 모델 비교 → Production Model 교체

**6. CI/CD 구조**

Git push → GitHub → Jenkins → Docker Build → 개발서버 재배포

Jenkins는 코드 배포 자동화를 담당한다. 모델 재학습과 모델 교체는 Jenkins가 아니라 Python 기반 자체 MLOps 로직에서 처리한다.

**7. 기술 스택**

Python, XGBoost, CUDA, Pandas, NumPy, SHAP, Apache Kafka, FastAPI, pytest, Docker, Docker Compose, Jenkins, Unity, Git/GitHub

**8. 제외 범위**

Airflow, MLflow는 사용하지 않는다. 기능상 필요하지 않기 때문에 자체 Python 기반 구조로 구현한다.

**9. 프로젝트 한 문장 설명**

TEP 기반 실시간 AI 예지보전 및 화학공정 디지털트윈 시스템

---

### 4.2 docs/02-tep-data-overview.md — TEP 데이터 구조 및 고장 시나리오 분석

**1. 문서 목적**: Run-to-Failure 데이터셋의 구조와 변수 역할을 정리하고, 학습에 사용할 변수와 제외할 변수를 결정하기 위한 기준 문서. 하나의 시뮬레이션 단위가 무엇인지, 시간축/RUL 정의, 측정값 vs 제어값 구분, 설비(반응기/분리기/정제기)와 변수 매핑, 열화 시나리오와 운전조건 구분, 데이터 누수 변수 식별이 목적.

**2. 데이터셋 개요**: **Tennessee Eastman Process Run-to-Failure Dataset**. 연속 화학 생산공정을 모사한 시뮬레이션이며, 일반 TEP 이상진단 데이터와 달리 정상 상태부터 시스템 종료까지 전체 수명주기를 생성한 데이터다. 실제 공장 측정값이 아니라 시뮬레이션 데이터. 연구 목적: 상태지표 생성, RUL 예측, 열화/고장 탐지, 설명가능한 예지보전, 여러 설비 동시 열화 상호작용 분석, 유지보수 의사결정 지원. 주요 열화 대상 3개 설비: 반응기, 제품 분리기, 정제기.

**3. 데이터 파일 구조**: `case1.csv`~`case7.csv` (case5_1.csv 포함 총 8개 CSV). 각 파일 58개 컬럼(`Id`, `Time`, 공정 변수 56개). 공식 통합 HDF5(`tep.h5`)에는 case1~case6, 각 100개 독립 Run-to-Failure simulation → 공식 분석 대상 총 600개 trajectory. `case5_1.csv`, `case7.csv`는 별도 생성된 추가 실험 데이터로 정확한 생성 목적 미확인. 재현성과 공식 시나리오 정의 우선을 위해 기본 학습/평가에는 case1~case6만 사용, 나머지는 향후 보조 실험 데이터로 보관.

시나리오별 열화 진행 및 운전 모드:

| 시나리오 | 열화 진행 | 운전 모드 |
|---|---|---|
| 1 | 반응기(상승,느림) → 분리기(상승,중간) | 6 |
| 2 | 반응기(상승,중간) → 정제기(상승,중간) | 4 |
| 3 | 분리기(상승,중간) → 정제기(상승,빠름) | 6 |
| 4 | 반응기(상승,느림) → 분리기(상승,중간) → 정제기(상승,빠름) | 2 |
| 5 | 반응기(하강,느림) → 정제기(하강,중간) → 정제기(상승,높음) | 1 |
| 6 | 분리기(상승,느림) → 정제기(상승,중간) → 분리기(상승,높음) | 5 |

각 시나리오는 첫 설비의 열화가 다른 설비 열화로 이어지는 연쇄적/상호작용형 열화를 포함하며, 시나리오마다 운전 모드가 다르므로 운전조건 차이와 열화 변화를 구분해야 한다.

**데이터 생성 과정**: 공정 초기화 → 약 30시간 안정화 → 정상 운전 → 60~70시간 사이 무작위 시점에 열화 시작 → 반응기/분리기/정제기 중 하나 이상 열화(가속 지수형, 증가/감소 방향, 느림/중간/빠름 속도, 단일 또는 연쇄 열화) → shutdown threshold 도달 시 종료 → 전체 기록을 하나의 trajectory로 저장.

**4. `Id`의 의미**: 하나의 독립적인 Run-to-Failure 시뮬레이션. 다른 파일의 동일 `Id`는 서로 다른 trajectory이므로 프로젝트 내부 고유 ID는 `case1.csv::17` 형태로 생성.

**5. `Time`의 의미**: Run 시작 후 경과 시뮬레이션 시간(hour). 0.05 hour = 3분 간격으로 증가. 기본 샘플링 간격은 3분.

**6. End of Life 정의**: 반응기/분리기/정제기 중 하나가 사전 정의된 임계 운전조건 또는 shutdown threshold에 도달하면 종료. 마지막 관측값이 해당 시뮬레이션의 시스템 EOL. 단, 실제 화학공장의 물리적 고장이 아니라 수정된 TEP 시뮬레이션 모델 내부에 정의된 운전 한계에 따른 EOL이다.

**7. RUL 정의**:

```python
rul_hours = trajectory_end_time - current_time
rul_fraction = rul_hours / trajectory_duration
```

1.0에 가까움 = 수명 초반, 0.0에 가까움 = EOL에 가까움.

**8. 전체 변수 구성**: 공정 관련 56개 변수 = 공정 측정값 + 조작 변수 + 추가 공정 상태 변수. 단순히 "센서 56개"로 부르지 않는다.

**9. 공정 측정 변수(41개, XMEAS)**:
- 유량/공정 측정값: A/D/E 원료 유량, A/C 혼합 원료 유량, 재순환 유량, 반응기 투입 유량
- 반응기: 압력, 액위, 온도
- 배출/분리기: 퍼지 유량, 제품 분리기 온도/액위/압력/하부배출량
- 정제기: 액위, 압력, 하부배출량, 온도, 증기 유량
- 기타 설비: 압축기 부하, 반응기/분리기 냉각수 출구 온도

**10. 성분 분석 측정값**: 반응기 유입(A~F), 퍼지 가스(A~H), 제품 성분(D~H) — 모두 측정 변수로 분류.

**11. 조작 변수(12개, XMV)**: D/E/A 원료 제어, A/C 원료 제어, 압축기 재순환 밸브, 퍼지 밸브, 분리기 액체 배출 제어, 정제기 제품/증기 배출 제어, 반응기/응축기 냉각수 제어, 교반기 제어. `msv` 계열 컬럼에 해당. 제어기가 열화에 보상 동작(밸브 조절)을 늘리면 모델이 이를 이용해 열화를 잘 예측할 수도 있으나, 사용 목적에 따라 입력 허용 여부를 별도 결정해야 한다.

**12. 추가 공정 상태 변수**: `Liquid Input Reactor/Separator/Stripper` — 기존 TEP 41+12 목록에 없는 추가 상태 변수. 최종 입력 사용 전 물리적 의미 추가 확인 필요.

**13. 주요 설비별 변수 매핑**: 반응기(Reactor Pressure/Level/Temperature/Feed Rate/Cooling Water Outlet Temp, 원료 유량/조성, 관련 제어: 원료 공급/Cooling Water/Agitator), 분리기(Product Sep Temp/Level/Pressure/Underflow, Separator Cooling Water Outlet Temp, Liquid Input Separator, 관련 제어: Separator/Condenser Coolant), 정제기(Stripper Level/Pressure/Underflow/Temp/Steam Flow, Liquid Input Stripper, 관련 제어: Stripper/Steam).

**14. 전체 공정 및 보조 변수**: Recycle, Purge, Compressor Work, 제품/퍼지 성분, 공정 유입량 — 특정 설비보다 공정 전체 영향 변수로 별도 표현 가능.

**15. 운전 모드**: 공식 데이터는 6개의 서로 다른 운전 모드를 포함(고장 종류가 아니라 생산 조건). 운전 모드 변화 ≠ 열화. 이 구분은 향후 드리프트 감지에서 중요 — 정상적 운전 모드 변경으로 인한 분포 변화를 드리프트/고장으로 오판하면 안 된다. 8개 CSV와 6개 모드의 정확한 대응은 미확인.

**16. 열화 시나리오**: 총 6개. 단일/2개/3개 설비 동시 열화, 증가/감소 방향, 느림/중간/빠름 속도, 가속 열화, 설비 간 상호작용 조합. 같은 case 내 100개 `Id`도 노이즈·시작시점·속도가 달라 완전히 동일하지 않다.

**17. 현재 미확정 사항**: (17.1) case 파일과 실제 시나리오의 매핑(6개 시나리오 vs 8개 CSV의 차이), (17.2) 각 파일/Run의 운전 모드 대응, (17.3) 설비별 실제 열화 Ground Truth — 현재 CSV에는 `reactor_health`, `separator_health`, `stripper_health`, `reactor_rul` 등 직접 상태 컬럼이 없어 시스템 EOL/RUL은 계산 가능하나 설비별 RUL 지도학습에는 시나리오 메타데이터가 추가로 필요.

**18. 데이터 누수 가능성이 있는 변수**: 위험도 높은 후보 — `Time`, `Id`, source file/case 번호, 계산된 RUL, life fraction, EOL 관련 파생값(특히 `Time`을 입력하면 모델이 센서 패턴 대신 "시간이 지났으니 고장 임박"만 학습할 위험). 별도 검토 대상 — 조작 변수(msv), Liquid Input 계열, 운전 모드 식별 변수.

**19. 모델 입력 기본 원칙**: 우선순위 = 실제 공정 측정값 → 성분 분석값 → 필요 시 조작 변수 추가. Model A(측정값만) vs Model B(측정값+조작 변수) 비교하여 조작 변수 의존도 확인.

**20. 학습/검증 분할 원칙**: 같은 `Id`가 train/test에 동시 포함되면 안 됨. 최소 분할 단위 = `trajectory_key = source_file + Id`. 기본 평가: 처음 보는 trajectory 예측. 강화 평가: Leave-One-Case-Out(하나의 case 전체를 제외하고 학습 후 해당 case 전체를 test) — 이미 사전 검증에서 TEP가 사용 가능한 수준의 일반화 성능을 보임을 확인.

**21. 현재 데이터 구조 결론**: TEP 데이터는 시간 순서 있는 다변량 시계열, 완전한 Run-to-Failure trajectory, 800개 독립 trajectory, 3분 단위 시간축, 시스템 EOL/RUL 계산 가능, 반응기/분리기/정제기 물리 측정값 존재, 설비 간 상호작용·여러 운전조건·여러 열화 패턴 존재, Kafka 순차 재생 가능, 디지털트윈 표시용 물리 센서명 존재 — 조건을 만족하여 기본 데이터셋으로 채택. 단, 설비별 RUL/고장원인 직접 지도학습 전에는 case/열화 시나리오 메타데이터를 먼저 확정해야 한다.

**22. 출처**: Recherche Data Gouv, Tennessee Eastman Process Run-to-Failure Dataset, DOI: `10.57745/1KATN7`; Duc An Nguyen, Khanh T. P. Nguyen, Kamal Medjaher, *Advancing Explainable Prognostics and Health Management: Insights from New Run-to-Failure Data of the Tennessee Eastman Process*, Proceedings of the Institution of Mechanical Engineers, Part O: Journal of Risk and Reliability, 2026; TEP 기본 변수 구조(41 measurement / 12 manipulated variables).

---

### 4.3 docs/03-dataset-design.md — 모델 검증용 데이터셋 설계

**1. 목적**: 학습·검증·테스트 데이터 구성 원칙 정의 — trajectory 데이터 누수 방지, RUL/고장위험 정답 생성 규칙, unseen trajectory vs unseen scenario 평가 분리, 모델 간 비교용 고정 split, 비공식 CSV 분리.

**2. 기본 사용 데이터**: 공식 HDF5의 case1~case6, 각 100개 → 총 600개 독립 trajectory.

**3. 추가 데이터 처리**: `case5_1.csv`, `case7.csv`는 컬럼 구조 동일하지만 공식 HDF5 미포함, 시나리오 정의 미확인 → 기본 학습/검증/테스트 제외, 향후 일반화 테스트/외부 데이터 성격 보조 평가/강건성 검증용으로 별도 사용 가능.

**4. trajectory 식별자**: `trajectory_key = case + "::" + Id` (예: `case1::1`, `case2::1`은 서로 다른 trajectory).

**5. 시간축**: `Time` 단위 hour, 기본 간격 0.05h(3분). 원본 순서 유지, shuffle 금지.

**6. End of Life**: `eol_time = trajectory["Time"].max()`.

**7. RUL target**: `rul_hours = eol_time - current_time`, `rul_fraction = rul_hours / trajectory_duration`.

**8. 고장 위험 target**:

```python
failure_within_4h = int(rul_hours <= 4.0)
failure_within_2h = int(rul_hours <= 2.0)
failure_within_1h = int(rul_hours <= 1.0)
```

**9. 데이터 분할의 최소 단위**: trajectory 전체(행 단위 분할 금지) — 같은 Run을 train/test에 동시에 걸치지 않는다.

**10. 기본 Train/Validation/Test 분할**: case당 100 trajectory를 Train 70 / Validation 15 / Test 15로. 6개 case 전체 = Train 420, Validation 90, Test 90 (총 600).

**11. 분할 재현성**: `RANDOM_STATE = 42`. 결정된 split은 `data/metadata/split_manifest.csv`에 저장하여 모든 모델이 동일 split 사용.

**12. 기본 Test의 목적**: "이미 학습한 열화 시나리오에서 새 trajectory를 예측할 수 있는가?" — 같은 case의 처음 보는 Id를 평가.

**13. Leave-One-Case-Out(LOCO) 검증**: 하나의 case 전체를 test로 제외하고 나머지로 학습, 6개 case에 대해 반복(Fold 1~6). 목적: "학습에서 보지 못한 새로운 열화 시나리오에서도 위험도 구별/RUL 추정이 가능한가?"

**14. Validation의 역할**: hyperparameter 선택, feature 구성 선택, classification threshold 결정, Baseline vs Temporal 비교, 모델 승격 기준. Test로 threshold나 hyperparameter를 결정하지 않는다.

**15. Classification threshold**: 고정 `0.5` 사용 안 함. 이전 LOCO 사전검증에서 AP/ROC-AUC는 높지만 threshold 0.5에서 recall이 낮은 case가 있었음 → threshold는 validation에서 Event Detection Rate, 사전 경고시간, False Alarm Rate, Recall을 함께 고려해 결정. Test에는 validation 결정 threshold를 그대로 적용.

**16. 평가 단위**: Point-level(AP, ROC-AUC, Recall, FPR, MAE, R²) + Event-level(Event Detection Rate, 최초 경고시간, 지속 경고 여부, 고장 이전 False Alarm, trajectory별 최대 위험 확률). 최종 프로젝트 판단에서는 Event-level을 중요하게 본다.

**17. 지속 경고**: 단발성 3분짜리 위험 확률 상승만으로 경고 발생시키지 않음 — 예: 2개 연속 위험 판정(약 6분 지속). 정확한 지속시간은 validation에서 확정. 목적은 일시적 sensor noise로 인한 경고 감소.

**18. 학습 feature에서 제외하는 값**: `Id`, `Time`, `trajectory_key`, case 번호, source filename, EOL time, `rul_hours`, `rul_fraction`, `life_fraction`, failure target. `Time`은 특히 시간 경과만 학습할 위험이 있어 제외.

**19. Baseline feature 정책**: Model A(측정 변수만) vs Model B(측정 변수+조작 변수) 비교 후 최종 feature 구성 결정. 조작 변수 추가 시 성능이 지나치게 상승하면 제어기 보상 행동 의존 여부 확인.

**20. 데이터 정규화**: XGBoost Baseline은 scaling 필수 아님. 신경망/거리 기반 모델 사용 시 별도 scaling 적용, scaler는 반드시 train으로만 fit.

**21. 결측치 처리**: 원본에 결측치 없으면 별도 보간 안 함. 실시간 Kafka 환경의 센서 누락 처리는 서비스 구현 단계에서 별도 정의.

**22. 기본 데이터 해상도**: 원본 3분 간격 유지. Baseline은 현재 시점 값 사용, Temporal Feature는 과거 데이터만 사용한 rolling feature 생성(미래 데이터 절대 사용 금지).

**23. 공식 vs 추가 평가 데이터 구분**: 공식 평가(case1~case6)와 추가 평가(case5_1, case7) 결과를 합산하지 않음. 포트폴리오 주요 성능은 공식 case1~case6 기준.

**24. 데이터셋 생성 결과물**:

```text
data/
├─ raw/
├─ processed/
│  ├─ train.*
│  ├─ validation.*
│  └─ test.*
└─ metadata/
   ├─ split_manifest.csv
   ├─ feature_schema.csv
   └─ trajectory_summary.csv
```

대용량 데이터는 CSV보다 Parquet 우선 검토.

**25. 최종 원칙**(10가지): (1) 하나의 trajectory는 하나의 split에만 존재. (2) Test 정보를 학습/threshold 결정에 사용 안 함. (3) RUL은 실제 trajectory EOL로부터 계산. (4) 고장 위험 target은 EOL까지 남은 시간으로 계산. (5) `Time`과 RUL 관련 정답 정보는 feature에서 제외. (6) 모든 모델은 동일 split에서 비교. (7) unseen trajectory 성능과 unseen scenario 성능을 따로 평가. (8) 공식 6개 scenario와 추가 CSV 결과를 섞지 않음. (9) Point metric뿐 아니라 Event metric 반드시 사용. (10) 시계열 feature에는 현재와 과거 데이터만 사용.

**26. 실제 데이터셋 생성 결과**: 공식 case1~case6, 총 600 trajectory 검증. 결측치 없음, infinite value 없음, trajectory 내부 중복 timestamp 없음, 모든 sampling interval 0.05h(3분), `Agitator` 컬럼은 전체 데이터에서 100으로 고정된 상수여서 feature 제외.

| Split | Trajectory 수 |
|---|---:|
| Train | 420 |
| Validation | 90 |
| Test | 90 |

가공 데이터는 Parquet 저장(`data/processed/{train,validation,test}.parquet`). 고장 위험 target의 positive 비율:

| Target | Train | Validation | Test |
|---|---:|---:|---:|
| 4시간 이내 고장 | 3.0204% | 3.0290% | 3.0197% |
| 2시간 이내 고장 | 1.5287% | 1.5332% | 1.5281% |
| 1시간 이내 고장 | 0.7829% | 0.7853% | 0.7823% |

---

### 4.4 docs/04-baseline-model.md — AI Baseline 모델

**1. 목적**: 시계열 Feature Engineering 적용 전, 현재 시점 공정 변수만으로 RUL/고장위험 예측이 어느 정도 가능한지 확인하는 첫 정식 Baseline 구축. 이후 Temporal 모델의 비교 기준으로 사용.

**2. 학습 알고리즘**: XGBoost, NVIDIA CUDA(`tree_method="hist"`, `device="cuda"`).

**3. 입력 Feature 구성**:
- **Model A**: 41개 XMEAS 측정 변수만.
- **Model B**: 41 XMEAS + 11 유효 XMV(`Agitator`는 상수라 제외) = 52 features.

**4. Baseline 제외 변수**: `Id`, `Time`, `case`, `trajectory_key`, `rul_hours`, `rul_fraction`, `failure_within_{4,2,1}h`, `Agitator`, `Liquid Input Stripper/Separator/Reactor`(추가 RTF 변수, 열화 누수 가능성).

**5. 예측 문제**: RUL 회귀(`rul_hours`), 4h/2h/1h 고장 위험 분류. Model A/B × 4 targets = 총 8 models.

**6. 학습 데이터**: Train 420 / Validation 90 / Test 90 trajectory, `data/processed/{train,validation,test}.parquet`.

**7. Validation 사용**: Early Stopping, threshold 결정, Model A/B 비교, 모델 선택. Test는 학습/threshold 결정에 미사용.

**8. Classification threshold**: Validation의 Precision-Recall 곡선에서 F1 최댓값 지점 선택(고정 0.5 미사용, ranking 성능은 높지만 0.5에서 recall이 낮아지는 경우가 있었기 때문).

**9. Class imbalance**: `scale_pos_weight = negative/positive` (train 기준) 적용.

**10. RUL 평가 지표**: MAE(주요 기준), Median AE, RMSE, R². 예측값이 음수면 평가 시 0으로 clip.

**11. 고장 위험 Point-level 평가**: Average Precision(중요), ROC-AUC, Precision, Recall, F1, FPR — imbalance가 크므로 Accuracy는 사용 안 함.

**12. Event-level 평가**: 2개 연속 시점 threshold 초과 시 지속 경고(약 6분). Event Detection Rate, 최초 지속경고 RUL, Median Warning Lead Time, horizon 이전 조기경고(`early alert`, 별도 기록, 반드시 오경보는 아님).

**13. Baseline 확률값의 의미**: `scale_pos_weight` 보정 적용했으므로 출력을 완전 보정된 확률로 단정하지 않고 `risk score`로 취급. 필요 시 최종 모델 단계에서 calibration 추가.

**14. 모델 저장**: `models/candidates/04-baseline/{model_a,model_b}/{rul_hours,failure_within_4h,failure_within_2h,failure_within_1h}.json`, 결과는 `reports/04-baseline/baseline_metrics.csv`.

**15. 완료 기준**(8개): CUDA 정상 학습, Model A 4개 모델 생성, Model B 4개 모델 생성, Validation 기반 threshold 생성, Test 성능 평가, Point/Event-level 결과 저장, A/B 성능 차이 분석, 이후 Temporal 모델의 Baseline 성능 확정.

**16. 실제 Baseline 학습 결과** — 총 8개 모델 학습 완료.

RUL 예측:

| Feature 구성 | Test MAE | Median AE | RMSE | R² |
|---|---:|---:|---:|---:|
| Model A - XMEAS 41개 | 3.206 h | 2.065 h | 4.975 h | 0.9839 |
| Model B - XMEAS 41개 + XMV 11개 | **3.045 h** | **1.987 h** | **4.693 h** | **0.9857** |

Model B가 Model A 대비 RUL MAE 약 5% 개선.

고장 위험 예측:

| Horizon | Model | AP | Precision | Recall | F1 | Point FPR |
|---|---|---:|---:|---:|---:|---:|
| 4h | A | 0.9902 | 0.9319 | 0.9638 | 0.9476 | 0.00219 |
| 4h | B | **0.9907** | **0.9523** | 0.9553 | **0.9538** | **0.00149** |
| 2h | A | 0.9744 | 0.8551 | 0.9694 | 0.9086 | 0.00255 |
| 2h | B | **0.9775** | **0.8669** | **0.9713** | **0.9161** | **0.00231** |
| 1h | A | 0.9381 | 0.7968 | 0.9576 | 0.8699 | 0.00193 |
| 1h | B | **0.9418** | **0.7990** | **0.9582** | **0.8714** | **0.00190** |

모든 고장 위험 모델이 Test 90 trajectory에서 지속 경고 기준 100% Event Detection Rate 기록.

**Baseline 대표 모델**: Model B(XMEAS 41 + XMV 11 = 52 features)를 대표 Baseline으로 선정 — 제어 변수 추가 시 RUL/고장위험 성능이 소폭 개선되고 비정상적으로 큰 상승은 없었음.

Baseline 기준 성능:

| Task | Baseline |
|---|---:|
| RUL MAE | 3.045 h |
| RUL R² | 0.9857 |
| 4h AP | 0.9907 |
| 2h AP | 0.9775 |
| 1h AP | 0.9418 |

---

### 4.5 docs/05-temporal-features.md — 시계열 Feature 모델

**1. 목적**: Baseline(현재값만)에서 최근 값의 변화 방향/속도/변동성/추세를 Feature로 추가해 동일 split·XGBoost로 성능 향상이 복잡도 증가를 정당화하는지 평가.

**2. 비교 대상**: Baseline Model B(52 features) — 위 4.4절 기준 성능표와 동일.

**3. Sampling Interval**: 0.05h=3분. 15분=5 interval, 30분=10, 60분=20. 5분 전 값은 정확한 샘플이 없어 3분 전·6분 전 값의 선형보간으로 추정(과거 데이터만 사용).

**4. 현재값**: Baseline Model B와 동일 52개.

**5. 과거 5분 Feature**: 5분 전 값 선형보간 후 변화량(`현재값 - 5분 전 추정값`), 변화속도(`변화량 / (5/60h)`). 52×2=104 features.

**6. 과거 15분 Feature**: 이동평균, 표준편차, 변화량, 변화속도. 52×4=208 features.

**7. 과거 30분 Feature**: 이동평균, 표준편차, 최대값, 최소값. 52×4=208 features.

**8. 과거 60분 Feature**: 변화량, 변화속도, 선형 기울기(60분 구간 전체에 회귀선 적용, 처음/끝값만 비교 안 함). 52×3=156 features.

**9. 전체 Feature 수**:

| 종류 | Feature 수 |
|---|---:|
| 현재값 | 52 |
| 5분 | 104 |
| 15분 | 208 |
| 30분 | 208 |
| 60분 | 156 |
| **총계** | **728** |

모든 종류를 모든 window와 조합하지 않고, 단기 변화·중기 변동성·장기 추세를 균형있게 구성.

**10. Warm-up**: 가장 긴 window 60분(20 rows) → 각 trajectory 처음 20 row는 Temporal 데이터에서 제외.

**11. 미래 데이터 누수 방지**: 허용 = t, t-3m..t-60m. 금지 = t+3m 이후. Feature 생성 후 leakage validation 수행(전체 trajectory로 생성 vs 특정 시점까지 잘라서 생성 비교, 미래값 인위 변경 시 현재 feature 불변 확인).

**12. 출력**: `data/processed/temporal/{train,validation,test}.parquet`, feature 정의 `data/metadata/temporal_feature_schema.csv`, 생성 결과 `data/metadata/temporal_dataset_summary.csv`.

**13. 모델**: RUL 회귀, 4h/2h/1h 고장위험 — 동일 XGBoost CUDA 환경. threshold는 Validation에서 결정.

**14. 최종 판단 기준**: RUL MAE/R², AP, Recall, FPR, Event Detection Rate, Warning Lead Time, Feature 수, 학습시간, 실시간 계산 비용을 종합 판단(단순 성능 향상만으로 채택하지 않음. Feature 수 52→728 증가의 운영 복잡도 정당화 여부 함께 판단).

**15. 실제 학습 결과** — 728 Temporal features로 학습.

RUL 성능:

| 지표 | Baseline Model B | Temporal | 변화 |
|---|---:|---:|---:|
| MAE | 3.045 h | **2.188 h** | **28.1% 개선** |
| Median AE | 1.987 h | **1.531 h** | 23.0% 개선 |
| RMSE | 4.693 h | **3.248 h** | 30.8% 개선 |
| R² | 0.9857 | **0.9930** | 개선 |

고장 위험 성능:

| Horizon | 지표 | Baseline Model B | Temporal |
|---|---|---:|---:|
| 4h | AP | 0.9907 | **0.9948** |
| 4h | F1 | 0.9538 | **0.9619** |
| 2h | AP | 0.9775 | **0.9833** |
| 2h | F1 | 0.9161 | **0.9276** |
| 1h | AP | 0.9418 | **0.9648** |
| 1h | F1 | 0.8714 | **0.8993** |

모든 horizon에서 Test Event Detection Rate 100% 유지. Median Warning Lead Time: 4h→4.0h, 2h→2.0h, 1h→1.0h.

**16. 복잡도 대비 성능 판단**: Feature 수 약 14배 증가(52→728)했으나 RUL MAE 약 28.1%, RMSE 약 30.8% 감소, 모든 horizon AP 개선(특히 1h는 0.9418→0.9648), Event Detection Rate 100% 유지, 2h/1h Point FPR 감소. RUL 정확도가 핵심 기능이라는 점을 고려하면 복잡도 증가를 감수할 가치가 있다고 판단 → **최종 모델 후보는 Temporal Feature 모델로 선정**(단, 728개 전체를 그대로 운영에 쓸지는 SHAP 분석으로 추가 검토).

---

### 4.6 docs/06-final-model.md — 최종 모델 선정 및 설명 기능

**1. 최종 RUL 모델**: 728 Temporal features XGBoost 선정.

| 모델 | Feature 수 | Test MAE | Test R² |
|---|---:|---:|---:|
| Baseline Model B | 52 | 3.0446 h | 0.9857 |
| Temporal XGBoost | 728 | **2.1877 h** | **0.9930** |

**2. 최종 고장 위험 모델**: 4h/2h/1h 모두 Temporal XGBoost로 선정.

| Horizon | Baseline AP | Temporal AP | Baseline F1 | Temporal F1 |
|---|---:|---:|---:|---:|
| 4시간 | 0.9907 | **0.9948** | 0.9538 | **0.9619** |
| 2시간 | 0.9775 | **0.9833** | 0.9161 | **0.9276** |
| 1시간 | 0.9418 | **0.9648** | 0.8714 | **0.8993** |

모든 horizon에서 Baseline 대비 AP/F1 개선, Event Detection Rate 100% 유지.

**3. 최종 Threshold 확정**(Validation의 F1 최댓값 기준):

| Target | Threshold |
|---|---:|
| 4시간 이내 고장 위험 | 0.622766 |
| 2시간 이내 고장 위험 | 0.610441 |
| 1시간 이내 고장 위험 | 0.783028 |

`reports/05-temporal/thresholds.json`에 저장. XGBoost 분류 모델은 imbalance 보정을 적용했으므로 출력값은 보정된 실제 확률이 아니라 `risk score`로 취급.

**4. 모델 저장 형식**: XGBoost JSON. 4개 파일 `rul_hours.json`, `failure_within_4h.json`, `failure_within_2h.json`, `failure_within_1h.json`. `Booster.load_model()`로 직접 로드 가능하며 candidate/production 파일 단위 비교·교체에 적합. 최종 production은 `models/production/v1.0.0/`.

**5. 모델 버전 관리**: 최초 버전 `v1.0.0`. 각 버전에 `metadata.json` 저장(버전, 생성시각, git commit, 알고리즘, feature 구성/개수, sampling interval, warm-up, 학습 case, 모델 파일명, threshold, test 성능, candidate 출처) — 추론/모델 교체 시 추적 가능하도록.

**6. Feature 목록 저장**: `models/production/v1.0.0/feature_list.json`(정확한 입력 순서), `feature_schema.csv`(feature 이름/원본 변수/변환 종류/시간 window). 실시간 추론은 `feature_list.json` 순서로 728개 입력 구성.

**7. SHAP 설명 기능**: XGBoost TreeSHAP으로 각 feature의 기여도 계산. `SHAP > 0` = 위험 증가 방향, `SHAP < 0` = 감소 방향, `|SHAP|` 클수록 영향 큼. 모든 기여도 합 + base value가 raw prediction과 일치하는지 additivity 검증. 분류 모델 SHAP은 raw margin 기여도이므로 실제 확률 변화량으로 직접 해석하지 않음.

**8. 주요 위험 요인 출력 형식**: 현재 상태에 따라 설명 대상 모델 결정 — `CRITICAL→1h 모델`, `WARNING→2h 모델`, `CAUTION→4h 모델`, `NORMAL→4h 모델`. SHAP 값이 양수인 feature 중 위험도를 가장 크게 증가시킨 상위 5개를 사용. 각 위험 요인 = `rank, feature, source_feature, transform, window_minutes, shap_value`.

**9. 최종 예측 결과 Schema**:

```text
model_version
trajectory_key
timestamp_hours

rul
└─ hours

risk
├─ failure_within_4h { score, threshold, alert }
├─ failure_within_2h { score, threshold, alert }
└─ failure_within_1h { score, threshold, alert }

status
explanation_model

top_risk_factors
├─ rank
├─ feature
├─ source_feature
├─ transform
├─ window_minutes
└─ shap_value
```

공정 상태 판정 우선순위: `1h threshold 이상 → CRITICAL`, `2h threshold 이상 → WARNING`, `4h threshold 이상 → CAUTION`, `모두 미만 → NORMAL`. 각 classification 출력값은 실제 보정 확률이 아닌 `risk score`.

**10. Section 6 완료 검증**: Production 모델 한 입력에 대해 RUL, 4h/2h/1h 고장위험, 공정 상태, SHAP 기반 주요 위험 요인을 동시에 생성하는 통합 검증 완료 — 결과는 `reports/06-final-model/sample_prediction.json`(§7 참조)에 저장, 실시간 Inference/FastAPI 예측 출력 계약으로 확정.

---

### 4.7 docs/07-project-structure.md — 프로젝트 기본 구조

**1. 목적**: 3인 팀이 같은 규칙으로 개발하고 이후 Kafka·추론·API·모니터링 서비스를 독립적으로 추가할 수 있도록 저장소 기본 구조와 공통 파일 역할 정리.

**2. 디렉터리 구조**(요약, §2 전체 트리 참고):

```text
TEP-DigitalTwin/
├─ data/             # 원본·가공 데이터와 공통 metadata
├─ deploy/           # 개발서버 수동 배포 스크립트
├─ docker/           # 서비스별 Dockerfile
├─ docs/             # 번호별 작업 문서
├─ logs/             # 실행 로그 (내용은 Git 제외)
├─ models/           # candidate·production 모델
├─ reports/          # 데이터·모델 검증 결과
├─ src/
│  ├─ common/        # 설정, logger, 모델 공통 유틸리티
│  ├─ data/          # 데이터 탐색·가공·feature 생성
│  ├─ training/      # 모델 학습
│  └─ evaluation/    # 검증 및 모델 비교
├─ compose.yaml      # Kafka·API·inference·monitor 개발환경
├─ requirements.txt  # Python 의존성
└─ .env.example      # 공유 가능한 환경변수 기본값
```

`src/api`, `src/inference`, `src/monitoring`, `src/streaming` 등은 이후 번호 작업에서 추가한다. README의 최종 목표 구조에 이 디렉터리가 보이더라도 현재는 아직 구현 전이다.

**3. 공통 설정 규칙**: 실제 실행값은 루트 `.env`(Git 미포함), 공유 가능한 키/기본값은 `.env.example`에만. Python 코드는 `src/common/config.py`로 환경변수를 읽음. 공통 재사용 설정/logger/모델 유틸리티는 번호 파일명 대신 `src/common/`에. 작업 산출물은 공통 라이브러리가 아닌 한 `04-train_baseline.py`처럼 체크리스트 번호를 파일명 앞에 붙인다.

**4. Git 협업 규칙**: `dev`는 팀 통합 브랜치. 새 작업은 최신 `dev`에서 독립 feature branch 생성 후 PR로 병합.

```text
dev
├─ feat/docker              # 08번 Docker 개발환경
├─ feat/manual-deployment   # 09번 수동 배포 절차
└─ feat/jenkins-cicd        # 10번 Jenkins 파이프라인
```

feature branch는 서로의 미병합 변경을 포함하지 않는다. 공통 기반이 필요하면 먼저 해당 PR을 `dev`에 병합한 뒤 최신 `dev`에서 새 branch를 만든다.

**5. 개발환경 재현**: 프로젝트 루트 `.venv` 사용(전역 Python에 설치 금지).

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

현재 API·inference·monitor 실행 모듈은 구현 전이므로 Compose 전체 정상 기동은 아직 완료 기준 미통과.

---

### 4.8 docs/08-docker-development.md — Docker 개발환경

**1. 목적**: Kafka, API, inference, monitoring 서비스를 동일 Docker Compose 네트워크에서 실행하는 개발환경 공통 규칙 정의.

**2. 서비스 구성**:

| 서비스 | 역할 | 컨테이너 이름 |
| --- | --- | --- |
| `kafka` | 센서·예측·드리프트 이벤트 메시지 브로커 | `tep-kafka` |
| `api` | 외부 조회용 FastAPI 서비스 | `tep-api` |
| `inference` | Kafka 센서 메시지 기반 실시간 추론 | `tep-inference` |
| `monitor` | 드리프트 감시와 재학습 트리거 | `tep-monitor` |

모든 서비스는 `tep-network` bridge 네트워크 사용. 애플리케이션 컨테이너는 Kafka healthcheck 성공 후 시작.

**3. 환경변수 관리**: 저장소엔 `.env.example`만 공유 기본값 포함, 실제 실행값은 Git 미포함 `.env`. `compose.yaml`은 각 애플리케이션 서비스에 `env_file: .env` 적용. 컨테이너 내부 Kafka 주소는 서비스 DNS `kafka:9092`로 덮어씀. 첫 실행 전 `Copy-Item .env.example .env`.

**4. 모델 공유 방식**: 개발환경에서는 호스트 `./models`를 세 애플리케이션 컨테이너에 `/app/models`로 읽기 전용 마운트. API/inference/monitor가 동일 production 모델 버전을 읽고, 호스트에서 버전 변경 시 이미지 재빌드 없이 반영(hot reload 정책은 20번에서 결정). 읽기 전용 마운트로 서비스가 production 모델을 덮어쓰지 못하게 함. Dockerfile의 `COPY models`는 Compose 없이 단독 실행할 때를 위한 기본 포함본으로 유지(Compose 실행 시 공유 마운트가 대체).

**5. 로그 구조와 확인 방법**: 호스트 `./logs`를 각 컨테이너 `/app/logs`에 마운트. 표준 출력은 `docker compose logs --follow {kafka,api,inference,monitor}`, 파일 로그는 `logs/`에서 서비스별 파일명으로 확인(Git 미포함, `.gitkeep`만 유지).

**6. 현재 검증 상태**: `docker compose config`와 `docker compose up --build -d`로 문법·환경변수·볼륨·빌드·기동 확인. `tep-kafka`는 healthcheck 통과해 `healthy` 상태. API/inference/monitor 이미지는 정상 빌드되나 아직 구현되지 않은 실행 모듈 때문에 컨테이너가 재시작함(Docker 설정 오류가 아니라 서비스 구현이 아직 없는 현재 단계의 결과). 전체 기동 검증 통과를 위해 필요한 것: (1) Docker Desktop/Engine 실행, (2) 12번 inference 구현, (3) 13번 FastAPI 구현, (4) 17번 monitor 구현 또는 임시 실행 정책 결정. 따라서 현재는 Docker 개발환경 구성 규칙까지 완료, `docker compose up -d` 최소 시스템 실행 완료 기준은 미체크.

---

### 4.9 docs/09-manual-deployment.md — 개발서버 수동 배포

**1. 목적**: Oracle Cloud 개발서버(주: 이후 Oracle 무료 서버가 회수되어 현재는 팀원 개인 컴퓨터를 배포 대상으로 대체할 예정 — README 최근 커밋 메모 참고)에 프로젝트를 수동 배포하고 Docker Compose 기반 서비스를 운영하는 표준 절차. 3인 팀이 같은 서버 절차와 환경변수 규칙을 사용하도록 하는 운영 기준.

**2. 배포 전제조건**: Oracle Cloud 개발서버 접근 권한, Git·Docker Engine·Docker Compose v2, Docker daemon 접근 가능한 배포 사용자, GitHub 저장소 읽기 권한, 서버 전용 `.env` 값. 민감한 값/서버별 주소는 저장소에 넣지 않고 `.env.example`을 복사해 서버 환경에 맞게 `.env` 작성.

```bash
cp .env.example .env
chmod 600 .env
```

**3. 최초 배포**:

```bash
git clone https://github.com/yuudong123/TEP-DigitalTwin.git
cd TEP-DigitalTwin
git switch dev
cp .env.example .env
```

`.env` 최소 확인 대상: `APP_ENV=development`, `API_PORT`, `KAFKA_*` topic/consumer group, `MODEL_VERSION`/`MODEL_DIR`, `DATA_*_DIR`, `LOG_DIR`.

```bash
bash deploy/09-manual-deploy.sh
# 또는
PROJECT_DIR=/opt/tep-digitaltwin bash deploy/09-manual-deploy.sh
```

**4. 코드 갱신 배포**:

```bash
git status --short
git pull --ff-only origin dev
bash deploy/09-manual-deploy.sh
```

`--ff-only`로 서버에서 의도치 않은 병합 커밋 방지.

**5. 배포 후 확인**:

```bash
docker compose ps --all
docker compose logs --tail 100 kafka
docker compose logs --tail 100 api inference monitor
```

서비스 구현 완료 후에는 FastAPI endpoint 응답, Kafka topic 생성/송수신, 서버 재부팅 뒤 재기동도 확인.

**6. 현재 제한 사항**: Docker Engine 연결, 이미지 빌드, Kafka healthcheck는 로컬에서 검증됨. API/inference/monitor 실행 모듈은 각각 13/12/17번에서 구현 예정이므로 현재는 전체 서비스가 정상 기동하지 않음. 이 문서는 절차·검증 도구를 제공하지만, 체크리스트 09 서버 배포 완료 항목은 실제 Oracle 개발서버에서 전체 서비스를 기동·검증한 뒤에만 완료 처리.

---

### 4.10 docs/10-jenkins-cicd.md — Jenkins 기본 CI/CD

**1. 목적**: 3인 팀의 `dev` 브랜치 변경을 Jenkins가 검증하고 개발서버에 배포하는 기본 CI/CD 흐름 정의. 모델 재학습과 production 모델 승격은 Jenkins가 아닌 이후 Python MLOps 작업에서 담당.

**2. 파이프라인 원칙**: 루트 `Jenkinsfile`은 Multibranch Pipeline 기준.

| 대상 브랜치 | 수행 작업 |
| --- | --- |
| 모든 감지 브랜치 | checkout, Compose 구성 검증, 가능한 경우 테스트 |
| `dev` | 위 검증 후 Docker 이미지 빌드 및 개발서버 배포 |

배포 단계는 `dev`에만 적용(기능 브랜치/PR이 개발서버를 덮어쓰지 않도록). 동시 배포 방지를 위해 `disableConcurrentBuilds()` 적용.

**3. Jenkins 서버 준비**: Jenkins는 개발서버 또는 Docker daemon 접근 가능한 전용 agent에서 실행. 필요 항목: Git, Docker Engine/Compose v2, Docker daemon 접근 권한, `tep-development-env` 이름의 Secret file credential, (선택) 테스트용 프로젝트 `.venv`. Jenkins는 패키지 설치나 가상환경 생성을 하지 않으며, 프로젝트 `.venv/bin/python`이 존재할 때만 해당 가상환경으로 `pytest` 실행.

**4. Jenkins Job 설정**: (1) Multibranch Pipeline Job 생성. (2) GitHub 저장소 `yuudong123/TEP-DigitalTwin`를 branch source로 연결. (3) Pipeline 정의는 저장소의 `Jenkinsfile` 사용. (4) 서버용 `.env`를 Jenkins Secret file credential(ID: `tep-development-env`)로 등록 — Jenkinsfile은 빌드 중에만 작업 경로의 `.env`로 복사, 빌드 종료 시 삭제. (5) `dev` 브랜치 검색 및 최초 빌드 실행. GitHub access token, Jenkins credential, 서버 주소는 Jenkins Credentials 또는 서버 환경설정에만 보관.

**5. GitHub Webhook 설정**: 저장소 Settings → Webhooks에서 `https://<jenkins-host>/github-webhook/` 추가. Content type `application/json`, Event `Just the push event`, Secret은 Jenkins와 GitHub에 동일 값. 설정 후 `dev`에 테스트 push하여 branch 감지/실행 로그 확인.

**6. 실패 처리와 로그**: 파이프라인 실패 시 Jenkins console log에 Compose 서비스 상태와 최근 컨테이너 로그 기록. 배포 후 운영 로그는 `docker compose ps --all`, `docker compose logs --tail 100 kafka`, `docker compose logs --tail 100 api inference monitor`로 추가 확인.

**7. 현재 완료 범위**: 저장소 내부에는 Jenkinsfile과 배포 연동 규칙 준비 완료. Jenkins 설치, GitHub credential/Webhook 등록, 실제 `dev` push 감지와 개발서버 배포는 Jenkins 및 Oracle 개발서버 접근 권한이 있어야 검증 가능. API/inference/monitor 구현 전에는 Compose 전체 기동이 실패하므로, 10번 체크리스트의 실제 배포 완료 항목은 해당 서비스 구현과 서버 검증 뒤에 완료 처리.

---

## 5. 설정 및 인프라 파일

### 5.1 requirements.txt

```text
numpy==2.4.6
pandas==3.0.5
h5py==3.16.0
pyarrow==25.0.1
scikit-learn==1.9.0
xgboost==3.2.0
python-dotenv==1.2.3
```

### 5.2 .env.example

```dotenv
# ============================================================
# Application
# ============================================================

APP_ENV=development
LOG_LEVEL=INFO


# ============================================================
# Kafka
# ============================================================

KAFKA_BOOTSTRAP_SERVERS=localhost:9092

KAFKA_SENSOR_TOPIC=tep-sensor-data
KAFKA_PREDICTION_TOPIC=tep-predictions
KAFKA_DRIFT_TOPIC=tep-drift-events

KAFKA_CONSUMER_GROUP=inference-service


# ============================================================
# TEP Replay
# ============================================================

TEP_REPLAY_SPEED=1.0
TEP_REPLAY_INTERVAL_SECONDS=0.1


# ============================================================
# Inference
# ============================================================

MODEL_VERSION=v1.0.0
MODEL_DIR=models/production/v1.0.0

TEMPORAL_WARMUP_MINUTES=60

RISK_THRESHOLD_4H=0.622766
RISK_THRESHOLD_2H=0.610441
RISK_THRESHOLD_1H=0.783028


# ============================================================
# FastAPI
# ============================================================

API_HOST=0.0.0.0
API_PORT=8000


# ============================================================
# Monitoring / Drift
# ============================================================

DRIFT_CHECK_ENABLED=true
DRIFT_CHECK_INTERVAL_SECONDS=60


# ============================================================
# Retraining
# ============================================================

RETRAIN_ENABLED=true

CANDIDATE_MODEL_DIR=models/candidates
PRODUCTION_MODEL_DIR=models/production


# ============================================================
# Paths
# ============================================================

DATA_RAW_DIR=data/raw
DATA_PROCESSED_DIR=data/processed
DATA_METADATA_DIR=data/metadata

REPORT_DIR=reports
LOG_DIR=logs
```

### 5.3 compose.yaml

```yaml
services:
  kafka:
    image: apache/kafka:4.1.0
    container_name: tep-kafka

    ports:
      - "9092:9092"

    healthcheck:
      test:
        [
          "CMD-SHELL",
          "/opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list > /dev/null 2>&1"
        ]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 20s

    restart: unless-stopped

    networks:
      - tep-network


  api:
    build:
      context: .
      dockerfile: docker/Dockerfile.api

    container_name: tep-api

    env_file:
      - .env

    environment:
      KAFKA_BOOTSTRAP_SERVERS: kafka:9092

    ports:
      - "${API_PORT:-8000}:${API_PORT:-8000}"

    depends_on:
      kafka:
        condition: service_healthy

    volumes:
      - ./models:/app/models:ro
      - ./logs:/app/logs

    restart: unless-stopped

    networks:
      - tep-network


  inference:
    build:
      context: .
      dockerfile: docker/Dockerfile.inference

    container_name: tep-inference

    env_file:
      - .env

    environment:
      KAFKA_BOOTSTRAP_SERVERS: kafka:9092

    depends_on:
      kafka:
        condition: service_healthy

    volumes:
      - ./models:/app/models:ro
      - ./logs:/app/logs

    restart: unless-stopped

    networks:
      - tep-network


  monitor:
    build:
      context: .
      dockerfile: docker/Dockerfile.monitor

    container_name: tep-monitor

    env_file:
      - .env

    environment:
      KAFKA_BOOTSTRAP_SERVERS: kafka:9092

    depends_on:
      kafka:
        condition: service_healthy

    volumes:
      - ./models:/app/models:ro
      - ./logs:/app/logs

    restart: unless-stopped

    networks:
      - tep-network


networks:
  tep-network:
    name: tep-network
    driver: bridge
```

### 5.4 docker/Dockerfile.api

```dockerfile
# docker build -f docker\Dockerfile.api -t tep-api:dev .
# docker images tep-api

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY models ./models
COPY data/metadata ./data/metadata

ENV PYTHONPATH=/app

CMD ["python", "-m", "src.api.main"]
```

### 5.5 docker/Dockerfile.inference

```dockerfile
# docker build -f docker\Dockerfile.inference -t tep-inference:dev .
# docker images tep-inference

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY models ./models
COPY data/metadata ./data/metadata

ENV PYTHONPATH=/app

CMD ["python", "-m", "src.inference.main"]
```

### 5.6 docker/Dockerfile.monitor

```dockerfile
# docker build -f docker\Dockerfile.monitor -t tep-monitor:dev .
# docker images tep-monitor

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY models ./models
COPY data/metadata ./data/metadata

ENV PYTHONPATH=/app

CMD ["python", "-m", "src.monitoring.main"]
```

> 참고: 위 세 Dockerfile 모두 `src.api.main` / `src.inference.main` / `src.monitoring.main`을 CMD로 지정하지만, 이 모듈들은 아직 저장소에 구현되어 있지 않다(§3 현재 개발 상태 참고). 현재 이 이미지들은 빌드는 되지만 컨테이너 실행은 재시작을 반복한다.

### 5.7 deploy/09-manual-deploy.sh

```bash
#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
COMPOSE_FILE="${PROJECT_DIR}/compose.yaml"
ENV_FILE="${PROJECT_DIR}/.env"

fail() {
    echo "[ERROR] $*" >&2
    exit 1
}

require_command() {
    command -v "$1" >/dev/null 2>&1 \
        || fail "Required command not found: $1"
}

require_command docker

docker compose version >/dev/null 2>&1 \
    || fail "Docker Compose v2 is required."

docker info >/dev/null 2>&1 \
    || fail "Docker daemon is unavailable or the current user lacks Docker access."

[[ -f "${COMPOSE_FILE}" ]] \
    || fail "compose.yaml not found: ${COMPOSE_FILE}"

[[ -f "${ENV_FILE}" ]] \
    || fail ".env not found. Copy .env.example and set server values first."

cd "${PROJECT_DIR}"

echo "[CHECK] Validating Compose configuration"
docker compose config --quiet

echo "[DEPLOY] Building images and starting services"
docker compose up --build --detach

echo "[STATUS]"
docker compose ps --all

cat <<'EOF'

[NEXT] Inspect service logs before treating this deployment as successful:
  docker compose logs --tail 100 kafka
  docker compose logs --tail 100 api inference monitor

The API, inference, and monitor services require their implementations from
sections 12, 13, and 17. Until then, their containers are expected to fail.
EOF
```

### 5.8 Jenkinsfile

```groovy
pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Prepare deployment environment') {
            steps {
                withCredentials([
                    file(
                        credentialsId: 'tep-development-env',
                        variable: 'DEPLOY_ENV_FILE'
                    )
                ]) {
                    sh '''
                        install -m 600 "$DEPLOY_ENV_FILE" .env
                    '''
                }
            }
        }

        stage('Validate deployment configuration') {
            steps {
                sh '''
                    set -eu
                    test -f compose.yaml
                    test -f .env
                    docker compose config --quiet
                '''
            }
        }

        stage('Run tests') {
            steps {
                script {
                    if (!fileExists('.venv/bin/python')) {
                        echo 'Skipping tests: project .venv is not available on this agent.'
                    } else if (!fileExists('tests')) {
                        echo 'Skipping tests: tests directory has not been added yet.'
                    } else {
                        int hasTests = sh(
                            script: "find tests -type f -name 'test_*.py' -print -quit | grep -q .",
                            returnStatus: true
                        )

                        if (hasTests != 0) {
                            echo 'Skipping tests: no pytest test files were found.'
                        } else {
                            sh '.venv/bin/python -m pytest tests'
                        }
                    }
                }
            }
        }

        stage('Build Docker images') {
            when {
                branch 'dev'
            }
            steps {
                sh 'docker compose build'
            }
        }

        stage('Deploy to development server') {
            when {
                branch 'dev'
            }
            steps {
                sh '''
                    set -eu
                    docker compose up --detach
                    docker compose ps --all
                '''
            }
        }
    }

    post {
        always {
            sh 'rm -f .env'
        }
        failure {
            sh 'docker compose ps --all || true'
            sh 'docker compose logs --tail 100 || true'
        }
    }
}
```

### 5.9 .gitignore

```gitignore
# ============================================================
# Python
# ============================================================

.venv/
venv/

__pycache__/
*.py[cod]
*.pyd
*.so

.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/

# Jupyter
.ipynb_checkpoints/


# ============================================================
# Environment / Secrets
# ============================================================

.env
.env.*
!.env.example


# ============================================================
# Dataset
# ============================================================

# 원본/가공 데이터는 용량이 크고 재생성 가능하므로 Git 제외
data/raw/
data/processed/


# ============================================================
# Logs
# ============================================================

logs/*
!logs/.gitkeep

*.log


# ============================================================
# IDE / OS
# ============================================================

.vscode/
.idea/

.DS_Store
Thumbs.db
desktop.ini


# ============================================================
# Web
# ============================================================

web/node_modules/
web/dist/
web/build/
web/.next/
web/.vite/

npm-debug.log*
yarn-debug.log*
yarn-error.log*
pnpm-debug.log*


# ============================================================
# Unity
# ============================================================

unity/[Ll]ibrary/
unity/[Tt]emp/
unity/[Oo]bj/
unity/[Ll]ogs/
unity/[Uu]ser[Ss]ettings/
unity/[Mm]emoryCaptures/
unity/[Rr]ecordings/

unity/[Bb]uild/
unity/[Bb]uilds/

# Unity / Visual Studio generated files
unity/*.csproj
unity/*.sln
unity/*.suo
unity/*.user
unity/*.userprefs
unity/*.tmp
unity/*.pidb
unity/*.booproj
unity/*.svd
unity/*.pdb
unity/*.mdb
unity/*.opendb
unity/*.VC.db

# ============================================================
# etc
# ============================================================
Personal_Checklist.md
```

---

## 6. 소스코드 전체 (src/)

### 6.1 src/common/config.py

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")


def env_str(name: str, default: str) -> str:
    return os.getenv(name, default)


def env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def env_float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def project_path(value: str) -> Path:
    path = Path(value)

    if path.is_absolute():
        return path

    return PROJECT_ROOT / path


@dataclass(frozen=True)
class Settings:
    # Application
    app_env: str = env_str(
        "APP_ENV",
        "development",
    )

    log_level: str = env_str(
        "LOG_LEVEL",
        "INFO",
    )

    # Kafka
    kafka_bootstrap_servers: str = env_str(
        "KAFKA_BOOTSTRAP_SERVERS",
        "localhost:9092",
    )

    kafka_sensor_topic: str = env_str(
        "KAFKA_SENSOR_TOPIC",
        "tep-sensor-data",
    )

    kafka_prediction_topic: str = env_str(
        "KAFKA_PREDICTION_TOPIC",
        "tep-predictions",
    )

    kafka_drift_topic: str = env_str(
        "KAFKA_DRIFT_TOPIC",
        "tep-drift-events",
    )

    kafka_consumer_group: str = env_str(
        "KAFKA_CONSUMER_GROUP",
        "inference-service",
    )

    # TEP Replay
    tep_replay_speed: float = env_float(
        "TEP_REPLAY_SPEED",
        1.0,
    )

    tep_replay_interval_seconds: float = env_float(
        "TEP_REPLAY_INTERVAL_SECONDS",
        0.1,
    )

    # Model
    model_version: str = env_str(
        "MODEL_VERSION",
        "v1.0.0",
    )

    temporal_warmup_minutes: int = env_int(
        "TEMPORAL_WARMUP_MINUTES",
        60,
    )

    # API
    api_host: str = env_str(
        "API_HOST",
        "0.0.0.0",
    )

    api_port: int = env_int(
        "API_PORT",
        8000,
    )

    # Drift
    drift_check_enabled: bool = env_bool(
        "DRIFT_CHECK_ENABLED",
        True,
    )

    drift_check_interval_seconds: int = env_int(
        "DRIFT_CHECK_INTERVAL_SECONDS",
        60,
    )

    # Retraining
    retrain_enabled: bool = env_bool(
        "RETRAIN_ENABLED",
        True,
    )

    # Paths
    model_dir: Path = project_path(
        env_str(
            "MODEL_DIR",
            "models/production/v1.0.0",
        )
    )

    candidate_model_dir: Path = project_path(
        env_str(
            "CANDIDATE_MODEL_DIR",
            "models/candidates",
        )
    )

    production_model_dir: Path = project_path(
        env_str(
            "PRODUCTION_MODEL_DIR",
            "models/production",
        )
    )

    data_raw_dir: Path = project_path(
        env_str(
            "DATA_RAW_DIR",
            "data/raw",
        )
    )

    data_processed_dir: Path = project_path(
        env_str(
            "DATA_PROCESSED_DIR",
            "data/processed",
        )
    )

    data_metadata_dir: Path = project_path(
        env_str(
            "DATA_METADATA_DIR",
            "data/metadata",
        )
    )

    report_dir: Path = project_path(
        env_str(
            "REPORT_DIR",
            "reports",
        )
    )

    log_dir: Path = project_path(
        env_str(
            "LOG_DIR",
            "logs",
        )
    )


settings = Settings()
```

### 6.2 src/common/logger.py

```python
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from src.common.config import settings


_LOGGERS: dict[str, logging.Logger] = {}


def get_logger(
    name: str,
    log_file: str | None = None,
) -> logging.Logger:
    """
    프로젝트 공통 Logger.

    사용 예:
        logger = get_logger(
            "inference",
            "inference.log",
        )

        logger.info("Inference service started")
    """

    if name in _LOGGERS:
        return _LOGGERS[name]

    logger = logging.getLogger(name)

    level = getattr(
        logging,
        settings.log_level.upper(),
        logging.INFO,
    )

    logger.setLevel(level)
    logger.propagate = False

    formatter = logging.Formatter(
        fmt=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(name)s | "
            "%(message)s"
        ),
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)

    # File
    if log_file is not None:
        log_dir: Path = settings.log_dir

        log_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        file_handler = RotatingFileHandler(
            log_dir / log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )

        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)

        logger.addHandler(file_handler)

    _LOGGERS[name] = logger

    return logger
```

### 6.3 src/common/06-create_production_version.py

```python
from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

VERSION = "v1.0.0"

SOURCE_MODEL_DIR = (
    PROJECT_ROOT
    / "models"
    / "candidates"
    / "05-temporal"
)

THRESHOLD_PATH = (
    PROJECT_ROOT
    / "reports"
    / "05-temporal"
    / "thresholds.json"
)

METRICS_PATH = (
    PROJECT_ROOT
    / "reports"
    / "05-temporal"
    / "temporal_metrics.csv"
)

PRODUCTION_DIR = (
    PROJECT_ROOT
    / "models"
    / "production"
    / VERSION
)

MODEL_FILES = [
    "rul_hours.json",
    "failure_within_4h.json",
    "failure_within_2h.json",
    "failure_within_1h.json",
]


def get_git_commit() -> str | None:
    try:
        result = subprocess.run(
            [
                "git",
                "rev-parse",
                "HEAD",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

        return result.stdout.strip()

    except Exception:
        return None


def load_thresholds() -> dict:
    with THRESHOLD_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def load_metrics() -> dict:
    df = pd.read_csv(METRICS_PATH)

    result = {}

    for _, row in df.iterrows():
        target = row["target"]

        if target == "rul_hours":
            result[target] = {
                "test_mae": float(
                    row["test_mae"]
                ),
                "test_rmse": float(
                    row["test_rmse"]
                ),
                "test_r2": float(
                    row["test_r2"]
                ),
            }

        else:
            result[target] = {
                "test_average_precision": float(
                    row["test_average_precision"]
                ),
                "test_roc_auc": float(
                    row["test_roc_auc"]
                ),
                "test_f1": float(
                    row["test_f1"]
                ),
                "event_detection_rate": float(
                    row["event_detection_rate"]
                ),
            }

    return result


def main() -> None:
    print("=" * 80)
    print("CREATE PRODUCTION MODEL VERSION")
    print("=" * 80)

    PRODUCTION_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # 모델 복사
    for filename in MODEL_FILES:
        source = SOURCE_MODEL_DIR / filename

        if not source.exists():
            raise FileNotFoundError(
                f"모델 파일이 없습니다: {source}"
            )

        destination = (
            PRODUCTION_DIR / filename
        )

        shutil.copy2(
            source,
            destination,
        )

        print(f"[COPY] {filename}")

    # threshold 복사
    if not THRESHOLD_PATH.exists():
        raise FileNotFoundError(
            f"threshold 파일이 없습니다: {THRESHOLD_PATH}"
        )

    shutil.copy2(
        THRESHOLD_PATH,
        PRODUCTION_DIR
        / "thresholds.json",
    )

    print("[COPY] thresholds.json")

    thresholds = load_thresholds()
    metrics = load_metrics()

    metadata = {
        "version": VERSION,

        "created_at_utc": (
            datetime.now(timezone.utc)
            .isoformat()
        ),

        "git_commit": get_git_commit(),

        "model_family": "XGBoost",

        "feature_set": "temporal",

        "feature_count": 728,

        "sampling_interval_minutes": 3,

        "warmup_minutes": 60,

        "training_cases": [
            "case1",
            "case2",
            "case3",
            "case4",
            "case5",
            "case6",
        ],

        "models": {
            "rul": "rul_hours.json",

            "failure_within_4h":
                "failure_within_4h.json",

            "failure_within_2h":
                "failure_within_2h.json",

            "failure_within_1h":
                "failure_within_1h.json",
        },

        "thresholds": thresholds,

        "test_metrics": metrics,

        "source_candidate":
            "models/candidates/05-temporal",
    }

    metadata_path = (
        PRODUCTION_DIR
        / "metadata.json"
    )

    with metadata_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            metadata,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print(f"[SAVE] {metadata_path}")

    print()
    print(f"Version       : {VERSION}")
    print("Feature set   : temporal")
    print("Feature count : 728")
    print(f"Git commit    : {metadata['git_commit']}")

    print()
    print("[PASS] Production model version created")


if __name__ == "__main__":
    main()
```

### 6.4 src/common/06-save_feature_list.py

```python
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

VERSION = "v1.0.0"

SOURCE_SCHEMA_PATH = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / "temporal_feature_schema.csv"
)

PRODUCTION_DIR = (
    PROJECT_ROOT
    / "models"
    / "production"
    / VERSION
)

FEATURE_LIST_PATH = (
    PRODUCTION_DIR
    / "feature_list.json"
)

FEATURE_SCHEMA_PATH = (
    PRODUCTION_DIR
    / "feature_schema.csv"
)

METADATA_PATH = (
    PRODUCTION_DIR
    / "metadata.json"
)

EXPECTED_FEATURE_COUNT = 728


def parse_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series

    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .eq("true")
    )


def main() -> None:
    print("=" * 80)
    print("SAVE PRODUCTION FEATURE LIST")
    print("=" * 80)

    if not SOURCE_SCHEMA_PATH.exists():
        raise FileNotFoundError(
            f"Temporal feature schema가 없습니다: {SOURCE_SCHEMA_PATH}"
        )

    if not PRODUCTION_DIR.exists():
        raise FileNotFoundError(
            f"Production model directory가 없습니다: {PRODUCTION_DIR}"
        )

    schema = pd.read_csv(
        SOURCE_SCHEMA_PATH
    )

    schema["model_feature"] = parse_bool(
        schema["model_feature"]
    )

    model_schema = (
        schema[
            schema["model_feature"]
        ]
        .copy()
        .reset_index(drop=True)
    )

    features = (
        model_schema["feature"]
        .tolist()
    )

    if len(features) != EXPECTED_FEATURE_COUNT:
        raise ValueError(
            "Feature count 오류: "
            f"expected={EXPECTED_FEATURE_COUNT}, "
            f"actual={len(features)}"
        )

    if len(features) != len(set(features)):
        raise ValueError(
            "Feature 이름에 중복이 있습니다."
        )

    # --------------------------------------------------------
    # Exact ordered feature list
    # --------------------------------------------------------

    feature_payload = {
        "model_version": VERSION,
        "feature_count": len(features),
        "order_required": True,
        "features": features,
    }

    with FEATURE_LIST_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            feature_payload,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print(
        f"[SAVE] {FEATURE_LIST_PATH}"
    )

    # --------------------------------------------------------
    # Feature schema snapshot
    # --------------------------------------------------------

    model_schema.to_csv(
        FEATURE_SCHEMA_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print(
        f"[SAVE] {FEATURE_SCHEMA_PATH}"
    )

    # --------------------------------------------------------
    # Update production metadata
    # --------------------------------------------------------

    if METADATA_PATH.exists():
        with METADATA_PATH.open(
            "r",
            encoding="utf-8",
        ) as file:
            metadata = json.load(file)

        metadata["feature_count"] = len(features)
        metadata["feature_list_file"] = "feature_list.json"
        metadata["feature_schema_file"] = "feature_schema.csv"

        with METADATA_PATH.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                metadata,
                file,
                indent=2,
                ensure_ascii=False,
            )

        print(
            "[UPDATE] metadata.json"
        )

    print()
    print(f"Feature count : {len(features)}")
    print(f"First feature : {features[0]}")
    print(f"Last feature  : {features[-1]}")

    print()
    print("[PASS] Production feature list saved")


if __name__ == "__main__":
    main()
```

### 6.5 src/common/06-save_prediction_schema.py

```python
from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

VERSION = "v1.0.0"

OUTPUT_PATH = (
    PROJECT_ROOT
    / "models"
    / "production"
    / VERSION
    / "prediction_schema.json"
)


def main() -> None:
    schema = {
        "schema_version": "1.0",

        "model_version": "string",

        "trajectory_key": "string",

        "timestamp_hours": "number",

        "rul": {
            "hours": "number",
        },

        "risk": {
            "failure_within_4h": {
                "score": "number",
                "threshold": "number",
                "alert": "boolean",
            },

            "failure_within_2h": {
                "score": "number",
                "threshold": "number",
                "alert": "boolean",
            },

            "failure_within_1h": {
                "score": "number",
                "threshold": "number",
                "alert": "boolean",
            },
        },

        "status": (
            "NORMAL | CAUTION | WARNING | CRITICAL"
        ),

        "explanation_model": (
            "failure_within_4h | "
            "failure_within_2h | "
            "failure_within_1h"
        ),

        "top_risk_factors": [
            {
                "rank": "integer",
                "feature": "string",
                "source_feature": "string",
                "transform": "string",
                "window_minutes": (
                    "integer | null"
                ),
                "shap_value": "number",
            }
        ],
    }

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            schema,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print(
        f"[SAVE] {OUTPUT_PATH}"
    )

    print(
        "[PASS] Prediction schema saved"
    )


if __name__ == "__main__":
    main()
```

### 6.6 src/common/06-shap_explainer.py

```python
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb


PROJECT_ROOT = Path(__file__).resolve().parents[2]

VERSION = "v1.0.0"

PRODUCTION_DIR = (
    PROJECT_ROOT
    / "models"
    / "production"
    / VERSION
)

FEATURE_LIST_PATH = (
    PRODUCTION_DIR
    / "feature_list.json"
)

TEST_DATA_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "temporal"
    / "test.parquet"
)

MODEL_FILES = {
    "failure_within_4h": "failure_within_4h.json",
    "failure_within_2h": "failure_within_2h.json",
    "failure_within_1h": "failure_within_1h.json",
}


def load_feature_list() -> list[str]:
    with FEATURE_LIST_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        payload = json.load(file)

    features = payload["features"]

    if len(features) != 728:
        raise ValueError(
            f"Expected 728 features, got {len(features)}"
        )

    return features


def load_model(target: str) -> xgb.Booster:
    if target not in MODEL_FILES:
        raise ValueError(
            f"Unsupported target: {target}"
        )

    path = (
        PRODUCTION_DIR
        / MODEL_FILES[target]
    )

    if not path.exists():
        raise FileNotFoundError(
            f"Model not found: {path}"
        )

    model = xgb.Booster()
    model.load_model(path)

    return model


def calculate_shap(
    model: xgb.Booster,
    feature_values: pd.DataFrame,
    feature_names: list[str],
) -> tuple[np.ndarray, float]:

    matrix = xgb.DMatrix(
        feature_values.to_numpy(
            dtype=np.float32
        ),
        feature_names=feature_names,
    )

    contributions = model.predict(
        matrix,
        pred_contribs=True,
    )

    # 마지막 값은 SHAP bias/base value
    shap_values = contributions[0, :-1]
    base_value = float(
        contributions[0, -1]
    )

    # TreeSHAP additivity 검증
    raw_prediction = float(
        model.predict(
            matrix,
            output_margin=True,
        )[0]
    )

    reconstructed = float(
        shap_values.sum()
        + base_value
    )

    if not np.isclose(
        raw_prediction,
        reconstructed,
        rtol=1e-4,
        atol=1e-4,
    ):
        raise ValueError(
            "SHAP additivity validation failed: "
            f"model={raw_prediction}, "
            f"shap={reconstructed}"
        )

    return shap_values, base_value


def main() -> None:
    print("=" * 80)
    print("XGBOOST TREESHAP VALIDATION")
    print("=" * 80)

    features = load_feature_list()

    # 테스트용 한 행만 읽는다.
    # 전체 660MB 데이터를 메모리에 올릴 필요 없음.
    test_df = pd.read_parquet(
        TEST_DATA_PATH,
        columns=(
            [
                "trajectory_key",
                "Time",
                "rul_hours",
            ]
            + features
        ),
    )

    # 고장에 가까운 데이터 하나를 테스트 대상으로 선택
    row = (
        test_df
        .sort_values("rul_hours")
        .iloc[[0]]
    )

    print(
        f"Trajectory : "
        f"{row['trajectory_key'].iloc[0]}"
    )

    print(
        f"Time       : "
        f"{row['Time'].iloc[0]:.2f} h"
    )

    print(
        f"RUL        : "
        f"{row['rul_hours'].iloc[0]:.2f} h"
    )

    X = row[features]

    for target in MODEL_FILES:

        print()
        print("-" * 80)
        print(target)
        print("-" * 80)

        model = load_model(
            target
        )

        shap_values, base_value = (
            calculate_shap(
                model,
                X,
                features,
            )
        )

        result = pd.DataFrame(
            {
                "feature": features,
                "shap_value": shap_values,
            }
        )

        result["abs_shap"] = (
            result["shap_value"]
            .abs()
        )

        result = (
            result
            .sort_values(
                "abs_shap",
                ascending=False,
            )
            .reset_index(drop=True)
        )

        print(
            f"Base value : "
            f"{base_value:.6f}"
        )

        print()
        print("Top 10 SHAP features:")

        print(
            result[
                [
                    "feature",
                    "shap_value",
                ]
            ]
            .head(10)
            .to_string(
                index=False
            )
        )

        print()
        print(
            "[PASS] SHAP additivity verified"
        )

    print()
    print("=" * 80)
    print("[PASS] TreeSHAP explanation implemented")
    print("=" * 80)


if __name__ == "__main__":
    main()
```

### 6.7 src/data/02-inspect_tep_h5.py

```python
import h5py

path = r"D:\TEP_DigitalTwin\data\unzip\TEP\teps.h5"

with h5py.File(path, "r") as f:
    def show(name, obj):
        print(name, type(obj).__name__, getattr(obj, "shape", ""))

    f.visititems(show)

    print("\nROOT ATTRIBUTES")
    for k, v in f.attrs.items():
        print(k, "=", v)
```

### 6.8 src/data/02-compare_extra_cases.py

```python
from pathlib import Path
import pandas as pd
import numpy as np

DATA_DIR = Path(r"D:\TEP_DigitalTwin\data\unzip\TEP")

FILES = [
    "case1.csv",
    "case2.csv",
    "case3.csv",
    "case4.csv",
    "case5.csv",
    "case5_1.csv",
    "case6.csv",
    "case7.csv",
]

info = {}

for name in FILES:
    path = DATA_DIR / name

    if not path.exists():
        print(f"[MISSING] {name}")
        continue

    df = pd.read_csv(path)

    info[name] = df

    print(
        f"{name:12s}",
        "shape =", df.shape,
        "Ids =", df["Id"].nunique(),
        "Time range =",
        (df["Time"].min(), df["Time"].max()),
    )

print()
print("=" * 70)
print("EXTRA CASE COMPARISON")
print("=" * 70)

for extra_name in ["case5_1.csv", "case7.csv"]:

    if extra_name not in info:
        continue

    extra = info[extra_name]

    print(f"\n[{extra_name}]")

    for base_name in [
        "case1.csv",
        "case2.csv",
        "case3.csv",
        "case4.csv",
        "case5.csv",
        "case6.csv",
    ]:

        if base_name not in info:
            continue

        base = info[base_name]

        same_shape = (
            extra.shape == base.shape
        )

        same_columns = (
            list(extra.columns)
            == list(base.columns)
        )

        exact_equal = False

        if same_shape and same_columns:
            exact_equal = extra.equals(base)

        print(
            f"vs {base_name:10s} | "
            f"same_shape={same_shape} | "
            f"same_columns={same_columns} | "
            f"exact_equal={exact_equal}"
        )
```

### 6.9 src/data/03-build_dataset_manifest.py

```python
from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd


# ============================================================
# Project settings
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DIR = PROJECT_ROOT / "data" / "raw" / "TEP"
METADATA_DIR = PROJECT_ROOT / "data" / "metadata"

OFFICIAL_CASES = [
    "case1",
    "case2",
    "case3",
    "case4",
    "case5",
    "case6",
]

EXPECTED_COLUMN_COUNT = 58
EXPECTED_IDS_PER_CASE = 100
EXPECTED_INTERVAL_HOURS = 0.05  # 3 minutes

TRAIN_COUNT = 70
VALIDATION_COUNT = 15
TEST_COUNT = 15

RANDOM_STATE = 42
FLOAT_TOLERANCE = 1e-8


def print_section(title: str) -> None:
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def load_cases() -> dict[str, pd.DataFrame]:
    data: dict[str, pd.DataFrame] = {}

    for case in OFFICIAL_CASES:
        path = RAW_DIR / f"{case}.csv"

        if not path.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")

        print(f"[LOAD] {path.name}")
        df = pd.read_csv(path)

        data[case] = df

    return data


def validate_columns(data: dict[str, pd.DataFrame]) -> list[str]:
    print_section("1. COLUMN SCHEMA CHECK")

    reference_case = OFFICIAL_CASES[0]
    reference_columns = list(data[reference_case].columns)

    print(f"{reference_case}: {len(reference_columns)} columns")

    if len(reference_columns) != EXPECTED_COLUMN_COUNT:
        raise ValueError(
            f"{reference_case}의 컬럼 수가 예상과 다릅니다. "
            f"expected={EXPECTED_COLUMN_COUNT}, actual={len(reference_columns)}"
        )

    if "Id" not in reference_columns:
        raise ValueError("필수 컬럼 'Id'가 없습니다.")

    if "Time" not in reference_columns:
        raise ValueError("필수 컬럼 'Time'이 없습니다.")

    for case, df in data.items():
        columns = list(df.columns)

        same = columns == reference_columns

        print(
            f"{case}: columns={len(columns)}, "
            f"same_as_reference={same}"
        )

        if not same:
            raise ValueError(
                f"{case}의 컬럼 구성이 {reference_case}와 다릅니다."
            )

    print("[PASS] 모든 공식 case의 컬럼 구성이 동일합니다.")

    return reference_columns


def build_trajectory_summary(
    data: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    print_section("2. TRAJECTORY / DATA QUALITY CHECK")

    rows = []

    total_missing = 0
    total_duplicate_timestamps = 0
    total_interval_errors = 0
    total_inf = 0

    for case, df in data.items():
        id_count = df["Id"].nunique()

        print()
        print(f"[{case}]")
        print(f"rows             : {len(df):,}")
        print(f"trajectory count : {id_count}")

        if id_count != EXPECTED_IDS_PER_CASE:
            print(
                f"[WARN] expected {EXPECTED_IDS_PER_CASE} trajectories, "
                f"found {id_count}"
            )

        case_missing = int(df.isna().sum().sum())
        total_missing += case_missing

        numeric_df = df.select_dtypes(include=[np.number])
        case_inf = int(np.isinf(numeric_df.to_numpy()).sum())
        total_inf += case_inf

        print(f"missing values    : {case_missing:,}")
        print(f"infinite values   : {case_inf:,}")

        for trajectory_id, trajectory in df.groupby("Id", sort=True):
            trajectory = trajectory.sort_values("Time").reset_index(drop=True)

            trajectory_key = f"{case}::{trajectory_id}"

            missing_count = int(trajectory.isna().sum().sum())

            duplicate_timestamp_count = int(
                trajectory["Time"].duplicated().sum()
            )

            times = trajectory["Time"].to_numpy(dtype=float)

            if len(times) > 1:
                intervals = np.diff(times)

                invalid_interval_mask = ~np.isclose(
                    intervals,
                    EXPECTED_INTERVAL_HOURS,
                    atol=FLOAT_TOLERANCE,
                    rtol=0.0,
                )

                invalid_interval_count = int(
                    invalid_interval_mask.sum()
                )

                min_interval = float(intervals.min())
                max_interval = float(intervals.max())
            else:
                invalid_interval_count = 0
                min_interval = np.nan
                max_interval = np.nan

            start_time = float(times[0])
            end_time = float(times[-1])
            duration_hours = end_time - start_time

            total_duplicate_timestamps += duplicate_timestamp_count
            total_interval_errors += invalid_interval_count

            numeric_trajectory = trajectory.select_dtypes(
                include=[np.number]
            )

            inf_count = int(
                np.isinf(numeric_trajectory.to_numpy()).sum()
            )

            rows.append(
                {
                    "trajectory_key": trajectory_key,
                    "case": case,
                    "Id": trajectory_id,
                    "row_count": len(trajectory),
                    "start_time": start_time,
                    "end_time": end_time,
                    "duration_hours": duration_hours,
                    "missing_count": missing_count,
                    "infinite_count": inf_count,
                    "duplicate_timestamp_count": duplicate_timestamp_count,
                    "invalid_interval_count": invalid_interval_count,
                    "min_interval_hours": min_interval,
                    "max_interval_hours": max_interval,
                }
            )

    summary = pd.DataFrame(rows)

    print_section("3. GLOBAL DATA QUALITY RESULT")

    print(f"trajectories                : {len(summary):,}")
    print(f"missing values              : {total_missing:,}")
    print(f"infinite values             : {total_inf:,}")
    print(
        f"duplicate trajectory/time   : "
        f"{total_duplicate_timestamps:,}"
    )
    print(
        f"non-0.05h sampling interval : "
        f"{total_interval_errors:,}"
    )

    if len(summary) != 600:
        print(
            f"[WARN] 공식 trajectory 수가 600이 아닙니다: "
            f"{len(summary)}"
        )
    else:
        print("[PASS] 총 600개의 공식 trajectory를 확인했습니다.")

    if total_missing == 0:
        print("[PASS] 결측치 없음")
    else:
        print("[WARN] 결측치 존재")

    if total_inf == 0:
        print("[PASS] inf / -inf 없음")
    else:
        print("[WARN] inf / -inf 존재")

    if total_duplicate_timestamps == 0:
        print("[PASS] 중복 timestamp 없음")
    else:
        print("[WARN] 중복 timestamp 존재")

    if total_interval_errors == 0:
        print("[PASS] 모든 trajectory의 sampling interval = 0.05h")
    else:
        print("[WARN] sampling interval 이상 존재")

    return summary


def build_split_manifest(
    summary: pd.DataFrame,
) -> pd.DataFrame:
    print_section("4. TRAIN / VALIDATION / TEST SPLIT")

    rng = np.random.default_rng(RANDOM_STATE)

    split_rows = []

    for case in OFFICIAL_CASES:
        case_summary = summary[
            summary["case"] == case
        ].copy()

        ids = np.array(sorted(case_summary["Id"].unique()))
        rng.shuffle(ids)

        if len(ids) != 100:
            raise ValueError(
                f"{case}: trajectory 수가 100이 아니므로 "
                "70/15/15 split을 생성할 수 없습니다."
            )

        train_ids = set(ids[:TRAIN_COUNT])
        validation_ids = set(
            ids[
                TRAIN_COUNT:
                TRAIN_COUNT + VALIDATION_COUNT
            ]
        )
        test_ids = set(
            ids[
                TRAIN_COUNT + VALIDATION_COUNT:
            ]
        )

        for trajectory_id in sorted(ids):
            if trajectory_id in train_ids:
                split = "train"
            elif trajectory_id in validation_ids:
                split = "validation"
            elif trajectory_id in test_ids:
                split = "test"
            else:
                raise RuntimeError("split assignment error")

            split_rows.append(
                {
                    "trajectory_key": f"{case}::{trajectory_id}",
                    "case": case,
                    "Id": trajectory_id,
                    "split": split,
                }
            )

        print(
            f"{case}: "
            f"train={len(train_ids)}, "
            f"validation={len(validation_ids)}, "
            f"test={len(test_ids)}"
        )

    manifest = pd.DataFrame(split_rows)

    print()
    print(manifest["split"].value_counts())

    expected = {
        "train": 420,
        "validation": 90,
        "test": 90,
    }

    actual = manifest["split"].value_counts().to_dict()

    for split, count in expected.items():
        if actual.get(split, 0) != count:
            raise ValueError(
                f"{split}: expected={count}, "
                f"actual={actual.get(split, 0)}"
            )

    if manifest["trajectory_key"].duplicated().any():
        raise ValueError(
            "동일 trajectory가 여러 split에 배정되었습니다."
        )

    print("[PASS] 420 / 90 / 90 trajectory split 생성 완료")

    return manifest


def classify_column_role(column: str) -> tuple[str, bool, str]:
    """
    이 단계에서는 최종 센서/제어 변수 선별을 확정하지 않는다.
    Section 4 Baseline에서 실제 feature 조합을 비교할 예정이므로
    모든 공정 변수는 candidate_feature로 기록한다.
    """

    if column == "Id":
        return (
            "identifier",
            False,
            "trajectory 식별용. 모델 입력 제외",
        )

    if column == "Time":
        return (
            "time",
            False,
            "경과시간 누수 가능성 때문에 모델 입력 제외",
        )

    if column.lower().startswith("msv"):
        return (
            "manipulated_or_control_variable",
            True,
            "제어/조작 변수 후보. Baseline Model B에서 별도 검증",
        )

    return (
        "process_candidate_feature",
        True,
        "공정 측정 또는 상태 변수 후보. Section 4에서 최종 선별",
    )


def build_feature_schema(
    data: dict[str, pd.DataFrame],
    columns: list[str],
) -> pd.DataFrame:
    print_section("5. FEATURE SCHEMA")

    reference_df = data[OFFICIAL_CASES[0]]

    rows = []

    for column in columns:
        role, candidate, note = classify_column_role(column)

        series = reference_df[column]

        rows.append(
            {
                "column": column,
                "dtype": str(series.dtype),
                "role": role,
                "candidate_feature": candidate,
                "note": note,
            }
        )

    schema = pd.DataFrame(rows)

    print(schema["role"].value_counts())

    return schema


def check_constant_columns(
    data: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    print_section("6. BASIC OUTLIER / CONSTANT CHECK")

    # 전체 공식 데이터를 메모리에 다시 합치지 않고
    # case별 min/max/nunique 정보를 누적한다.
    numeric_columns = [
        col
        for col in data[OFFICIAL_CASES[0]].columns
        if pd.api.types.is_numeric_dtype(
            data[OFFICIAL_CASES[0]][col]
        )
    ]

    results = []

    for column in numeric_columns:
        mins = []
        maxs = []
        unique_values = set()

        for df in data.values():
            series = df[column].dropna()

            if len(series) == 0:
                continue

            mins.append(float(series.min()))
            maxs.append(float(series.max()))

            # constant 여부 판단만 필요하므로
            # unique를 무한정 저장하지 않음.
            if len(unique_values) <= 2:
                unique_values.update(
                    series.drop_duplicates().head(3).tolist()
                )

        global_min = min(mins) if mins else np.nan
        global_max = max(maxs) if maxs else np.nan

        constant = (
            len(unique_values) == 1
            if unique_values
            else False
        )

        results.append(
            {
                "column": column,
                "global_min": global_min,
                "global_max": global_max,
                "constant_candidate": constant,
            }
        )

    result_df = pd.DataFrame(results)

    constants = result_df[
        result_df["constant_candidate"]
    ]

    if constants.empty:
        print("[PASS] 전체 데이터에서 고정된 numeric column 없음")
    else:
        print("[WARN] 고정값 후보 컬럼:")
        print(constants.to_string(index=False))

    print()
    print(
        "주의: 여기서 '이상값 없음'을 물리적으로 증명하는 것은 아님."
    )
    print(
        "NaN, inf, 시간축 오류, 고정 컬럼 등 명백한 데이터 이상을 "
        "우선 검사함."
    )

    return result_df


def save_outputs(
    trajectory_summary: pd.DataFrame,
    split_manifest: pd.DataFrame,
    feature_schema: pd.DataFrame,
    column_summary: pd.DataFrame,
) -> None:
    print_section("7. SAVE METADATA")

    METADATA_DIR.mkdir(parents=True, exist_ok=True)

    trajectory_path = (
        METADATA_DIR / "trajectory_summary.csv"
    )
    split_path = (
        METADATA_DIR / "split_manifest.csv"
    )
    feature_path = (
        METADATA_DIR / "feature_schema.csv"
    )
    column_path = (
        METADATA_DIR / "column_summary.csv"
    )

    trajectory_summary.to_csv(
        trajectory_path,
        index=False,
        encoding="utf-8-sig",
    )

    split_manifest.to_csv(
        split_path,
        index=False,
        encoding="utf-8-sig",
    )

    feature_schema.to_csv(
        feature_path,
        index=False,
        encoding="utf-8-sig",
    )

    column_summary.to_csv(
        column_path,
        index=False,
        encoding="utf-8-sig",
    )

    print(f"[SAVE] {trajectory_path}")
    print(f"[SAVE] {split_path}")
    print(f"[SAVE] {feature_path}")
    print(f"[SAVE] {column_path}")


def main() -> int:
    print_section("TEP DATASET MANIFEST BUILDER")

    print(f"Project root : {PROJECT_ROOT}")
    print(f"Raw data     : {RAW_DIR}")
    print(f"Metadata     : {METADATA_DIR}")

    try:
        data = load_cases()

        columns = validate_columns(data)

        trajectory_summary = build_trajectory_summary(
            data
        )

        split_manifest = build_split_manifest(
            trajectory_summary
        )

        feature_schema = build_feature_schema(
            data,
            columns,
        )

        column_summary = check_constant_columns(
            data
        )

        save_outputs(
            trajectory_summary=trajectory_summary,
            split_manifest=split_manifest,
            feature_schema=feature_schema,
            column_summary=column_summary,
        )

    except Exception as exc:
        print()
        print(f"[FAIL] {type(exc).__name__}: {exc}")
        return 1

    print_section("COMPLETE")
    print("Dataset validation and split metadata generated successfully.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### 6.10 src/data/03-build_processed_dataset.py

```python
from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DIR = PROJECT_ROOT / "data" / "raw" / "TEP"
METADATA_DIR = PROJECT_ROOT / "data" / "metadata"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

OFFICIAL_CASES = [
    "case1",
    "case2",
    "case3",
    "case4",
    "case5",
    "case6",
]

CONSTANT_COLUMNS = [
    "Agitator",
]


def load_split_manifest() -> pd.DataFrame:
    path = METADATA_DIR / "split_manifest.csv"

    if not path.exists():
        raise FileNotFoundError(
            f"split manifest가 없습니다: {path}"
        )

    return pd.read_csv(path)


def add_targets(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # 같은 case 내부에서도 Id별로 각각 독립적인 trajectory이다.
    eol_time = df.groupby("Id")["Time"].transform("max")
    start_time = df.groupby("Id")["Time"].transform("min")

    duration = eol_time - start_time

    df["rul_hours"] = eol_time - df["Time"]

    df["rul_fraction"] = (
        df["rul_hours"] / duration
    )

    df["failure_within_4h"] = (
        df["rul_hours"] <= 4.0
    ).astype("int8")

    df["failure_within_2h"] = (
        df["rul_hours"] <= 2.0
    ).astype("int8")

    df["failure_within_1h"] = (
        df["rul_hours"] <= 1.0
    ).astype("int8")

    return df


def process_case(
    case: str,
    manifest: pd.DataFrame,
) -> list[pd.DataFrame]:

    path = RAW_DIR / f"{case}.csv"

    print(f"[LOAD] {path.name}")

    df = pd.read_csv(path)

    # case 정보를 데이터 관리용으로 추가.
    # 모델 feature로 사용해서는 안 된다.
    df.insert(0, "case", case)

    df["trajectory_key"] = (
        df["case"]
        + "::"
        + df["Id"].astype(str)
    )

    df = add_targets(df)

    for column in CONSTANT_COLUMNS:
        if column in df.columns:
            df = df.drop(columns=column)

    case_manifest = manifest[
        manifest["case"] == case
    ][
        ["trajectory_key", "split"]
    ]

    df = df.merge(
        case_manifest,
        on="trajectory_key",
        how="left",
        validate="many_to_one",
    )

    if df["split"].isna().any():
        missing = df.loc[
            df["split"].isna(),
            "trajectory_key",
        ].unique()

        raise ValueError(
            f"{case}: split을 찾을 수 없는 trajectory가 있습니다: "
            f"{missing[:10]}"
        )

    outputs = []

    for split in ["train", "validation", "test"]:
        split_df = df[df["split"] == split].copy()

        outputs.append(
            (
                split,
                split_df,
            )
        )

    return outputs


def validate_processed(
    datasets: dict[str, pd.DataFrame],
) -> None:

    print()
    print("=" * 80)
    print("PROCESSED DATA VALIDATION")
    print("=" * 80)

    trajectory_sets = {}

    for split, df in datasets.items():

        keys = set(df["trajectory_key"].unique())
        trajectory_sets[split] = keys

        print()
        print(f"[{split}]")
        print(f"rows         : {len(df):,}")
        print(f"trajectories : {len(keys):,}")
        print(
            f"RUL range    : "
            f"{df['rul_hours'].min():.2f} ~ "
            f"{df['rul_hours'].max():.2f} h"
        )

        for target in [
            "failure_within_4h",
            "failure_within_2h",
            "failure_within_1h",
        ]:
            positives = int(df[target].sum())
            ratio = float(df[target].mean())

            print(
                f"{target:18s}: "
                f"{positives:,} positive "
                f"({ratio:.4%})"
            )

        if df.isna().any().any():
            raise ValueError(
                f"{split}: processed 데이터에 결측치가 있습니다."
            )

        if "Agitator" in df.columns:
            raise ValueError(
                f"{split}: Agitator가 제거되지 않았습니다."
            )

    if trajectory_sets["train"] & trajectory_sets["validation"]:
        raise ValueError(
            "Train과 Validation trajectory가 중복됩니다."
        )

    if trajectory_sets["train"] & trajectory_sets["test"]:
        raise ValueError(
            "Train과 Test trajectory가 중복됩니다."
        )

    if trajectory_sets["validation"] & trajectory_sets["test"]:
        raise ValueError(
            "Validation과 Test trajectory가 중복됩니다."
        )

    expected_counts = {
        "train": 420,
        "validation": 90,
        "test": 90,
    }

    for split, expected in expected_counts.items():
        actual = len(trajectory_sets[split])

        if actual != expected:
            raise ValueError(
                f"{split}: expected={expected}, actual={actual}"
            )

    print()
    print("[PASS] split 간 trajectory 중복 없음")
    print("[PASS] 420 / 90 / 90 trajectory 확인")
    print("[PASS] target 생성 확인")
    print("[PASS] 상수 컬럼 Agitator 제거 확인")


def save_datasets(
    datasets: dict[str, pd.DataFrame],
) -> None:

    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print()
    print("=" * 80)
    print("SAVE PARQUET")
    print("=" * 80)

    for split, df in datasets.items():

        path = PROCESSED_DIR / f"{split}.parquet"

        # split은 파일 자체로 이미 구분되므로 저장할 필요 없음.
        output = df.drop(columns=["split"])

        output.to_parquet(
            path,
            index=False,
        )

        size_mb = path.stat().st_size / 1024 / 1024

        print(
            f"[SAVE] {path.name}"
            f" | rows={len(output):,}"
            f" | {size_mb:.1f} MB"
        )


def update_feature_schema() -> None:

    path = METADATA_DIR / "feature_schema.csv"

    if not path.exists():
        return

    schema = pd.read_csv(path)

    mask = schema["column"] == "Agitator"

    if mask.any():
        schema.loc[mask, "role"] = "constant"
        schema.loc[mask, "candidate_feature"] = False
        schema.loc[
            mask,
            "note",
        ] = (
            "전체 공식 데이터에서 값이 100으로 고정되어 "
            "예측 정보가 없으므로 제외"
        )

        schema.to_csv(
            path,
            index=False,
            encoding="utf-8-sig",
        )

        print(
            "[UPDATE] feature_schema.csv: "
            "Agitator -> constant / excluded"
        )


def main() -> None:

    print("=" * 80)
    print("TEP PROCESSED DATASET BUILDER")
    print("=" * 80)

    manifest = load_split_manifest()

    parts = {
        "train": [],
        "validation": [],
        "test": [],
    }

    for case in OFFICIAL_CASES:

        case_outputs = process_case(
            case,
            manifest,
        )

        for split, df in case_outputs:
            parts[split].append(df)

    datasets = {}

    for split, frames in parts.items():

        datasets[split] = pd.concat(
            frames,
            ignore_index=True,
        )

        # 파일 순서와 관계없이 항상 명시적으로 정렬
        datasets[split] = datasets[split].sort_values(
            ["case", "Id", "Time"]
        ).reset_index(drop=True)

    validate_processed(datasets)

    save_datasets(datasets)

    update_feature_schema()

    print()
    print("=" * 80)
    print("COMPLETE")
    print("=" * 80)
    print("Processed dataset generation completed successfully.")


if __name__ == "__main__":
    main()
```

### 6.11 src/data/04-inspect_feature_columns.py

```python
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "TEP"
    / "case1.csv"
)


def main():
    df = pd.read_csv(
        RAW_PATH,
        nrows=5,
    )

    print("=" * 80)
    print("TEP FEATURE COLUMNS")
    print("=" * 80)

    for index, column in enumerate(df.columns, start=1):
        print(f"{index:02d}. {column}")


if __name__ == "__main__":
    main()
```

### 6.12 src/data/04-build_feature_schema.py

```python
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "TEP"
    / "case1.csv"
)

OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / "feature_schema.csv"
)


XMV_COLUMNS = [
    "D feed",
    "E Feed",
    "A Feed",
    "A and C Feed",
    "Recycle",
    "Purge",
    "Separator",
    "Stripper",
    "Steam",
    "Reactor Coolant",
    "Condenser Coolant",
    "Agitator",
]


XMEAS_COLUMNS = [
    "msv A Feed",
    "msv D Feed",
    "msv E Feed",
    "msv A and C Feed",
    "Recycle Flow",
    "Reactor Feed Rate",
    "Reactor Pressure",
    "Reactor Level",
    "Reactor Temperature",
    "Purge Rate",
    "Product Sep Temp",
    "Product Sep Level",
    "Product Sep Pressure",
    "Product Sep Underflow",
    "Stripper Level",
    "Stripper Pressure",
    "Stripper Underflow",
    "Stripper Temp",
    "Stripper Steam Flow",
    "Compressor Work",
    "Reactor Coolant Temp",
    "Separator Coolant Temp",
    "Component A to Reactor",
    "Component B to Reactor",
    "Component C to Reactor",
    "Component D to Reactor",
    "Component E to Reactor",
    "Component F to Reactor",
    "Component A to Purge",
    "Component B to Purge",
    "Component C to Purge",
    "Component D to Purge",
    "Component E to Purge",
    "Component F to Purge",
    "Component G to Purge",
    "Component H to Purge",
    "Component D to Product",
    "Component E to Product",
    "Component F to Product",
    "Component G to Product",
    "Component H to Product",
]


EXTRA_COLUMNS = [
    "Liquid Input Stripper",
    "Liquid Input Separator",
    "Liquid Input Reactor",
]


def main():
    df = pd.read_csv(RAW_PATH, nrows=5)

    rows = []

    for column in df.columns:

        # ----------------------------------------------------
        # Identifier
        # ----------------------------------------------------
        if column == "Id":
            role = "identifier"
            tep_variable = None
            model_a = False
            model_b = False
            note = "trajectory 식별자. 모델 입력 제외"

        # ----------------------------------------------------
        # Time
        # ----------------------------------------------------
        elif column == "Time":
            role = "time"
            tep_variable = None
            model_a = False
            model_b = False
            note = "경과시간 정보. 모델 입력 제외"

        # ----------------------------------------------------
        # Manipulated Variables (XMV)
        # ----------------------------------------------------
        elif column in XMV_COLUMNS:
            index = XMV_COLUMNS.index(column) + 1

            role = "manipulated_variable"
            tep_variable = f"XMV({index})"

            # Agitator는 전체 데이터에서 100으로 고정됨
            if column == "Agitator":
                model_a = False
                model_b = False
                note = (
                    "XMV 변수이나 전체 공식 데이터에서 "
                    "100으로 고정된 상수이므로 제외"
                )
            else:
                model_a = False
                model_b = True
                note = (
                    "공정 조작/제어 변수. "
                    "Model B에서만 사용"
                )

        # ----------------------------------------------------
        # Measured Variables (XMEAS)
        # ----------------------------------------------------
        elif column in XMEAS_COLUMNS:
            index = XMEAS_COLUMNS.index(column) + 1

            role = "measured_variable"
            tep_variable = f"XMEAS({index})"

            model_a = True
            model_b = True

            note = (
                "공정 측정 변수. "
                "Model A와 Model B 모두 사용"
            )

        # ----------------------------------------------------
        # Additional RTF variables
        # ----------------------------------------------------
        elif column in EXTRA_COLUMNS:
            role = "degradation_state_candidate"
            tep_variable = None

            model_a = False
            model_b = False

            note = (
                "RTF 데이터셋의 추가 변수. "
                "열화 정보 누수 가능성이 있으므로 "
                "Baseline feature에서 제외"
            )

        else:
            raise ValueError(
                f"분류되지 않은 컬럼 발견: {column}"
            )

        rows.append(
            {
                "column": column,
                "dtype": str(df[column].dtype),
                "role": role,
                "tep_variable": tep_variable,
                "model_a_feature": model_a,
                "model_b_feature": model_b,
                "note": note,
            }
        )

    schema = pd.DataFrame(rows)

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    xmv_count = (schema["role"] == "manipulated_variable").sum()
    xmeas_count = (schema["role"] == "measured_variable").sum()
    extra_count = (
        schema["role"] == "degradation_state_candidate"
    ).sum()

    model_a_count = schema["model_a_feature"].sum()
    model_b_count = schema["model_b_feature"].sum()

    print("=" * 80)
    print("TEP FEATURE SCHEMA")
    print("=" * 80)

    print(f"XMV variables       : {xmv_count}")
    print(f"XMEAS variables     : {xmeas_count}")
    print(f"Extra RTF variables : {extra_count}")
    print()
    print(f"Model A features    : {model_a_count}")
    print(f"Model B features    : {model_b_count}")

    if xmv_count != 12:
        raise ValueError(
            f"XMV 개수 오류: expected=12, actual={xmv_count}"
        )

    if xmeas_count != 41:
        raise ValueError(
            f"XMEAS 개수 오류: expected=41, actual={xmeas_count}"
        )

    if extra_count != 3:
        raise ValueError(
            f"Extra 변수 개수 오류: expected=3, actual={extra_count}"
        )

    if model_a_count != 41:
        raise ValueError(
            f"Model A feature 오류: {model_a_count}"
        )

    if model_b_count != 52:
        raise ValueError(
            f"Model B feature 오류: {model_b_count}"
        )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    schema.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print(f"[SAVE] {OUTPUT_PATH}")
    print()
    print("[PASS] Feature schema 생성 완료")


if __name__ == "__main__":
    main()
```

### 6.13 src/data/05-build_temporal_features.py

```python
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
TEMPORAL_DIR = PROCESSED_DIR / "temporal"

METADATA_DIR = PROJECT_ROOT / "data" / "metadata"

FEATURE_SCHEMA_PATH = METADATA_DIR / "feature_schema.csv"
TEMPORAL_SCHEMA_PATH = METADATA_DIR / "temporal_feature_schema.csv"
SUMMARY_PATH = METADATA_DIR / "temporal_dataset_summary.csv"

BASE_FEATURE_COUNT = 52
TEMPORAL_FEATURE_COUNT = 728

LAG_15M = 5
LAG_30M = 10
LAG_60M = 20

WINDOW_15M = 6
WINDOW_30M = 11
WINDOW_60M = 21

WARMUP_ROWS = 20

META_COLUMNS = [
    "case",
    "Id",
    "Time",
    "trajectory_key",
    "rul_hours",
    "rul_fraction",
    "failure_within_4h",
    "failure_within_2h",
    "failure_within_1h",
]


def section(title: str) -> None:
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def parse_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series

    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .eq("true")
    )


def load_base_features() -> list[str]:
    schema = pd.read_csv(FEATURE_SCHEMA_PATH)

    schema["model_b_feature"] = parse_bool(
        schema["model_b_feature"]
    )

    features = schema.loc[
        schema["model_b_feature"],
        "column",
    ].tolist()

    if len(features) != BASE_FEATURE_COUNT:
        raise ValueError(
            f"Model B feature count error: {len(features)}"
        )

    return features


def rolling_slope_60m(base: pd.DataFrame) -> pd.DataFrame:
    values = base.to_numpy(dtype=np.float32)

    rows, feature_count = values.shape

    output = np.full(
        (rows, feature_count),
        np.nan,
        dtype=np.float32,
    )

    if rows < WINDOW_60M:
        return pd.DataFrame(
            output,
            columns=base.columns,
            index=base.index,
        )

    # 0 ~ 1 hour, 3 minute intervals
    x = (
        np.arange(WINDOW_60M, dtype=np.float32)
        * 0.05
    )

    x_centered = x - x.mean()

    denominator = float(
        np.sum(x_centered ** 2)
    )

    windows = np.lib.stride_tricks.sliding_window_view(
        values,
        window_shape=WINDOW_60M,
        axis=0,
    )

    slopes = np.tensordot(
        windows,
        x_centered,
        axes=([2], [0]),
    ) / denominator

    output[
        WINDOW_60M - 1:
    ] = slopes.astype(np.float32)

    return pd.DataFrame(
        output,
        columns=base.columns,
        index=base.index,
    )


def build_features(
    trajectory: pd.DataFrame,
    base_features: list[str],
) -> pd.DataFrame:

    trajectory = (
        trajectory
        .sort_values("Time")
        .reset_index(drop=True)
    )

    base = trajectory[
        base_features
    ].astype(np.float32)

    frames = []

    # ========================================================
    # Current
    # ========================================================

    frames.append(base.copy())

    # ========================================================
    # 5 minute
    #
    # Sampling is 3 minutes.
    #
    # t-5m lies between:
    # t-6m and t-3m.
    #
    # Linear interpolation:
    # 2/3 * value(t-6m)
    # +
    # 1/3 * value(t-3m)
    # ========================================================

    past_5m = (
        (2.0 / 3.0) * base.shift(2)
        +
        (1.0 / 3.0) * base.shift(1)
    )

    delta_5m = base - past_5m

    delta_5m.columns = [
        f"{c}__delta_5m"
        for c in base_features
    ]

    rate_5m = (
        delta_5m
        / (5.0 / 60.0)
    )

    rate_5m.columns = [
        f"{c}__rate_5m_per_h"
        for c in base_features
    ]

    frames.extend([
        delta_5m,
        rate_5m,
    ])

    # ========================================================
    # 15 minute
    # ========================================================

    delta_15m = (
        base
        - base.shift(LAG_15M)
    )

    delta_15m.columns = [
        f"{c}__delta_15m"
        for c in base_features
    ]

    rate_15m = delta_15m / 0.25

    rate_15m.columns = [
        f"{c}__rate_15m_per_h"
        for c in base_features
    ]

    mean_15m = (
        base
        .rolling(
            WINDOW_15M,
            min_periods=WINDOW_15M,
        )
        .mean()
    )

    mean_15m.columns = [
        f"{c}__mean_15m"
        for c in base_features
    ]

    std_15m = (
        base
        .rolling(
            WINDOW_15M,
            min_periods=WINDOW_15M,
        )
        .std(ddof=0)
    )

    std_15m.columns = [
        f"{c}__std_15m"
        for c in base_features
    ]

    frames.extend([
        mean_15m,
        std_15m,
        delta_15m,
        rate_15m,
    ])

    # ========================================================
    # 30 minute
    # ========================================================

    mean_30m = (
        base
        .rolling(
            WINDOW_30M,
            min_periods=WINDOW_30M,
        )
        .mean()
    )

    mean_30m.columns = [
        f"{c}__mean_30m"
        for c in base_features
    ]

    std_30m = (
        base
        .rolling(
            WINDOW_30M,
            min_periods=WINDOW_30M,
        )
        .std(ddof=0)
    )

    std_30m.columns = [
        f"{c}__std_30m"
        for c in base_features
    ]

    max_30m = (
        base
        .rolling(
            WINDOW_30M,
            min_periods=WINDOW_30M,
        )
        .max()
    )

    max_30m.columns = [
        f"{c}__max_30m"
        for c in base_features
    ]

    min_30m = (
        base
        .rolling(
            WINDOW_30M,
            min_periods=WINDOW_30M,
        )
        .min()
    )

    min_30m.columns = [
        f"{c}__min_30m"
        for c in base_features
    ]

    frames.extend([
        mean_30m,
        std_30m,
        max_30m,
        min_30m,
    ])

    # ========================================================
    # 60 minute
    # ========================================================

    delta_60m = (
        base
        - base.shift(LAG_60M)
    )

    delta_60m.columns = [
        f"{c}__delta_60m"
        for c in base_features
    ]

    # 60 minutes = 1 hour
    rate_60m = delta_60m.copy()

    rate_60m.columns = [
        f"{c}__rate_60m_per_h"
        for c in base_features
    ]

    slope_60m = rolling_slope_60m(
        base
    )

    slope_60m.columns = [
        f"{c}__slope_60m_per_h"
        for c in base_features
    ]

    frames.extend([
        delta_60m,
        rate_60m,
        slope_60m,
    ])

    # ========================================================
    # Merge
    # ========================================================

    features = pd.concat(
        frames,
        axis=1,
    )

    if features.shape[1] != TEMPORAL_FEATURE_COUNT:
        raise ValueError(
            "Temporal feature count mismatch: "
            f"{features.shape[1]}"
        )

    result = pd.concat(
        [
            trajectory[META_COLUMNS],
            features,
        ],
        axis=1,
    )

    result = (
        result
        .iloc[WARMUP_ROWS:]
        .reset_index(drop=True)
    )

    feature_columns = [
        c for c in result.columns
        if c not in META_COLUMNS
    ]

    result[feature_columns] = (
        result[feature_columns]
        .astype(np.float32)
    )

    if (
        result[feature_columns]
        .isna()
        .any()
        .any()
    ):
        raise ValueError(
            "NaN remains after warm-up removal."
        )

    return result


def build_schema(
    base_features: list[str],
) -> pd.DataFrame:

    rows = []

    def add(
        source: str,
        feature: str,
        transform: str,
        window: str,
    ):
        rows.append(
            {
                "feature": feature,
                "source_feature": source,
                "transform": transform,
                "window": window,
                "model_feature": True,
            }
        )

    for c in base_features:
        add(c, c, "current", "current")

        add(c, f"{c}__delta_5m", "delta", "5m")
        add(
            c,
            f"{c}__rate_5m_per_h",
            "rate",
            "5m",
        )

        add(c, f"{c}__mean_15m", "mean", "15m")
        add(c, f"{c}__std_15m", "std", "15m")
        add(c, f"{c}__delta_15m", "delta", "15m")
        add(
            c,
            f"{c}__rate_15m_per_h",
            "rate",
            "15m",
        )

        add(c, f"{c}__mean_30m", "mean", "30m")
        add(c, f"{c}__std_30m", "std", "30m")
        add(c, f"{c}__max_30m", "max", "30m")
        add(c, f"{c}__min_30m", "min", "30m")

        add(c, f"{c}__delta_60m", "delta", "60m")
        add(
            c,
            f"{c}__rate_60m_per_h",
            "rate",
            "60m",
        )
        add(
            c,
            f"{c}__slope_60m_per_h",
            "slope",
            "60m",
        )

    schema = pd.DataFrame(rows)

    if len(schema) != TEMPORAL_FEATURE_COUNT:
        raise ValueError(
            f"Schema count error: {len(schema)}"
        )

    return schema


def validate_no_future_leakage(
    source: pd.DataFrame,
    base_features: list[str],
) -> None:

    section("NO FUTURE LEAKAGE CHECK")

    trajectory_keys = (
        source["trajectory_key"]
        .drop_duplicates()
        .head(3)
        .tolist()
    )

    checks = 0

    for key in trajectory_keys:

        trajectory = (
            source[
                source["trajectory_key"] == key
            ]
            .sort_values("Time")
            .reset_index(drop=True)
        )

        full = build_features(
            trajectory,
            base_features,
        )

        candidate_indices = sorted(
            set(
                [
                    20,
                    min(100, len(trajectory) - 2),
                    len(trajectory) // 2,
                ]
            )
        )

        for cut in candidate_indices:

            if cut < 20 or cut >= len(trajectory) - 1:
                continue

            current_time = float(
                trajectory.loc[cut, "Time"]
            )

            expected = full[
                np.isclose(
                    full["Time"],
                    current_time,
                )
            ]

            if len(expected) != 1:
                raise ValueError(
                    "Leakage validation row lookup failed."
                )

            expected_features = (
                expected
                .drop(columns=META_COLUMNS)
                .iloc[0]
                .to_numpy(dtype=np.float32)
            )

            # ------------------------------------------------
            # Test 1:
            # truncate future completely
            # ------------------------------------------------

            truncated = (
                trajectory
                .iloc[:cut + 1]
                .copy()
            )

            truncated_features = build_features(
                truncated,
                base_features,
            )

            actual_features = (
                truncated_features
                .drop(columns=META_COLUMNS)
                .iloc[-1]
                .to_numpy(dtype=np.float32)
            )

            if not np.allclose(
                expected_features,
                actual_features,
                rtol=1e-5,
                atol=1e-5,
            ):
                raise ValueError(
                    f"Future leakage detected: "
                    f"{key}, Time={current_time}"
                )

            # ------------------------------------------------
            # Test 2:
            # destroy future sensor values.
            # Current features must remain unchanged.
            # ------------------------------------------------

            mutated = trajectory.copy()

            mutated.loc[
                cut + 1:,
                base_features,
            ] = (
                mutated.loc[
                    cut + 1:,
                    base_features,
                ]
                + 1_000_000.0
            )

            mutated_features = build_features(
                mutated,
                base_features,
            )

            mutated_row = mutated_features[
                np.isclose(
                    mutated_features["Time"],
                    current_time,
                )
            ]

            changed_features = (
                mutated_row
                .drop(columns=META_COLUMNS)
                .iloc[0]
                .to_numpy(dtype=np.float32)
            )

            if not np.allclose(
                expected_features,
                changed_features,
                rtol=1e-5,
                atol=1e-5,
            ):
                raise ValueError(
                    "Future mutation changed current feature: "
                    f"{key}, Time={current_time}"
                )

            checks += 1

    print(
        f"[PASS] {checks} temporal checkpoints verified"
    )

    print(
        "[PASS] Truncating future data does not change current features"
    )

    print(
        "[PASS] Mutating future values does not change current features"
    )


def process_split(
    split: str,
    base_features: list[str],
) -> dict:

    section(f"PROCESS {split.upper()}")

    input_path = (
        PROCESSED_DIR
        / f"{split}.parquet"
    )

    output_path = (
        TEMPORAL_DIR
        / f"{split}.parquet"
    )

    columns = (
        META_COLUMNS
        + base_features
    )

    df = pd.read_parquet(
        input_path,
        columns=columns,
    )

    df = (
        df
        .sort_values(
            ["case", "Id", "Time"]
        )
        .reset_index(drop=True)
    )

    if split == "test":
        validate_no_future_leakage(
            df,
            base_features,
        )

    input_rows = len(df)

    trajectory_count = (
        df["trajectory_key"]
        .nunique()
    )

    writer = None
    output_rows = 0
    completed = 0

    try:
        for _, trajectory in df.groupby(
            "trajectory_key",
            sort=False,
        ):
            result = build_features(
                trajectory,
                base_features,
            )

            table = pa.Table.from_pandas(
                result,
                preserve_index=False,
            )

            if writer is None:
                writer = pq.ParquetWriter(
                    output_path,
                    table.schema,
                    compression="zstd",
                )

            writer.write_table(table)

            output_rows += len(result)
            completed += 1

            if completed % 25 == 0:
                print(
                    f"[PROGRESS] "
                    f"{completed}/{trajectory_count}"
                )

    finally:
        if writer is not None:
            writer.close()

    expected_removed = (
        trajectory_count
        * WARMUP_ROWS
    )

    expected_output = (
        input_rows
        - expected_removed
    )

    if output_rows != expected_output:
        raise ValueError(
            f"{split} output row mismatch: "
            f"expected={expected_output}, "
            f"actual={output_rows}"
        )

    size_mb = (
        output_path.stat().st_size
        / 1024
        / 1024
    )

    print(
        f"[PASS] {split}: "
        f"{output_rows:,} rows, "
        f"{trajectory_count} trajectories, "
        f"{size_mb:.1f} MB"
    )

    return {
        "split": split,
        "trajectory_count": trajectory_count,
        "input_rows": input_rows,
        "removed_warmup_rows": expected_removed,
        "output_rows": output_rows,
        "feature_count": TEMPORAL_FEATURE_COUNT,
        "file_size_mb": size_mb,
    }


def main() -> None:

    section("TEP TEMPORAL FEATURE BUILDER")

    TEMPORAL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    base_features = load_base_features()

    print(
        f"Base features     : {len(base_features)}"
    )

    print(
        f"Temporal features : {TEMPORAL_FEATURE_COUNT}"
    )

    schema = build_schema(
        base_features
    )

    schema.to_csv(
        TEMPORAL_SCHEMA_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print(
        f"[SAVE] {TEMPORAL_SCHEMA_PATH}"
    )

    results = []

    for split in [
        "train",
        "validation",
        "test",
    ]:
        results.append(
            process_split(
                split,
                base_features,
            )
        )

    summary = pd.DataFrame(
        results
    )

    summary.to_csv(
        SUMMARY_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    section("COMPLETE")

    print(
        summary.to_string(
            index=False
        )
    )

    print()
    print(
        "[PASS] Temporal feature dataset completed"
    )


if __name__ == "__main__":
    main()
```

### 6.14 src/evaluation/05-compare_temporal.py

```python
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

BASELINE_PATH = (
    PROJECT_ROOT
    / "reports"
    / "04-baseline"
    / "baseline_metrics.csv"
)

TEMPORAL_PATH = (
    PROJECT_ROOT
    / "reports"
    / "05-temporal"
    / "temporal_metrics.csv"
)

OUTPUT_PATH = (
    PROJECT_ROOT
    / "reports"
    / "05-temporal"
    / "comparison_vs_baseline.csv"
)


def main():

    baseline = pd.read_csv(
        BASELINE_PATH
    )

    temporal = pd.read_csv(
        TEMPORAL_PATH
    )

    # 대표 Baseline은 Model B
    baseline = baseline[
        baseline["feature_set"]
        == "model_b"
    ]

    rows = []

    # RUL
    b = baseline[
        baseline["target"]
        == "rul_hours"
    ].iloc[0]

    t = temporal[
        temporal["target"]
        == "rul_hours"
    ].iloc[0]

    rows.append(
        {
            "target": "rul_hours",
            "metric": "MAE",
            "baseline": b["test_mae"],
            "temporal": t["test_mae"],
            "improvement_percent":
                (
                    (
                        b["test_mae"]
                        - t["test_mae"]
                    )
                    / b["test_mae"]
                    * 100
                ),
        }
    )

    for target in [
        "failure_within_4h",
        "failure_within_2h",
        "failure_within_1h",
    ]:

        b = baseline[
            baseline["target"]
            == target
        ].iloc[0]

        t = temporal[
            temporal["target"]
            == target
        ].iloc[0]

        rows.append(
            {
                "target": target,
                "metric":
                    "Average Precision",
                "baseline":
                    b[
                        "test_average_precision"
                    ],
                "temporal":
                    t[
                        "test_average_precision"
                    ],
                "improvement_percent":
                    (
                        (
                            t[
                                "test_average_precision"
                            ]
                            -
                            b[
                                "test_average_precision"
                            ]
                        )
                        /
                        b[
                            "test_average_precision"
                        ]
                        * 100
                    ),
            }
        )

    comparison = pd.DataFrame(
        rows
    )

    comparison.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print(
        comparison.to_string(
            index=False
        )
    )

    print()
    print(
        f"[SAVE] {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
```

### 6.15 src/evaluation/06-validate_final_prediction.py

```python
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import xgboost as xgb


PROJECT_ROOT = Path(__file__).resolve().parents[2]

VERSION = "v1.0.0"

PRODUCTION_DIR = (
    PROJECT_ROOT
    / "models"
    / "production"
    / VERSION
)

TEST_DATA_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "temporal"
    / "test.parquet"
)

FEATURE_LIST_PATH = (
    PRODUCTION_DIR
    / "feature_list.json"
)

FEATURE_SCHEMA_PATH = (
    PRODUCTION_DIR
    / "feature_schema.csv"
)

THRESHOLD_PATH = (
    PRODUCTION_DIR
    / "thresholds.json"
)

METADATA_PATH = (
    PRODUCTION_DIR
    / "metadata.json"
)

OUTPUT_PATH = (
    PROJECT_ROOT
    / "reports"
    / "06-final-model"
    / "sample_prediction.json"
)

MODEL_FILES = {
    "rul_hours":
        "rul_hours.json",

    "failure_within_4h":
        "failure_within_4h.json",

    "failure_within_2h":
        "failure_within_2h.json",

    "failure_within_1h":
        "failure_within_1h.json",
}


def load_json(
    path: Path,
) -> dict:
    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def load_model(
    filename: str,
) -> xgb.Booster:
    path = (
        PRODUCTION_DIR
        / filename
    )

    if not path.exists():
        raise FileNotFoundError(
            f"Model not found: {path}"
        )

    model = xgb.Booster()
    model.load_model(path)

    return model


def load_sample(
    features: list[str],
) -> pd.DataFrame:
    """
    test.parquet 전체를 읽지 않고
    마지막 row group의 마지막 행 하나만 사용.
    """

    parquet_file = pq.ParquetFile(
        TEST_DATA_PATH
    )

    columns = [
        "trajectory_key",
        "Time",
        "rul_hours",
        *features,
    ]

    table = parquet_file.read_row_group(
        parquet_file.num_row_groups - 1,
        columns=columns,
    )

    df = table.to_pandas()

    if df.empty:
        raise ValueError(
            "No sample row found"
        )

    return df.tail(1).copy()


def get_threshold(
    thresholds: dict,
    target: str,
) -> float:
    """
    thresholds.json의 구조가
    {target: number}
    또는
    {target: {threshold: number}}
    둘 중 어느 형태여도 처리.
    """

    value = thresholds[target]

    if isinstance(value, dict):
        if "threshold" not in value:
            raise KeyError(
                f"No threshold value for {target}"
            )

        value = value["threshold"]

    return float(value)


def predict_score(
    model: xgb.Booster,
    matrix: xgb.DMatrix,
) -> float:
    return float(
        model.predict(
            matrix
        )[0]
    )


def determine_status(
    risk_4h: float,
    risk_2h: float,
    risk_1h: float,
    threshold_4h: float,
    threshold_2h: float,
    threshold_1h: float,
) -> tuple[str, str]:

    if risk_1h >= threshold_1h:
        return (
            "CRITICAL",
            "failure_within_1h",
        )

    if risk_2h >= threshold_2h:
        return (
            "WARNING",
            "failure_within_2h",
        )

    if risk_4h >= threshold_4h:
        return (
            "CAUTION",
            "failure_within_4h",
        )

    return (
        "NORMAL",
        "failure_within_4h",
    )


def parse_feature_name(
    feature: str,
) -> tuple[str, str, int | None]:
    """
    Feature schema에 설명용 필드가 없을 경우를 위한 fallback.

    이름에서 가능한 범위까지만 추출한다.
    정확한 명명 규칙을 모르는 경우에도 원본 feature 문자열은 보존한다.
    """

    lowered = feature.lower()

    transform_candidates = [
        "mean",
        "std",
        "delta",
        "rate",
        "slope",
        "max",
        "min",
    ]

    transform = "current"

    for candidate in transform_candidates:
        if candidate in lowered:
            transform = candidate
            break

    match = re.search(
        r"(5|15|30|60)\s*m",
        lowered,
    )

    if match:
        window_minutes = int(
            match.group(1)
        )
    else:
        window_minutes = None

    source_feature = feature

    separators = [
        "__",
        "_mean",
        "_std",
        "_delta",
        "_rate",
        "_slope",
        "_max",
        "_min",
    ]

    for separator in separators:
        if separator in source_feature:
            source_feature = (
                source_feature
                .split(separator)[0]
            )
            break

    return (
        source_feature,
        transform,
        window_minutes,
    )


def build_feature_metadata(
    features: list[str],
) -> dict[str, dict]:
    """
    feature_schema.csv에 설명 가능한 열이 있으면 사용하고,
    없으면 feature 이름으로 fallback.
    """

    result = {}

    if FEATURE_SCHEMA_PATH.exists():
        schema = pd.read_csv(
            FEATURE_SCHEMA_PATH
        )

        if "feature" in schema.columns:
            for _, row in schema.iterrows():
                feature = str(
                    row["feature"]
                )

                source_feature = (
                    row.get(
                        "source_feature",
                        None,
                    )
                )

                transform = (
                    row.get(
                        "transform",
                        None,
                    )
                )

                window = (
                    row.get(
                        "window_minutes",
                        None,
                    )
                )

                parsed = parse_feature_name(
                    feature
                )

                if (
                    source_feature is None
                    or pd.isna(source_feature)
                ):
                    source_feature = parsed[0]

                if (
                    transform is None
                    or pd.isna(transform)
                ):
                    transform = parsed[1]

                if (
                    window is None
                    or pd.isna(window)
                ):
                    window = parsed[2]

                if pd.isna(window):
                    window = None

                if window is not None:
                    try:
                        window = int(
                            window
                        )
                    except Exception:
                        window = None

                result[feature] = {
                    "source_feature":
                        str(source_feature),

                    "transform":
                        str(transform),

                    "window_minutes":
                        window,
                }

    for feature in features:
        if feature not in result:
            parsed = parse_feature_name(
                feature
            )

            result[feature] = {
                "source_feature":
                    parsed[0],

                "transform":
                    parsed[1],

                "window_minutes":
                    parsed[2],
            }

    return result


def calculate_top_risk_factors(
    model: xgb.Booster,
    matrix: xgb.DMatrix,
    features: list[str],
    feature_metadata: dict[str, dict],
    top_k: int = 5,
) -> list[dict]:

    contributions = model.predict(
        matrix,
        pred_contribs=True,
    )

    shap_values = (
        contributions[0, :-1]
    )

    base_value = float(
        contributions[0, -1]
    )

    raw_prediction = float(
        model.predict(
            matrix,
            output_margin=True,
        )[0]
    )

    reconstructed = float(
        shap_values.sum()
        + base_value
    )

    if not np.isclose(
        raw_prediction,
        reconstructed,
        rtol=1e-4,
        atol=1e-4,
    ):
        raise ValueError(
            "SHAP additivity validation failed"
        )

    rows = []

    for feature, shap_value in zip(
        features,
        shap_values,
    ):
        shap_value = float(
            shap_value
        )

        # 위험도를 증가시키는 Feature만 주요 위험요인으로 사용
        if shap_value <= 0:
            continue

        metadata = (
            feature_metadata[feature]
        )

        rows.append(
            {
                "feature": feature,

                "source_feature":
                    metadata[
                        "source_feature"
                    ],

                "transform":
                    metadata[
                        "transform"
                    ],

                "window_minutes":
                    metadata[
                        "window_minutes"
                    ],

                "shap_value":
                    shap_value,
            }
        )

    rows.sort(
        key=lambda x: x["shap_value"],
        reverse=True,
    )

    top_rows = rows[:top_k]

    for index, row in enumerate(
        top_rows,
        start=1,
    ):
        row["rank"] = index

    # rank를 첫 번째 필드처럼 보기 좋게 정리
    formatted = []

    for row in top_rows:
        formatted.append(
            {
                "rank":
                    row["rank"],

                "feature":
                    row["feature"],

                "source_feature":
                    row["source_feature"],

                "transform":
                    row["transform"],

                "window_minutes":
                    row["window_minutes"],

                "shap_value":
                    row["shap_value"],
            }
        )

    return formatted


def main() -> None:
    print("=" * 80)
    print("FINAL PRODUCTION PREDICTION VALIDATION")
    print("=" * 80)

    feature_payload = load_json(
        FEATURE_LIST_PATH
    )

    features = (
        feature_payload[
            "features"
        ]
    )

    if len(features) != 728:
        raise ValueError(
            f"Expected 728 features, got {len(features)}"
        )

    thresholds = load_json(
        THRESHOLD_PATH
    )

    metadata = load_json(
        METADATA_PATH
    )

    feature_metadata = (
        build_feature_metadata(
            features
        )
    )

    row = load_sample(
        features
    )

    X = row[features]

    matrix = xgb.DMatrix(
        X,
        feature_names=features,
    )

    models = {
        target: load_model(
            filename
        )
        for target, filename
        in MODEL_FILES.items()
    }

    # --------------------------------------------------------
    # RUL
    # --------------------------------------------------------

    rul_prediction = (
        predict_score(
            models["rul_hours"],
            matrix,
        )
    )

    # RUL은 물리적으로 음수가 될 수 없으므로
    # 표시값만 0 이상으로 제한
    rul_prediction = max(
        0.0,
        rul_prediction,
    )

    # --------------------------------------------------------
    # Risk scores
    # --------------------------------------------------------

    risk_4h = predict_score(
        models[
            "failure_within_4h"
        ],
        matrix,
    )

    risk_2h = predict_score(
        models[
            "failure_within_2h"
        ],
        matrix,
    )

    risk_1h = predict_score(
        models[
            "failure_within_1h"
        ],
        matrix,
    )

    threshold_4h = get_threshold(
        thresholds,
        "failure_within_4h",
    )

    threshold_2h = get_threshold(
        thresholds,
        "failure_within_2h",
    )

    threshold_1h = get_threshold(
        thresholds,
        "failure_within_1h",
    )

    status, explanation_target = (
        determine_status(
            risk_4h,
            risk_2h,
            risk_1h,
            threshold_4h,
            threshold_2h,
            threshold_1h,
        )
    )

    # --------------------------------------------------------
    # SHAP explanation
    # --------------------------------------------------------

    risk_factors = (
        calculate_top_risk_factors(
            models[
                explanation_target
            ],
            matrix,
            features,
            feature_metadata,
            top_k=5,
        )
    )

    # --------------------------------------------------------
    # Final prediction result
    # --------------------------------------------------------

    result = {
        "schema_version": "1.0",

        "model_version": (
            metadata.get(
                "version",
                VERSION,
            )
        ),

        "trajectory_key": str(
            row[
                "trajectory_key"
            ].iloc[0]
        ),

        "timestamp_hours": float(
            row["Time"].iloc[0]
        ),

        "rul": {
            "hours":
                rul_prediction,
        },

        "risk": {
            "failure_within_4h": {
                "score":
                    risk_4h,

                "threshold":
                    threshold_4h,

                "alert":
                    bool(
                        risk_4h
                        >= threshold_4h
                    ),
            },

            "failure_within_2h": {
                "score":
                    risk_2h,

                "threshold":
                    threshold_2h,

                "alert":
                    bool(
                        risk_2h
                        >= threshold_2h
                    ),
            },

            "failure_within_1h": {
                "score":
                    risk_1h,

                "threshold":
                    threshold_1h,

                "alert":
                    bool(
                        risk_1h
                        >= threshold_1h
                    ),
            },
        },

        "status":
            status,

        "explanation_model":
            explanation_target,

        "top_risk_factors":
            risk_factors,
    }

    # --------------------------------------------------------
    # Required-field validation
    # --------------------------------------------------------

    required_keys = [
        "model_version",
        "rul",
        "risk",
        "status",
        "top_risk_factors",
    ]

    for key in required_keys:
        if key not in result:
            raise ValueError(
                f"Missing output field: {key}"
            )

    if status not in {
        "NORMAL",
        "CAUTION",
        "WARNING",
        "CRITICAL",
    }:
        raise ValueError(
            f"Invalid status: {status}"
        )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            result,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print()
    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )

    print()
    print("-" * 80)

    print(
        f"True RUL      : "
        f"{float(row['rul_hours'].iloc[0]):.4f} h"
    )

    print(
        f"Predicted RUL : "
        f"{rul_prediction:.4f} h"
    )

    print(
        f"Status        : "
        f"{status}"
    )

    print(
        f"Explanation   : "
        f"{explanation_target}"
    )

    print(
        f"Risk factors  : "
        f"{len(risk_factors)}"
    )

    print(
        f"[SAVE] {OUTPUT_PATH}"
    )

    print()
    print("=" * 80)

    print(
        "[PASS] RUL prediction available"
    )

    print(
        "[PASS] Risk scores available"
    )

    print(
        "[PASS] Status available"
    )

    print(
        "[PASS] Risk factors available"
    )

    print(
        "[PASS] Final prediction contract validated"
    )

    print("=" * 80)


if __name__ == "__main__":
    main()
```

### 6.16 src/training/04-train_baseline.py

```python
from __future__ import annotations

import argparse
import gc
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    median_absolute_error,
    precision_recall_curve,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)


# ============================================================
# Paths
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
METADATA_DIR = PROJECT_ROOT / "data" / "metadata"

MODEL_ROOT = (
    PROJECT_ROOT
    / "models"
    / "candidates"
    / "04-baseline"
)

REPORT_DIR = (
    PROJECT_ROOT
    / "reports"
    / "04-baseline"
)

FEATURE_SCHEMA_PATH = (
    METADATA_DIR
    / "feature_schema.csv"
)


# ============================================================
# Settings
# ============================================================

RANDOM_STATE = 42

MAX_BOOST_ROUNDS = 1000
EARLY_STOPPING_ROUNDS = 50

CLASSIFICATION_TARGETS = {
    "failure_within_4h": 4.0,
    "failure_within_2h": 2.0,
    "failure_within_1h": 1.0,
}

TARGET_COLUMNS = [
    "rul_hours",
    "failure_within_4h",
    "failure_within_2h",
    "failure_within_1h",
]

META_COLUMNS = [
    "trajectory_key",
    "Time",
]


# ============================================================
# Utility
# ============================================================

def section(title: str) -> None:
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def parse_bool_column(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series

    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .eq("true")
    )


# ============================================================
# CUDA check
# ============================================================

def check_cuda() -> None:
    section("CUDA CHECK")

    print(f"XGBoost version: {xgb.__version__}")

    X = np.array(
        [
            [0.0, 1.0],
            [1.0, 0.0],
            [0.5, 0.5],
            [1.0, 1.0],
        ],
        dtype=np.float32,
    )

    y = np.array(
        [0, 1, 0, 1],
        dtype=np.float32,
    )

    dtrain = xgb.DMatrix(X, label=y)

    params = {
        "objective": "binary:logistic",
        "tree_method": "hist",
        "device": "cuda",
        "verbosity": 1,
    }

    xgb.train(
        params,
        dtrain,
        num_boost_round=2,
    )

    print("[PASS] XGBoost CUDA training available")


# ============================================================
# Feature schema
# ============================================================

def load_feature_sets() -> dict[str, list[str]]:
    schema = pd.read_csv(FEATURE_SCHEMA_PATH)

    schema["model_a_feature"] = parse_bool_column(
        schema["model_a_feature"]
    )

    schema["model_b_feature"] = parse_bool_column(
        schema["model_b_feature"]
    )

    model_a = schema.loc[
        schema["model_a_feature"],
        "column",
    ].tolist()

    model_b = schema.loc[
        schema["model_b_feature"],
        "column",
    ].tolist()

    if len(model_a) != 41:
        raise ValueError(
            f"Model A feature count error: {len(model_a)}"
        )

    if len(model_b) != 52:
        raise ValueError(
            f"Model B feature count error: {len(model_b)}"
        )

    return {
        "model_a": model_a,
        "model_b": model_b,
    }


# ============================================================
# Dataset
# ============================================================

def load_split(
    split: str,
    feature_columns: list[str],
) -> pd.DataFrame:

    path = PROCESSED_DIR / f"{split}.parquet"

    required_columns = (
        feature_columns
        + META_COLUMNS
        + TARGET_COLUMNS
    )

    # 중복 컬럼 방지
    required_columns = list(
        dict.fromkeys(required_columns)
    )

    print(f"[LOAD] {path.name}")

    df = pd.read_parquet(
        path,
        columns=required_columns,
    )

    return df


def build_dmatrix(
    df: pd.DataFrame,
    feature_columns: list[str],
) -> xgb.DMatrix:

    X = df[feature_columns].to_numpy(
        dtype=np.float32,
    )

    return xgb.DMatrix(
        X,
        feature_names=feature_columns,
    )


# ============================================================
# Threshold
# ============================================================

def choose_f1_threshold(
    y_true: np.ndarray,
    probabilities: np.ndarray,
) -> tuple[float, float]:

    precision, recall, thresholds = (
        precision_recall_curve(
            y_true,
            probabilities,
        )
    )

    if len(thresholds) == 0:
        return 0.5, 0.0

    precision = precision[:-1]
    recall = recall[:-1]

    denominator = precision + recall

    f1 = np.divide(
        2.0 * precision * recall,
        denominator,
        out=np.zeros_like(denominator),
        where=denominator > 0,
    )

    best_index = int(np.nanargmax(f1))

    return (
        float(thresholds[best_index]),
        float(f1[best_index]),
    )


# ============================================================
# Prediction
# ============================================================

def predict_best(
    model: xgb.Booster,
    matrix: xgb.DMatrix,
) -> np.ndarray:

    best_iteration = getattr(
        model,
        "best_iteration",
        None,
    )

    if best_iteration is None:
        return model.predict(matrix)

    return model.predict(
        matrix,
        iteration_range=(
            0,
            best_iteration + 1,
        ),
    )


# ============================================================
# Regression metrics
# ============================================================

def regression_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> dict:

    # 실제 RUL은 음수가 될 수 없음
    y_pred = np.clip(
        y_pred,
        a_min=0.0,
        a_max=None,
    )

    mae = mean_absolute_error(
        y_true,
        y_pred,
    )

    median_ae = median_absolute_error(
        y_true,
        y_pred,
    )

    rmse = np.sqrt(
        mean_squared_error(
            y_true,
            y_pred,
        )
    )

    r2 = r2_score(
        y_true,
        y_pred,
    )

    return {
        "mae": float(mae),
        "median_absolute_error": float(median_ae),
        "rmse": float(rmse),
        "r2": float(r2),
    }


# ============================================================
# Classification metrics
# ============================================================

def classification_metrics(
    y_true: np.ndarray,
    probabilities: np.ndarray,
    threshold: float,
) -> dict:

    predicted = (
        probabilities >= threshold
    ).astype(np.int8)

    ap = average_precision_score(
        y_true,
        probabilities,
    )

    roc_auc = roc_auc_score(
        y_true,
        probabilities,
    )

    precision = precision_score(
        y_true,
        predicted,
        zero_division=0,
    )

    recall = recall_score(
        y_true,
        predicted,
        zero_division=0,
    )

    f1 = f1_score(
        y_true,
        predicted,
        zero_division=0,
    )

    tn, fp, fn, tp = confusion_matrix(
        y_true,
        predicted,
        labels=[0, 1],
    ).ravel()

    fpr = (
        fp / (fp + tn)
        if (fp + tn) > 0
        else 0.0
    )

    return {
        "average_precision": float(ap),
        "roc_auc": float(roc_auc),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "point_fpr": float(fpr),
        "tp": int(tp),
        "fp": int(fp),
        "tn": int(tn),
        "fn": int(fn),
    }


# ============================================================
# Event-level metrics
# ============================================================

def event_metrics(
    trajectory_keys: pd.Series,
    rul_hours: pd.Series,
    probabilities: np.ndarray,
    threshold: float,
    horizon_hours: float,
) -> dict:

    evaluation = pd.DataFrame(
        {
            "trajectory_key": trajectory_keys.to_numpy(),
            "rul_hours": rul_hours.to_numpy(),
            "probability": probabilities,
        }
    )

    detected_count = 0
    early_alert_count = 0

    warning_leads = []

    total_trajectories = (
        evaluation["trajectory_key"].nunique()
    )

    for _, group in evaluation.groupby(
        "trajectory_key",
        sort=False,
    ):
        group = group.reset_index(drop=True)

        alerts = (
            group["probability"].to_numpy()
            >= threshold
        )

        # 2개 연속 양성일 때 두 번째 시점에 실제 경고 발생
        sustained = np.zeros(
            len(alerts),
            dtype=bool,
        )

        if len(alerts) >= 2:
            sustained[1:] = (
                alerts[:-1]
                & alerts[1:]
            )

        rul = group[
            "rul_hours"
        ].to_numpy()

        inside_horizon = (
            rul <= horizon_hours
        )

        valid_alerts = np.where(
            sustained & inside_horizon
        )[0]

        if len(valid_alerts) > 0:
            detected_count += 1

            first_alert_index = (
                valid_alerts[0]
            )

            warning_leads.append(
                float(
                    rul[first_alert_index]
                )
            )

        # horizon보다 더 일찍 지속 경고가 있었는지 별도 기록
        if np.any(
            sustained
            & (rul > horizon_hours)
        ):
            early_alert_count += 1

    detection_rate = (
        detected_count
        / total_trajectories
    )

    early_alert_rate = (
        early_alert_count
        / total_trajectories
    )

    median_lead = (
        float(np.median(warning_leads))
        if warning_leads
        else np.nan
    )

    return {
        "event_detection_rate": float(
            detection_rate
        ),
        "median_warning_lead_hours": (
            median_lead
        ),
        "early_alert_trajectory_rate": float(
            early_alert_rate
        ),
        "detected_trajectories": int(
            detected_count
        ),
        "total_trajectories": int(
            total_trajectories
        ),
    }


# ============================================================
# Params
# ============================================================

def regression_params() -> dict:
    return {
        "objective": "reg:squarederror",
        "eval_metric": "mae",
        "tree_method": "hist",
        "device": "cuda",
        "eta": 0.05,
        "max_depth": 8,
        "min_child_weight": 5,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_lambda": 1.0,
        "reg_alpha": 0.0,
        "seed": RANDOM_STATE,
    }


def classification_params(
    scale_pos_weight: float,
) -> dict:

    return {
        "objective": "binary:logistic",
        "eval_metric": "aucpr",
        "tree_method": "hist",
        "device": "cuda",
        "eta": 0.05,
        "max_depth": 8,
        "min_child_weight": 5,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_lambda": 1.0,
        "reg_alpha": 0.0,
        "scale_pos_weight": scale_pos_weight,
        "seed": RANDOM_STATE,
    }


# ============================================================
# Feature-set training
# ============================================================

def train_feature_set(
    feature_set_name: str,
    feature_columns: list[str],
) -> list[dict]:

    section(
        f"TRAINING {feature_set_name.upper()}"
    )

    print(
        f"Feature count: "
        f"{len(feature_columns)}"
    )

    train_df = load_split(
        "train",
        feature_columns,
    )

    validation_df = load_split(
        "validation",
        feature_columns,
    )

    test_df = load_split(
        "test",
        feature_columns,
    )

    section("BUILD DMATRIX")

    dtrain = build_dmatrix(
        train_df,
        feature_columns,
    )

    dvalidation = build_dmatrix(
        validation_df,
        feature_columns,
    )

    dtest = build_dmatrix(
        test_df,
        feature_columns,
    )

    model_dir = (
        MODEL_ROOT
        / feature_set_name
    )

    model_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    results: list[dict] = []

    # ========================================================
    # RUL Regression
    # ========================================================

    section(
        f"{feature_set_name}: RUL REGRESSION"
    )

    y_train = train_df[
        "rul_hours"
    ].to_numpy(dtype=np.float32)

    y_validation = validation_df[
        "rul_hours"
    ].to_numpy(dtype=np.float32)

    y_test = test_df[
        "rul_hours"
    ].to_numpy(dtype=np.float32)

    dtrain.set_label(y_train)
    dvalidation.set_label(
        y_validation
    )

    model = xgb.train(
        regression_params(),
        dtrain,
        num_boost_round=MAX_BOOST_ROUNDS,
        evals=[
            (dtrain, "train"),
            (
                dvalidation,
                "validation",
            ),
        ],
        early_stopping_rounds=(
            EARLY_STOPPING_ROUNDS
        ),
        verbose_eval=50,
    )

    validation_pred = predict_best(
        model,
        dvalidation,
    )

    test_pred = predict_best(
        model,
        dtest,
    )

    validation_result = (
        regression_metrics(
            y_validation,
            validation_pred,
        )
    )

    test_result = regression_metrics(
        y_test,
        test_pred,
    )

    model_path = (
        model_dir
        / "rul_hours.json"
    )

    model.save_model(model_path)

    print()
    print(
        f"Validation MAE: "
        f"{validation_result['mae']:.4f} h"
    )

    print(
        f"Test MAE      : "
        f"{test_result['mae']:.4f} h"
    )

    print(
        f"Test R²       : "
        f"{test_result['r2']:.4f}"
    )

    results.append(
        {
            "feature_set": feature_set_name,
            "feature_count": len(
                feature_columns
            ),
            "task": "regression",
            "target": "rul_hours",
            "best_iteration": getattr(
                model,
                "best_iteration",
                np.nan,
            ),
            "threshold": np.nan,
            "scale_pos_weight": np.nan,

            "validation_mae":
                validation_result["mae"],
            "validation_rmse":
                validation_result["rmse"],
            "validation_r2":
                validation_result["r2"],

            "test_mae":
                test_result["mae"],
            "test_median_absolute_error":
                test_result[
                    "median_absolute_error"
                ],
            "test_rmse":
                test_result["rmse"],
            "test_r2":
                test_result["r2"],
        }
    )

    del model
    gc.collect()

    # ========================================================
    # Classifiers
    # ========================================================

    for (
        target,
        horizon_hours,
    ) in CLASSIFICATION_TARGETS.items():

        section(
            f"{feature_set_name}: {target}"
        )

        y_train = train_df[
            target
        ].to_numpy(
            dtype=np.float32
        )

        y_validation = (
            validation_df[target]
            .to_numpy(
                dtype=np.float32
            )
        )

        y_test = test_df[
            target
        ].to_numpy(
            dtype=np.int8
        )

        positive = float(
            y_train.sum()
        )

        negative = float(
            len(y_train)
            - positive
        )

        scale_pos_weight = (
            negative / positive
        )

        print(
            f"scale_pos_weight = "
            f"{scale_pos_weight:.4f}"
        )

        dtrain.set_label(
            y_train
        )

        dvalidation.set_label(
            y_validation
        )

        model = xgb.train(
            classification_params(
                scale_pos_weight
            ),
            dtrain,
            num_boost_round=(
                MAX_BOOST_ROUNDS
            ),
            evals=[
                (
                    dtrain,
                    "train",
                ),
                (
                    dvalidation,
                    "validation",
                ),
            ],
            early_stopping_rounds=(
                EARLY_STOPPING_ROUNDS
            ),
            verbose_eval=50,
        )

        validation_prob = (
            predict_best(
                model,
                dvalidation,
            )
        )

        test_prob = predict_best(
            model,
            dtest,
        )

        threshold, best_val_f1 = (
            choose_f1_threshold(
                y_validation,
                validation_prob,
            )
        )

        validation_metrics = (
            classification_metrics(
                y_validation.astype(
                    np.int8
                ),
                validation_prob,
                threshold,
            )
        )

        test_metrics = (
            classification_metrics(
                y_test,
                test_prob,
                threshold,
            )
        )

        event_result = event_metrics(
            trajectory_keys=(
                test_df[
                    "trajectory_key"
                ]
            ),
            rul_hours=(
                test_df[
                    "rul_hours"
                ]
            ),
            probabilities=test_prob,
            threshold=threshold,
            horizon_hours=(
                horizon_hours
            ),
        )

        model_path = (
            model_dir
            / f"{target}.json"
        )

        model.save_model(
            model_path
        )

        print()
        print(
            f"Threshold       : "
            f"{threshold:.6f}"
        )

        print(
            f"Validation F1   : "
            f"{best_val_f1:.4f}"
        )

        print(
            f"Test AP         : "
            f"{test_metrics['average_precision']:.4f}"
        )

        print(
            f"Test ROC-AUC    : "
            f"{test_metrics['roc_auc']:.4f}"
        )

        print(
            f"Test Recall     : "
            f"{test_metrics['recall']:.4f}"
        )

        print(
            f"Event Detection : "
            f"{event_result['event_detection_rate']:.4f}"
        )

        print(
            f"Median Lead     : "
            f"{event_result['median_warning_lead_hours']:.4f} h"
        )

        results.append(
            {
                "feature_set": feature_set_name,
                "feature_count": len(
                    feature_columns
                ),
                "task": "classification",
                "target": target,
                "best_iteration": getattr(
                    model,
                    "best_iteration",
                    np.nan,
                ),
                "threshold": threshold,
                "scale_pos_weight":
                    scale_pos_weight,

                "validation_average_precision":
                    validation_metrics[
                        "average_precision"
                    ],
                "validation_roc_auc":
                    validation_metrics[
                        "roc_auc"
                    ],
                "validation_f1":
                    validation_metrics[
                        "f1"
                    ],

                "test_average_precision":
                    test_metrics[
                        "average_precision"
                    ],
                "test_roc_auc":
                    test_metrics[
                        "roc_auc"
                    ],
                "test_precision":
                    test_metrics[
                        "precision"
                    ],
                "test_recall":
                    test_metrics[
                        "recall"
                    ],
                "test_f1":
                    test_metrics[
                        "f1"
                    ],
                "test_point_fpr":
                    test_metrics[
                        "point_fpr"
                    ],

                "event_detection_rate":
                    event_result[
                        "event_detection_rate"
                    ],
                "median_warning_lead_hours":
                    event_result[
                        "median_warning_lead_hours"
                    ],
                "early_alert_trajectory_rate":
                    event_result[
                        "early_alert_trajectory_rate"
                    ],
            }
        )

        del model
        gc.collect()

    del dtrain
    del dvalidation
    del dtest

    del train_df
    del validation_df
    del test_df

    gc.collect()

    return results


# ============================================================
# Main
# ============================================================

def main() -> None:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--feature-set",
        choices=[
            "A",
            "B",
            "all",
        ],
        default="all",
        help=(
            "A = XMEAS only, "
            "B = XMEAS + XMV, "
            "all = both"
        ),
    )

    args = parser.parse_args()

    section("TEP BASELINE TRAINER")

    check_cuda()

    feature_sets = (
        load_feature_sets()
    )

    selected = []

    if args.feature_set in (
        "A",
        "all",
    ):
        selected.append(
            "model_a"
        )

    if args.feature_set in (
        "B",
        "all",
    ):
        selected.append(
            "model_b"
        )

    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    all_results = []

    for feature_set_name in selected:

        result = train_feature_set(
            feature_set_name,
            feature_sets[
                feature_set_name
            ],
        )

        all_results.extend(
            result
        )

        # 중간 결과도 매번 저장
        pd.DataFrame(
            all_results
        ).to_csv(
            REPORT_DIR
            / "baseline_metrics.csv",
            index=False,
            encoding="utf-8-sig",
        )

    section("FINAL RESULT")

    result_df = pd.DataFrame(
        all_results
    )

    print(
        result_df.to_string(
            index=False
        )
    )

    output_path = (
        REPORT_DIR
        / "baseline_metrics.csv"
    )

    result_df.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print(
        f"[SAVE] {output_path}"
    )

    print()
    print(
        "[PASS] Baseline training completed"
    )


if __name__ == "__main__":
    main()
```

### 6.17 src/training/05-train_temporal.py

```python
from __future__ import annotations

import gc
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    median_absolute_error,
    precision_recall_curve,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "temporal"
)

SCHEMA_PATH = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / "temporal_feature_schema.csv"
)

MODEL_DIR = (
    PROJECT_ROOT
    / "models"
    / "candidates"
    / "05-temporal"
)

REPORT_DIR = (
    PROJECT_ROOT
    / "reports"
    / "05-temporal"
)

MAX_ROUNDS = 1000
EARLY_STOPPING = 50
RANDOM_STATE = 42
MAX_BIN = 256

TARGETS = {
    "failure_within_4h": 4.0,
    "failure_within_2h": 2.0,
    "failure_within_1h": 1.0,
}


def section(title):
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def feature_columns():
    schema = pd.read_csv(SCHEMA_PATH)

    return schema[
        schema["model_feature"] == True
    ]["feature"].tolist()


def load(split, features):
    columns = (
        [
            "trajectory_key",
            "Time",
            "rul_hours",
            "failure_within_4h",
            "failure_within_2h",
            "failure_within_1h",
        ]
        + features
    )

    print(f"[LOAD] {split}.parquet")

    return pd.read_parquet(
        DATA_DIR / f"{split}.parquet",
        columns=columns,
    )


def choose_threshold(y, probability):
    precision, recall, thresholds = (
        precision_recall_curve(
            y,
            probability,
        )
    )

    precision = precision[:-1]
    recall = recall[:-1]

    denominator = precision + recall

    f1 = np.divide(
        2 * precision * recall,
        denominator,
        out=np.zeros_like(denominator),
        where=denominator > 0,
    )

    index = int(np.nanargmax(f1))

    return (
        float(thresholds[index]),
        float(f1[index]),
    )


def classification_metrics(
    y,
    probability,
    threshold,
):
    pred = (
        probability >= threshold
    ).astype(np.int8)

    tn, fp, fn, tp = confusion_matrix(
        y,
        pred,
        labels=[0, 1],
    ).ravel()

    return {
        "average_precision":
            average_precision_score(
                y,
                probability,
            ),

        "roc_auc":
            roc_auc_score(
                y,
                probability,
            ),

        "precision":
            precision_score(
                y,
                pred,
                zero_division=0,
            ),

        "recall":
            recall_score(
                y,
                pred,
                zero_division=0,
            ),

        "f1":
            f1_score(
                y,
                pred,
                zero_division=0,
            ),

        "point_fpr":
            fp / (fp + tn),
    }


def event_metrics(
    df,
    probability,
    threshold,
    horizon,
):
    temp = pd.DataFrame(
        {
            "trajectory_key":
                df["trajectory_key"].to_numpy(),

            "rul_hours":
                df["rul_hours"].to_numpy(),

            "probability":
                probability,
        }
    )

    detected = 0
    leads = []

    for _, group in temp.groupby(
        "trajectory_key",
        sort=False,
    ):
        alert = (
            group["probability"]
            .to_numpy()
            >= threshold
        )

        sustained = np.zeros(
            len(alert),
            dtype=bool,
        )

        sustained[1:] = (
            alert[:-1]
            & alert[1:]
        )

        rul = (
            group["rul_hours"]
            .to_numpy()
        )

        indexes = np.where(
            sustained
            & (rul <= horizon)
        )[0]

        if len(indexes):
            detected += 1

            leads.append(
                float(
                    rul[indexes[0]]
                )
            )

    total = (
        temp["trajectory_key"]
        .nunique()
    )

    return {
        "event_detection_rate":
            detected / total,

        "median_warning_lead_hours":
            float(np.median(leads))
            if leads
            else np.nan,
    }


def regression_params():
    return {
        "objective": "reg:squarederror",
        "eval_metric": "mae",
        "tree_method": "hist",
        "device": "cuda",
        "max_bin": MAX_BIN,
        "eta": 0.05,
        "max_depth": 8,
        "min_child_weight": 5,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "seed": RANDOM_STATE,
    }


def classifier_params(weight):
    return {
        "objective": "binary:logistic",
        "eval_metric": "aucpr",
        "tree_method": "hist",
        "device": "cuda",
        "max_bin": MAX_BIN,
        "eta": 0.05,
        "max_depth": 8,
        "min_child_weight": 5,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "scale_pos_weight": weight,
        "seed": RANDOM_STATE,
    }


def main():

    section("TEMPORAL MODEL TRAINING")

    features = feature_columns()

    if len(features) != 728:
        raise ValueError(
            f"Expected 728 features, got {len(features)}"
        )

    train = load("train", features)
    val = load("validation", features)
    test = load("test", features)

    X_train = train[
        features
    ].to_numpy(dtype=np.float32)

    X_val = val[
        features
    ].to_numpy(dtype=np.float32)

    X_test = test[
        features
    ].to_numpy(dtype=np.float32)

    MODEL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    results = []
    thresholds = {}

    # ========================================================
    # RUL
    # ========================================================

    section("RUL")

    y_train = train[
        "rul_hours"
    ].to_numpy(dtype=np.float32)

    y_val = val[
        "rul_hours"
    ].to_numpy(dtype=np.float32)

    y_test = test[
        "rul_hours"
    ].to_numpy(dtype=np.float32)

    dtrain = xgb.QuantileDMatrix(
        X_train,
        y_train,
        max_bin=MAX_BIN,
    )

    dval = xgb.QuantileDMatrix(
        X_val,
        y_val,
        ref=dtrain,
        max_bin=MAX_BIN,
    )

    dtest = xgb.QuantileDMatrix(
        X_test,
        ref=dtrain,
        max_bin=MAX_BIN,
    )

    started = time.perf_counter()

    model = xgb.train(
        regression_params(),
        dtrain,
        num_boost_round=MAX_ROUNDS,
        evals=[
            (dtrain, "train"),
            (dval, "validation"),
        ],
        early_stopping_rounds=
            EARLY_STOPPING,
        verbose_eval=50,
    )

    training_seconds = (
        time.perf_counter()
        - started
    )

    prediction = model.predict(
        dtest,
        iteration_range=(
            0,
            model.best_iteration + 1,
        ),
    )

    prediction = np.clip(
        prediction,
        0,
        None,
    )

    mae = mean_absolute_error(
        y_test,
        prediction,
    )

    rmse = np.sqrt(
        mean_squared_error(
            y_test,
            prediction,
        )
    )

    r2 = r2_score(
        y_test,
        prediction,
    )

    median_ae = (
        median_absolute_error(
            y_test,
            prediction,
        )
    )

    model.save_model(
        MODEL_DIR / "rul_hours.json"
    )

    results.append(
        {
            "task": "regression",
            "target": "rul_hours",
            "feature_count": 728,
            "best_iteration":
                model.best_iteration,
            "training_seconds":
                training_seconds,
            "test_mae": mae,
            "test_median_absolute_error":
                median_ae,
            "test_rmse": rmse,
            "test_r2": r2,
        }
    )

    print(
        f"MAE={mae:.4f} h | "
        f"R²={r2:.6f}"
    )

    del model
    gc.collect()

    # ========================================================
    # Classification
    # ========================================================

    for target, horizon in TARGETS.items():

        section(target)

        y_train = train[
            target
        ].to_numpy(dtype=np.float32)

        y_val = val[
            target
        ].to_numpy(dtype=np.float32)

        y_test = test[
            target
        ].to_numpy(dtype=np.int8)

        positive = y_train.sum()
        negative = len(y_train) - positive

        weight = (
            negative / positive
        )

        dtrain.set_label(y_train)
        dval.set_label(y_val)

        started = time.perf_counter()

        model = xgb.train(
            classifier_params(
                weight
            ),
            dtrain,
            num_boost_round=MAX_ROUNDS,
            evals=[
                (dtrain, "train"),
                (dval, "validation"),
            ],
            early_stopping_rounds=
                EARLY_STOPPING,
            verbose_eval=50,
        )

        training_seconds = (
            time.perf_counter()
            - started
        )

        val_prob = model.predict(
            dval,
            iteration_range=(
                0,
                model.best_iteration + 1,
            ),
        )

        test_prob = model.predict(
            dtest,
            iteration_range=(
                0,
                model.best_iteration + 1,
            ),
        )

        threshold, val_f1 = (
            choose_threshold(
                y_val,
                val_prob,
            )
        )

        thresholds[target] = threshold

        metrics = classification_metrics(
            y_test,
            test_prob,
            threshold,
        )

        events = event_metrics(
            test,
            test_prob,
            threshold,
            horizon,
        )

        model.save_model(
            MODEL_DIR
            / f"{target}.json"
        )

        results.append(
            {
                "task":
                    "classification",

                "target":
                    target,

                "feature_count":
                    728,

                "best_iteration":
                    model.best_iteration,

                "training_seconds":
                    training_seconds,

                "threshold":
                    threshold,

                "validation_f1":
                    val_f1,

                "test_average_precision":
                    metrics[
                        "average_precision"
                    ],

                "test_roc_auc":
                    metrics[
                        "roc_auc"
                    ],

                "test_precision":
                    metrics[
                        "precision"
                    ],

                "test_recall":
                    metrics[
                        "recall"
                    ],

                "test_f1":
                    metrics["f1"],

                "test_point_fpr":
                    metrics[
                        "point_fpr"
                    ],

                "event_detection_rate":
                    events[
                        "event_detection_rate"
                    ],

                "median_warning_lead_hours":
                    events[
                        "median_warning_lead_hours"
                    ],
            }
        )

        print(
            f"AP={metrics['average_precision']:.6f} | "
            f"F1={metrics['f1']:.6f} | "
            f"Event={events['event_detection_rate']:.4f}"
        )

        del model
        gc.collect()

    # ========================================================
    # Save
    # ========================================================

    result = pd.DataFrame(
        results
    )

    metrics_path = (
        REPORT_DIR
        / "temporal_metrics.csv"
    )

    result.to_csv(
        metrics_path,
        index=False,
        encoding="utf-8-sig",
    )

    with open(
        REPORT_DIR / "thresholds.json",
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            thresholds,
            file,
            indent=2,
        )

    section("FINAL RESULT")

    print(
        result.to_string(
            index=False
        )
    )

    print()
    print(
        "[PASS] Temporal model training complete"
    )


if __name__ == "__main__":
    main()
```

---

## 7. 모델 산출물 및 리포트

### 7.1 models/production/v1.0.0/metadata.json

```json
{
  "version": "v1.0.0",
  "created_at_utc": "2026-09-07T12:04:07.277084+00:00",
  "git_commit": "b109db1ca055f69463944444171dcc76fc02c695",
  "model_family": "XGBoost",
  "feature_set": "temporal",
  "feature_count": 728,
  "sampling_interval_minutes": 3,
  "warmup_minutes": 60,
  "training_cases": [
    "case1",
    "case2",
    "case3",
    "case4",
    "case5",
    "case6"
  ],
  "models": {
    "rul": "rul_hours.json",
    "failure_within_4h": "failure_within_4h.json",
    "failure_within_2h": "failure_within_2h.json",
    "failure_within_1h": "failure_within_1h.json"
  },
  "thresholds": {
    "failure_within_4h": 0.6227655410766602,
    "failure_within_2h": 0.6104410290718079,
    "failure_within_1h": 0.7830277681350708
  },
  "test_metrics": {
    "rul_hours": {
      "test_mae": 2.1876509189605717,
      "test_rmse": 3.248124094748797,
      "test_r2": 0.9930388331413268
    },
    "failure_within_4h": {
      "test_average_precision": 0.9947744395236096,
      "test_roc_auc": 0.9998346421006136,
      "test_f1": 0.9619073348642442,
      "event_detection_rate": 1.0
    },
    "failure_within_2h": {
      "test_average_precision": 0.9832703097364448,
      "test_roc_auc": 0.999739168307588,
      "test_f1": 0.9275888917726448,
      "event_detection_rate": 1.0
    },
    "failure_within_1h": {
      "test_average_precision": 0.9647654284608465,
      "test_roc_auc": 0.999732350213379,
      "test_f1": 0.8992950654582075,
      "event_detection_rate": 1.0
    }
  },
  "source_candidate": "models/candidates/05-temporal",
  "feature_list_file": "feature_list.json",
  "feature_schema_file": "feature_schema.csv"
}
```

### 7.2 models/production/v1.0.0/thresholds.json (= reports/05-temporal/thresholds.json)

```json
{
  "failure_within_4h": 0.6227655410766602,
  "failure_within_2h": 0.6104410290718079,
  "failure_within_1h": 0.7830277681350708
}
```

### 7.3 models/production/v1.0.0/prediction_schema.json

```json
{
  "schema_version": "1.0",
  "model_version": "string",
  "trajectory_key": "string",
  "timestamp_hours": "number",
  "rul": {
    "hours": "number"
  },
  "risk": {
    "failure_within_4h": {
      "score": "number",
      "threshold": "number",
      "alert": "boolean"
    },
    "failure_within_2h": {
      "score": "number",
      "threshold": "number",
      "alert": "boolean"
    },
    "failure_within_1h": {
      "score": "number",
      "threshold": "number",
      "alert": "boolean"
    }
  },
  "status": "NORMAL | CAUTION | WARNING | CRITICAL",
  "explanation_model": "failure_within_4h | failure_within_2h | failure_within_1h",
  "top_risk_factors": [
    {
      "rank": "integer",
      "feature": "string",
      "source_feature": "string",
      "transform": "string",
      "window_minutes": "integer | null",
      "shap_value": "number"
    }
  ]
}
```

> `models/production/v1.0.0/feature_list.json`(734줄, `features` 배열에 728개 feature명 순서대로 저장)과 `feature_schema.csv`(729줄, feature명/원본변수/변환종류/window)는 §8.3의 `data/metadata/temporal_feature_schema.csv`와 사실상 동일한 스키마를 가진 대용량 파일이라 여기서는 생략한다. 필요하면 로컬 저장소에서 직접 확인.

### 7.4 reports/04-baseline/baseline_metrics.csv (Baseline Model A/B 전체 8모델 결과, 원본 CSV 그대로)

```csv
feature_set,feature_count,task,target,best_iteration,threshold,scale_pos_weight,validation_mae,validation_rmse,validation_r2,test_mae,test_median_absolute_error,test_rmse,test_r2,validation_average_precision,validation_roc_auc,validation_f1,test_average_precision,test_roc_auc,test_precision,test_recall,test_f1,test_point_fpr,event_detection_rate,median_warning_lead_hours,early_alert_trajectory_rate
model_a,41,regression,rul_hours,999,,,3.397573709487915,5.248310725596581,0.9819957613945007,3.206362247467041,2.0646934509277344,4.975080955268427,0.9839053750038147,,,,,,,,,,,,
model_a,41,classification,failure_within_4h,328,0.8497931957244873,32.10871674261355,,,,,,,,0.9910015368979076,0.9997060454375072,0.948017259091843,0.9902449427462824,0.9996997495173277,0.9319357834682235,0.9637760702524698,0.9475885328836425,0.0021917737986900626,1.0,3.950000000000003,0.6444444444444445
model_a,41,classification,failure_within_2h,264,0.8504828214645386,64.41548559479554,,,,,,,,0.9676220141115928,0.999490491073396,0.8974493820667894,0.9744282679672266,0.9995925441528197,0.8550585984214303,0.9693600867678959,0.9086287965433981,0.002549893333669953,1.0,2.0,0.8111111111111111
model_a,41,classification,failure_within_1h,298,0.8888468742370605,126.72972666439833,,,,,,,,0.9201797037119107,0.9993588870041031,0.8444100978876867,0.9381247002532267,0.9995234517353988,0.7968267959453503,0.9576271186440678,0.8698580707240798,0.0019251890736123813,1.0,1.0,0.7333333333333333
model_b,52,regression,rul_hours,999,,,3.2281906604766846,4.949651324389651,0.9839865565299988,3.0446279048919678,1.986978530883789,4.693102527564097,0.9856780767440796,,,,,,,,,,,,
model_b,52,classification,failure_within_4h,175,0.9371151924133301,32.10871674261355,,,,,,,,0.9911802042424915,0.9997100698773715,0.9500312738897769,0.9907311270097799,0.9997183067118287,0.9522637122144714,0.9552689352360044,0.9537639564353723,0.0014910897772764753,1.0,3.924999999999997,0.4888888888888889
model_b,52,classification,failure_within_2h,436,0.7543125748634338,64.41548559479554,,,,,,,,0.9716236653838964,0.999558034195089,0.910862409479921,0.9775399312946134,0.9996426314899933,0.866892545982575,0.9712581344902386,0.9161125319693094,0.002314259626268109,1.0,2.0,0.7777777777777778
model_b,52,classification,failure_within_1h,275,0.9023092985153198,126.72972666439833,,,,,,,,0.9266036071910131,0.9993908913574131,0.8574369531652084,0.9417508732832123,0.999541182529286,0.7990282685512368,0.958156779661017,0.8713872832369942,0.0019001323828495304,1.0,1.0,0.7
```

### 7.5 reports/05-temporal/temporal_metrics.csv (Temporal 최종 4모델 결과, 원본 CSV 그대로)

```csv
task,target,feature_count,best_iteration,training_seconds,test_mae,test_median_absolute_error,test_rmse,test_r2,threshold,validation_f1,test_average_precision,test_roc_auc,test_precision,test_recall,test_f1,test_point_fpr,event_detection_rate,median_warning_lead_hours
regression,rul_hours,728,998,60.70022759999847,2.1876509189605713,1.5306053161621094,3.2481240947487975,0.9930388331413269,,,,,,,,,,
classification,failure_within_4h,728,594,30.037091000005603,,,,,0.6227655410766602,0.96191452991453,0.9947744395236097,0.9998346421006137,0.9471934025006651,0.977085620197585,0.9619073348642442,0.0017093133899085927,1.0,4.0
classification,failure_within_2h,728,465,23.738613599998644,,,,,0.6104410290718079,0.9250364866657822,0.9832703097364447,0.999739168307588,0.8894972623195619,0.9690889370932755,0.9275888917726447,0.0018824965975145957,1.0,2.0
classification,failure_within_1h,728,513,26.424517799983732,,,,,0.7830277681350708,0.8963703314045239,0.9647654284608463,0.999732350213379,0.8570057581573897,0.9459745762711864,0.8992950654582075,0.0012539079429598119,1.0,1.0
```

### 7.6 reports/05-temporal/comparison_vs_baseline.csv

```csv
target,metric,baseline,temporal,improvement_percent
rul_hours,MAE,3.044627904891968,2.1876509189605717,28.14718293011915
failure_within_4h,Average Precision,0.99073112700978,0.9947744395236096,0.40811400829133193
failure_within_2h,Average Precision,0.9775399312946134,0.9832703097364448,0.5862040269027542
failure_within_1h,Average Precision,0.9417508732832124,0.9647654284608465,2.443805026418373
```

### 7.7 reports/06-final-model/sample_prediction.json (§4.6-10에서 언급한 통합 검증 결과, 실제 저장된 값)

```json
{
  "schema_version": "1.0",
  "model_version": "v1.0.0",
  "trajectory_key": "case6::95",
  "timestamp_hours": 128.8,
  "rul": {
    "hours": 0.35779672861099243
  },
  "risk": {
    "failure_within_4h": {
      "score": 0.9999998807907104,
      "threshold": 0.6227655410766602,
      "alert": true
    },
    "failure_within_2h": {
      "score": 0.9999949932098389,
      "threshold": 0.6104410290718079,
      "alert": true
    },
    "failure_within_1h": {
      "score": 0.999846339225769,
      "threshold": 0.7830277681350708,
      "alert": true
    }
  },
  "status": "CRITICAL",
  "explanation_model": "failure_within_1h",
  "top_risk_factors": [
    {
      "rank": 1,
      "feature": "Product Sep Level",
      "source_feature": "Product Sep Level",
      "transform": "current",
      "window_minutes": null,
      "shap_value": 4.332988739013672
    },
    {
      "rank": 2,
      "feature": "Product Sep Level__max_30m",
      "source_feature": "Product Sep Level",
      "transform": "max",
      "window_minutes": 30,
      "shap_value": 4.043984413146973
    },
    {
      "rank": 3,
      "feature": "Product Sep Level__mean_15m",
      "source_feature": "Product Sep Level",
      "transform": "mean",
      "window_minutes": 15,
      "shap_value": 1.441996693611145
    },
    {
      "rank": 4,
      "feature": "Product Sep Level__min_30m",
      "source_feature": "Product Sep Level",
      "transform": "min",
      "window_minutes": 30,
      "shap_value": 1.0816271305084229
    },
    {
      "rank": 5,
      "feature": "Product Sep Level__mean_30m",
      "source_feature": "Product Sep Level",
      "transform": "mean",
      "window_minutes": 30,
      "shap_value": 1.044765830039978
    }
  ]
}
```

이 예측은 `case6::95` trajectory의 EOL 직전(RUL 약 0.36시간, 즉 약 21분 전) 시점 데이터에 대한 실제 추론 결과다. 세 개의 위험 모델 모두 threshold를 크게 초과해 CRITICAL 상태로 판정했고, `explanation_model`이 `failure_within_1h`로 선택되어 그 모델의 SHAP 상위 5개 위험 요인이 출력되었다. 상위 5개 요인이 모두 `Product Sep Level`(제품 분리기 액위) 관련 feature라는 점에서, 이 trajectory의 실제 열화가 분리기 쪽에서 진행되었음을 보여준다.

### 7.8 models/candidates/, models/production/v1.0.0/의 XGBoost 모델 바이너리(JSON)

다음 파일들은 XGBoost `Booster.save_model()`이 생성한 모델 가중치 JSON(트리 구조 전체를 포함하는 대용량 이진성 데이터)이라 텍스트로 옮기지 않는다. 필요하면 `xgb.Booster().load_model(path)`로 로컬에서 직접 로드해서 사용한다.

```text
models/candidates/04-baseline/model_a/{rul_hours,failure_within_4h,failure_within_2h,failure_within_1h}.json
models/candidates/04-baseline/model_b/{rul_hours,failure_within_4h,failure_within_2h,failure_within_1h}.json
models/candidates/05-temporal/{rul_hours,failure_within_4h,failure_within_2h,failure_within_1h}.json
models/production/v1.0.0/{rul_hours,failure_within_4h,failure_within_2h,failure_within_1h}.json
```

이 중 `models/production/v1.0.0/{rul_hours,failure_within_1h,failure_within_2h,failure_within_4h}.json` 4개가 현재 서비스에 사용해야 할 실제 production 가중치다(§4.6, §7.1의 metadata.json 기준 v1.0.0).

---

## 8. 데이터 메타데이터 스키마 (data/metadata/)

`data/raw/`, `data/processed/`의 원본·가공 데이터 자체는 Git에 포함되지 않는다(§1 참고, 재생성 가능). 여기서는 `data/metadata/`에 커밋되어 있는 6개 스키마/요약 파일을 다룬다. 작은 파일(59줄 이하)은 전체를 옮겼고, 600줄이 넘는 3개 파일은 컬럼 구조·대표 행·총 행수만 기록했다(원본은 로컬 저장소에 그대로 존재).

### 8.1 data/metadata/column_summary.csv (59개 컬럼 전체, 원본 CSV 그대로)

각 컬럼의 전체 공식 데이터(case1~case6) 기준 min/max와 상수 여부.

```csv
column,global_min,global_max,constant_candidate
Id,1.0,100.0,False
Time,0.0,149.05,False
D feed,12.3062324640963,100.0,False
E Feed,8.90594569306517,100.0,False
A Feed,0.0,89.6652640929222,False
A and C Feed,55.7371778212015,97.0374386581446,False
Recycle,0.0,71.166,False
Purge,0.146933771567698,100.0,False
Separator,29.0307876747725,62.045708124707,False
Stripper,41.8340375032455,74.6432212715253,False
Steam,0.0,1.0,False
Reactor Coolant,24.87685387123,61.1318140819933,False
Condenser Coolant,5.60527886672384,100.0,False
Agitator,100.0,100.0,True
msv A Feed,-0.0040526576578617,0.912020443764439,False
msv D Feed,662.300005441103,5886.09016534107,False
msv E Feed,678.939984219222,8448.67566287329,False
msv A and C Feed,8.33656744122066,14.8966449385436,False
Recycle Flow,18.3462747705545,35.2787508779169,False
Reactor Feed Rate,32.9092577695203,54.5311151933523,False
Reactor Pressure,2651.98756745714,2861.39483037812,False
Reactor Level,60.2470239291352,112.342772723529,False
Reactor Temperature,122.698987886491,128.246022513368,False
Purge Rate,-0.0028018794328628,0.919294373849602,False
Product Sep Temp,73.7234179590551,96.4178614919597,False
Product Sep Level,37.2052862445156,139.180088271257,False
Product Sep Pressure,2558.63147479399,2797.63850870596,False
Product Sep Underflow,17.5561500247032,41.268813962441,False
Stripper Level,6.62188752718192,133.108160606811,False
Stripper Pressure,2922.66397868561,3405.68198144452,False
Stripper Underflow,19.2065411090235,36.3931289077752,False
Stripper Temp,49.6863189263505,69.6683372499117,False
Stripper Steam Flow,-4.81174936071038,11.3134088690711,False
Compressor Work,239.557580127562,338.004771845529,False
Reactor Coolant Temp,96.5600491934926,108.619069158679,False
Separator Coolant Temp,44.7446416000405,97.8375319081992,False
Component A to Reactor,23.9147295299338,39.4201597723509,False
Component B to Reactor,4.98859582701345,27.1383946798564,False
Component C to Reactor,10.7321052238731,28.919074042067,False
Component D to Reactor,0.848212615186299,13.7523702897777,False
Component E to Reactor,2.73860127992235,29.4440939182138,False
Component F to Reactor,0.896379330866845,5.69150389420625,False
Component A to Purge,20.7854476491173,42.6620794960276,False
Component B to Purge,8.84274955024014,44.6999268722352,False
Component C to Purge,2.34877075373113,27.4121544876861,False
Component D to Purge,-0.290307177332004,2.91602051382299,False
Component E to Purge,2.46848563942453,27.2073098862875,False
Component F to Purge,1.30250849256323,7.54863215470599,False
Component G to Purge,1.07349707075802,11.5966642397707,False
Component H to Purge,0.262424955718254,6.2240809232377,False
Component D to Product,-0.0369138095843153,0.0677937977785288,False
Component E to Product,0.105868632911378,1.92804500880706,False
Component F to Product,0.0206707656148016,0.468004148503747,False
Component G to Product,9.67905441544916,91.9788017610488,False
Component H to Product,6.18530316508674,87.589395824496,False
Liquid Input Stripper,50.0,150.864208890632,False
Liquid Input Separator,49.9740237932505,147.656884241018,False
Liquid Input Reactor,65.0,107.668820075016,False
```

`Agitator`만 `constant_candidate=True`(전체 데이터에서 100으로 고정) — 이 결과가 §4.4의 Baseline에서 `Agitator`를 제외하는 근거가 되었다.

### 8.2 data/metadata/feature_schema.csv (59개 컬럼 전체, 원본 CSV 그대로)

Baseline Model A/B의 최종 feature 선정 근거. `role`, `tep_variable`(XMEAS/XMV 번호), `model_a_feature`, `model_b_feature`, `note` 컬럼 포함.

```csv
column,dtype,role,tep_variable,model_a_feature,model_b_feature,note
Id,int64,identifier,,False,False,trajectory 식별자. 모델 입력 제외
Time,float64,time,,False,False,경과시간 정보. 모델 입력 제외
D feed,float64,manipulated_variable,XMV(1),False,True,공정 조작/제어 변수. Model B에서만 사용
E Feed,float64,manipulated_variable,XMV(2),False,True,공정 조작/제어 변수. Model B에서만 사용
A Feed,float64,manipulated_variable,XMV(3),False,True,공정 조작/제어 변수. Model B에서만 사용
A and C Feed,float64,manipulated_variable,XMV(4),False,True,공정 조작/제어 변수. Model B에서만 사용
Recycle,float64,manipulated_variable,XMV(5),False,True,공정 조작/제어 변수. Model B에서만 사용
Purge,float64,manipulated_variable,XMV(6),False,True,공정 조작/제어 변수. Model B에서만 사용
Separator,float64,manipulated_variable,XMV(7),False,True,공정 조작/제어 변수. Model B에서만 사용
Stripper,float64,manipulated_variable,XMV(8),False,True,공정 조작/제어 변수. Model B에서만 사용
Steam,int64,manipulated_variable,XMV(9),False,True,공정 조작/제어 변수. Model B에서만 사용
Reactor Coolant,float64,manipulated_variable,XMV(10),False,True,공정 조작/제어 변수. Model B에서만 사용
Condenser Coolant,float64,manipulated_variable,XMV(11),False,True,공정 조작/제어 변수. Model B에서만 사용
Agitator,int64,manipulated_variable,XMV(12),False,False,XMV 변수이나 전체 공식 데이터에서 100으로 고정된 상수이므로 제외
msv A Feed,float64,measured_variable,XMEAS(1),True,True,공정 측정 변수. Model A와 Model B 모두 사용
msv D Feed,float64,measured_variable,XMEAS(2),True,True,공정 측정 변수. Model A와 Model B 모두 사용
msv E Feed,float64,measured_variable,XMEAS(3),True,True,공정 측정 변수. Model A와 Model B 모두 사용
msv A and C Feed,float64,measured_variable,XMEAS(4),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Recycle Flow,float64,measured_variable,XMEAS(5),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Reactor Feed Rate,float64,measured_variable,XMEAS(6),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Reactor Pressure,float64,measured_variable,XMEAS(7),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Reactor Level,float64,measured_variable,XMEAS(8),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Reactor Temperature,float64,measured_variable,XMEAS(9),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Purge Rate,float64,measured_variable,XMEAS(10),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Product Sep Temp,float64,measured_variable,XMEAS(11),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Product Sep Level,float64,measured_variable,XMEAS(12),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Product Sep Pressure,float64,measured_variable,XMEAS(13),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Product Sep Underflow,float64,measured_variable,XMEAS(14),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Stripper Level,float64,measured_variable,XMEAS(15),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Stripper Pressure,float64,measured_variable,XMEAS(16),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Stripper Underflow,float64,measured_variable,XMEAS(17),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Stripper Temp,float64,measured_variable,XMEAS(18),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Stripper Steam Flow,float64,measured_variable,XMEAS(19),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Compressor Work,float64,measured_variable,XMEAS(20),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Reactor Coolant Temp,float64,measured_variable,XMEAS(21),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Separator Coolant Temp,float64,measured_variable,XMEAS(22),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Component A to Reactor,float64,measured_variable,XMEAS(23),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Component B to Reactor,float64,measured_variable,XMEAS(24),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Component C to Reactor,float64,measured_variable,XMEAS(25),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Component D to Reactor,float64,measured_variable,XMEAS(26),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Component E to Reactor,float64,measured_variable,XMEAS(27),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Component F to Reactor,float64,measured_variable,XMEAS(28),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Component A to Purge,float64,measured_variable,XMEAS(29),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Component B to Purge,float64,measured_variable,XMEAS(30),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Component C to Purge,float64,measured_variable,XMEAS(31),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Component D to Purge,float64,measured_variable,XMEAS(32),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Component E to Purge,float64,measured_variable,XMEAS(33),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Component F to Purge,float64,measured_variable,XMEAS(34),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Component G to Purge,float64,measured_variable,XMEAS(35),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Component H to Purge,float64,measured_variable,XMEAS(36),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Component D to Product,float64,measured_variable,XMEAS(37),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Component E to Product,float64,measured_variable,XMEAS(38),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Component F to Product,float64,measured_variable,XMEAS(39),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Component G to Product,float64,measured_variable,XMEAS(40),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Component H to Product,float64,measured_variable,XMEAS(41),True,True,공정 측정 변수. Model A와 Model B 모두 사용
Liquid Input Stripper,int64,degradation_state_candidate,,False,False,RTF 데이터셋의 추가 변수. 열화 정보 누수 가능성이 있으므로 Baseline feature에서 제외
Liquid Input Separator,int64,degradation_state_candidate,,False,False,RTF 데이터셋의 추가 변수. 열화 정보 누수 가능성이 있으므로 Baseline feature에서 제외
Liquid Input Reactor,int64,degradation_state_candidate,,False,False,RTF 데이터셋의 추가 변수. 열화 정보 누수 가능성이 있으므로 Baseline feature에서 제외
```

### 8.3 data/metadata/split_manifest.csv (600 trajectory 전체 — 스키마와 대표 행만 기록)

컬럼: `trajectory_key, case, Id, split`. 총 601행(헤더 포함), 즉 600개 trajectory(§3의 §26 결과와 일치: train 420 / validation 90 / test 90).

```csv
trajectory_key,case,Id,split
case1::1,case1,1,train
case1::2,case1,2,train
case1::3,case1,3,train
case1::4,case1,4,train
... (총 600 행, case1~case6 × Id 1~100)
```

### 8.4 data/metadata/trajectory_summary.csv (600 trajectory 전체 — 스키마와 대표 행만 기록)

컬럼: `trajectory_key, case, Id, row_count, start_time, end_time, duration_hours, missing_count, infinite_count, duplicate_timestamp_count, invalid_interval_count, min_interval_hours, max_interval_hours`. 총 601행(헤더 포함), 600개 trajectory에 대한 데이터 품질 검증 결과(§4.2의 §21 결론과 일치: 결측치/무한값/중복 timestamp/간격 오류 모두 0).

```csv
trajectory_key,case,Id,row_count,start_time,end_time,duration_hours,missing_count,infinite_count,duplicate_timestamp_count,invalid_interval_count,min_interval_hours,max_interval_hours
case1::1,case1,1,2929,0.0,146.4,146.4,0,0,0,0,0.04999999999998295,0.05000000000001137
case1::2,case1,2,2937,0.0,146.8,146.8,0,0,0,0,0.04999999999998295,0.05000000000001137
case1::3,case1,3,2909,0.0,145.4,145.4,0,0,0,0,0.04999999999998295,0.05000000000001137
case1::4,case1,4,2905,0.0,145.2,145.2,0,0,0,0,0.04999999999998295,0.05000000000001137
... (총 600 행)
```

### 8.5 data/metadata/temporal_feature_schema.csv (728개 Temporal feature 전체 — 스키마와 대표 행만 기록)

컬럼: `feature, source_feature, transform, window, model_feature`. 총 729행(헤더 포함), §4.5의 728개 Temporal feature 정의와 정확히 일치(52개 base feature × 14개 파생 = 728, `current` 변환 포함하면 base당 15개 항목이지만 `current`는 원본 컬럼명 그대로이므로 실제로는 base 52 + delta/rate/mean/std/max/min/slope 조합 676 = 728).

```csv
feature,source_feature,transform,window,model_feature
D feed,D feed,current,current,True
D feed__delta_5m,D feed,delta,5m,True
D feed__rate_5m_per_h,D feed,rate,5m,True
D feed__mean_15m,D feed,mean,15m,True
D feed__std_15m,D feed,std,15m,True
D feed__delta_15m,D feed,delta,15m,True
D feed__rate_15m_per_h,D feed,rate,15m,True
D feed__mean_30m,D feed,mean,30m,True
D feed__std_30m,D feed,std,30m,True
... (D feed에 이어서 max_30m, min_30m, delta_60m, rate_60m_per_h, slope_60m_per_h까지, 이후 나머지 51개 base feature에 대해 동일 패턴 반복, 총 728 행)
```

동일한 스키마 구조가 `models/production/v1.0.0/feature_schema.csv`(729행, §7.3 참고)에도 그대로 저장되어 있다.

### 8.6 data/metadata/temporal_dataset_summary.csv (전체, 5줄이라 그대로 포함)

Temporal feature 생성 파이프라인(§4.5, `src/data/05-build_temporal_features.py`)의 실행 결과 요약.

```csv
split,trajectory_count,input_rows,removed_warmup_rows,output_rows,feature_count,file_size_mb
train,420,1126193,8400,1117793,728,3079.9105167388916
validation,90,240672,1800,238872,728,658.4982948303223
test,90,241345,1800,239545,728,660.2860660552979
```

각 trajectory에서 warm-up 20행씩 제거(§4.5 §10)되어 `output_rows = input_rows - trajectory_count × 20`이 정확히 성립한다.

---

## 9. 다음 작업자를 위한 핵심 요약

**지금 당장 이어받을 수 있는 상태**: 데이터 파이프라인(01~07)은 완결되어 있고, production 모델(v1.0.0, 728-feature Temporal XGBoost)과 예측/설명 계약(§4.6, §7.3)도 확정되어 있다. 이 문서 §6의 전체 소스코드와 §7의 모델 메타데이터만 있으면 추론 로직(feature 순서, threshold, 상태 판정, SHAP top-5 추출)을 그대로 재현할 수 있다.

**아직 구현되지 않은 것(11번 이후)**: `src/api`, `src/inference`, `src/monitoring`, `src/streaming`, `src/mlops`, `tests/`, `unity/`, `web/`, `config/`, `notebooks/` — 이들은 저장소에 코드가 전혀 없다. `compose.yaml`과 3개 Dockerfile은 이 모듈들이 이미 존재한다고 가정하고 `CMD ["python", "-m", "src.api.main"]` 등을 실행하므로, 지금 그대로 `docker compose up`하면 kafka만 healthy이고 api/inference/monitor는 재시작을 반복한다(§5.3, §5.4~5.6 참고).

**설계가 이미 끝난 것 (구현 시 그대로 따르면 됨)**:
- Kafka topic 이름/consumer group: `.env.example`(§5.2) — `tep-sensor-data`, `tep-predictions`, `tep-drift-events`, consumer group `inference-service`.
- 추론 입력 feature 순서: `models/production/v1.0.0/feature_list.json`(728개, 순서 고정).
- 추론 출력 스키마: `models/production/v1.0.0/prediction_schema.json`(§7.3), 실제 예시는 `reports/06-final-model/sample_prediction.json`(§7.7).
- 상태 판정 임계값: `RISK_THRESHOLD_{4H,2H,1H}` = 0.622766 / 0.610441 / 0.783028(§5.2, §4.6 §3).
- 지속 경고 규칙: 2개 연속 시점 threshold 초과(약 6분) — Kafka 실시간 스트림에서 동일 로직 적용 필요(§4.3 §17, §4.4 §12).
- Temporal warm-up: trajectory 시작 후 60분(20 sample)은 추론 불가 — 실시간 스트림에서도 동일하게 초기 60분은 예측 보류 필요(`TEMPORAL_WARMUP_MINUTES=60`, §5.2).

**아직 결정되지 않은 것 (구현 담당자가 정해야 함)**:
- Kafka sensor 메시지의 정확한 필드 구조, trajectory/case 선택 방식(§4.0 A 담당 작업).
- Drift event schema와 재학습 trigger 조건(§4.0 B 담당 작업, 17번).
- 배포 대상 서버 — 원래 Oracle Cloud 무료 서버를 쓰다가 회수되어, 현재는 팀원 개인 컴퓨터를 대신 배포 대상으로 사용하는 방향으로 전환 중(README 최근 git 커밋 메모 기준. §4.9 문서 자체는 여전히 Oracle 기준으로 작성되어 있어 실제 배포 시 서버 주소/접속 방식 부분만 개인 컴퓨터에 맞게 갱신하면 됨).
- 모델 hot reload 정책(§4.8 §4, 20번 작업에서 결정 예정).

**이 프로젝트를 이해하는 데 가장 중요한 문서 3개**(순서대로 읽을 것을 권장): §4.2(TEP 데이터 구조 — RUL/EOL/데이터 누수 개념의 기초), §4.3(데이터셋 분할 설계 — 이후 모든 실험의 전제), §4.6(최종 모델과 예측 계약 — 실제 구현 시 참조할 스키마).

