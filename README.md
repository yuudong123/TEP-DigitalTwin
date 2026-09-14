# TEP Digital Twin

TEP Run-to-Failure 화학공정 데이터를 실시간으로 스트리밍하고,
AI를 이용해 공정의 고장 위험과 잔여수명(RUL)을 예측하며,
데이터 드리프트에 따른 자동 재학습과 디지털트윈 모니터링까지 구현하는
예지보전 시스템이다.

---

## 1. 주요 기능

- TEP Run-to-Failure 데이터 처리
- XGBoost 기반 RUL 예측
- 4시간 / 2시간 / 1시간 고장 위험 예측
- 시계열 Feature 기반 예측
- TreeSHAP 기반 위험 요인 설명
- Kafka 기반 실시간 데이터 스트리밍
- FastAPI 기반 예측 API
- Web 모니터링
- Unity 디지털트윈
- Drift Detection
- 자동 재학습
- Candidate 모델 평가 및 Production 승격
- Docker 기반 서비스 구성
- Jenkins 기반 CI/CD

---

## 2. 시스템 구조

```text
TEP CSV
   ↓
Kafka Producer
   ↓
Kafka
   ↓
Inference Service
   ↓
XGBoost Model
   ↓
FastAPI
   ↓
Web / Unity
```

MLOps 흐름:

```text
Real-time Data
   ↓
Drift Monitor
   ↓
Drift Confirmed
   ↓
Retraining
   ↓
Candidate Model
   ↓
Candidate Evaluation
   ↓
Production Promotion
   ↓
Inference Model Update
```

CI/CD:

```text
Git Push
   ↓
GitHub
   ↓
Jenkins
   ↓
Docker Build
   ↓
Development Server Deploy
```

---

## 3. AI 모델

현재 Production 모델:

```text
Version: v1.0.0
Model: XGBoost
Feature Set: Temporal
Feature Count: 728
```

예측 Task:

- RUL (`rul_hours`)
- 4시간 이내 고장 위험
- 2시간 이내 고장 위험
- 1시간 이내 고장 위험

최종 모델은 다음 위치에서 관리한다.

```text
models/production/v1.0.0/
```

---

## 4. 프로젝트 구조

```text
TEP_DigitalTwin/
├─ config/
├─ data/
│  ├─ metadata/
│  ├─ processed/
│  └─ raw/
├─ docker/
├─ docs/
├─ logs/
├─ models/
│  ├─ candidates/
│  └─ production/
├─ notebooks/
├─ reports/
├─ src/
│  ├─ api/
│  ├─ common/
│  ├─ data/
│  ├─ evaluation/
│  ├─ inference/
│  ├─ mlops/
│  ├─ monitoring/
│  ├─ streaming/
│  └─ training/
├─ tests/
├─ unity/
└─ web/
```

---

## 5. 개발환경

권장 Python:

```text
Python 3.11
```

프로젝트 clone:

```powershell
git clone <repository-url>
cd TEP_DigitalTwin
```

가상환경 생성:

```powershell
python -m venv .venv
```

PowerShell 활성화:

```powershell
.\.venv\Scripts\Activate.ps1
```

Python 패키지 설치:

```powershell
python -m pip install -r requirements.txt
```

환경변수 파일 생성:

```powershell
Copy-Item .env.example .env
```

---

## 6. 환경설정

실제 실행 설정은 루트의 `.env`에서 관리한다.

공유 가능한 기본 구조는:

```text
.env.example
```

에 저장한다.

`.env`는 Git에 포함하지 않는다.

공통 Python 설정은:

```text
src/common/config.py
```

에서 로드한다.

---

## 7. 데이터

다음 데이터는 Git에 포함하지 않는다.

```text
data/raw/
data/processed/
```

원본 또는 학습용 데이터가 필요한 작업자는 별도로 데이터를 준비하거나
프로젝트의 데이터 생성 스크립트를 이용해 재생성해야 한다.

데이터 구조 및 Feature 정의에 필요한 Metadata는 다음 위치에서 관리한다.

```text
data/metadata/
```

---

## 8. 로그

실행 로그는:

```text
logs/
```

에 저장한다.

공통 Logger:

```text
src/common/logger.py
```

서비스별 로그 파일은 Runtime에서 생성하며 Git에는 포함하지 않는다.

---

## 9. Git Branch 전략

```text
main
```

안정 버전.

```text
dev
```

팀 통합 브랜치이자 기본 개발 기준 브랜치.

실제 기능 개발은 최신 `dev`에서 Feature Branch를 생성한다.

예:

```text
feat/docker
feat/kafka-replay
feat/inference
feat/web
feat/retraining
```

작업 완료 후 Pull Request를 통해 `dev`에 병합한다.

---

## 10. 문서

상세 프로젝트 문서는:

```text
docs/
```

에 저장한다.

현재 주요 문서:

```text
00-team-roles.md
01-project-plan.md
02-tep-data-overview.md
03-dataset-design.md
04-baseline-model.md
05-temporal-features.md
06-final-model.md
07-project-structure.md
08-docker-development.md
09-manual-deployment.md
10-jenkins-cicd.md
```

---

## 11. 현재 개발 상태

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

준비 완료:

```text
08. Docker 개발환경 구성
09. 수동 배포 절차 문서·스크립트
10. Jenkins 파이프라인 파일·설정 문서
```

08~10번의 실제 운영 완료 기준은 아직 통과하지 않았다. API·inference·monitor
구현과 배포 대상 컴퓨터에서의 검증이 필요하다.
 
