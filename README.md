# TEP Digital Twin

> 화학공정 센서 데이터를 실시간으로 재생하면서, 고장 위험과 남은 수명을 예측하는 프로젝트입니다.

## 📌 프로젝트 개요

| 항목 | 내용 |
|---|---|
| 개발 형태 | 3인 팀으로 시작한 프로젝트 |
| 데이터 | TEP Run-to-Failure, 공식 6개 시나리오·600개 trajectory |
| 예측 대상 | 잔여수명(RUL), 4·2·1시간 이내 고장 위험 |
| 모델·설명 | XGBoost · 시계열 특징 728개 · TreeSHAP |
| 서비스·운영 | Kafka · FastAPI · Web · Docker · Jenkins |
| 개인 담당 | 조현재 — 백엔드, 이후 웹·모델 관리 등 남은 개발과 통합 담당 |

## 담당한 작업

- 처음에는 백엔드를 맡아 Kafka 데이터 재생, 실시간 추론, FastAPI를 구현했습니다. 각 서비스에서 주고받는 데이터 형식도 정리했습니다.
- 개발 도중 팀원 한 명이 빠지면서 남은 작업을 이어받았습니다. 웹 화면과 모델 관리 기능을 포함해 전체 서비스를 연결하는 작업을 진행하고 있습니다.
- 센서 재생부터 예측 결과가 웹에 표시되기까지 연결하고, 후보 모델 평가·교체·이전 모델 복구 기능을 연동했습니다.
- Unity 연결과 빌드, 장시간 부하 테스트, PC 재부팅 후 복구 확인은 남아 있습니다.

처음 나눈 역할은 [팀 역할 문서](docs/00-team-roles.md), 이후 작업과 남은 내용은 [진행표](docs/00-progress-status.md)에 정리했습니다. 아래 모델 성능은 팀 프로젝트에서 사용한 모델의 평가 결과입니다.

## 개발하면서 해결한 문제

| 문제 | 처리 방법 | 관련 문서·코드 |
|---|---|---|
| 같은 공정 실행의 인접 행이 학습·평가에 섞일 위험 | `case::Id`로 trajectory를 식별하고 실행 단위 분할, validation에서 threshold 선택 | [데이터셋 설계](docs/03-dataset-design.md), [최종 모델](docs/06-final-model.md) |
| 정적인 센서값만으로 열화 추세 표현이 부족 | 52개 기본 변수에서 변화량·통계·기울기를 포함한 728개 Temporal Feature 구성 | [실시간 특징 코드](src/inference/temporal_features.py) |
| 빠른 재생이 공정 시간축을 바꾸는 문제 | 전송 속도 대신 메시지의 3분 간격 시간축으로 최근 21개 시점·60분 특징 생성 | [실시간 특징 코드](src/inference/temporal_features.py), [추론 시험](tests/test_inference_runtime.py) |
| 부적합 모델 교체 또는 적용 실패 위험 | validation 성능 비교와 파일 해시 확인 후 승인된 모델만 적용, 실패하면 이전 모델로 복구 | [생명주기 시험](tests/test_model_lifecycle.py), [실증 기록](reports/19-20-lifecycle/verification-2026-09-30.md) |
| 열화 변화와 재학습 가능한 운영 Drift 혼동 | 변화는 기록하되, 운영 데이터와 정답이 확보되기 전에는 자동 재학습을 실행하지 않음 | [진행표와 남은 조건](docs/00-progress-status.md) |

## 모델 성능과 테스트 결과

[최종 모델 평가 결과](docs/06-final-model.md)는 다음과 같습니다.

| Test 지표 | Baseline 52 features | Temporal 728 features |
|---|---:|---:|
| RUL MAE | 3.0446 h | **2.1877 h** |
| RUL R² | 0.9857 | **0.9930** |
| 4시간 위험 AP / F1 | 0.9907 / 0.9538 | **0.9948 / 0.9619** |
| 2시간 위험 AP / F1 | 0.9775 / 0.9161 | **0.9833 / 0.9276** |
| 1시간 위험 AP / F1 | 0.9418 / 0.8714 | **0.9648 / 0.8993** |

RUL MAE는 약 **28.1% 감소**했습니다. 분류 출력은 보정된 실제 고장 확률이 아닌 `risk score`이며, SHAP은 모델 판단 기여도입니다.

- **서비스 연결 테스트:** CSV 센서 2,929건 → 예측 2,909건, 동기 예측 일치·재생 제어·API 재시작 보존 기록. 추론에는 21개 시점이 필요해 처음 20건은 데이터를 모으는 데 사용합니다. [통합 실증](reports/16-integration/verification-2026-09-30.md)
- **모델 교체 테스트:** validation 238,872행·90 trajectory에서 동등 모델 control 통과와 악화 후보 거부, hot application·rollback을 확인했습니다. 기존 모델을 복사한 비교용 모델과 성능이 나쁜 후보를 사용한 테스트입니다. [실증 기록](reports/19-20-lifecycle/verification-2026-09-30.md)
- **남은 작업:** Unity를 제외한 서비스 연결과 Jenkins 배포를 확인했습니다. Unity 연결, 장시간 부하와 재부팅 복구 테스트, 재학습에 필요한 운영 데이터·정답 확보는 남아 있습니다. [최신 진행표](docs/00-progress-status.md)

---


TEP Run-to-Failure 화학공정 데이터를 실시간으로 스트리밍하고,
AI를 이용해 공정의 고장 위험과 잔여수명(RUL)을 예측하며,
공정 열화·운전상태 변화 모니터링과 디지털트윈 모니터링까지 구현하는
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
- 운전상태·열화 변화 모니터링
- 자동 재학습은 운영 Drift 데이터 확보 후 재검토
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
운전상태·열화 변화 Monitor
   ↓
변화 Event 기록
   ↓
Inference/RUL 결과와 함께 점검
   ↓
운영 Drift 데이터 확보 후 모델 생명주기 연계 검토
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
│  ├─ lifecycle/
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
08. Docker 개발환경 구성 (완료)
09. 집 Windows PC 수동 배포 도구 및 기반 환경 검증
10. Windows Jenkins dev Poll SCM 및 실제 빌드·기반 환경 배포 검증
```

개발서버는 Oracle 대신 집 Windows PC의 `D:\TEP_DigitalTwin`을 사용한다.
Jenkins는 별도 작업 폴더에서 GitHub `dev`를 받아 2분마다 변경을 확인한다.
Kafka·Inference·Monitor·API/Web 전체 운영 기동과 Jenkins #25/#26 SUCCESS를 확인했다.
PR #27–30은 dev 병합 완료. 실제 CSV 센서2,929건 → 예측2,909건,
동기 예측 일치·재생 제어·API snapshot 재시작 보존까지 실증했다.
실제 validation 전체238,872행에서 후보 평가와 승격·hot application·rollback 경로를 검증했다.
동등 모델 복사 control 및 악화 후보로 검증한 것이며 새 개선 모델을 운영 적용한 것은 아니다.
Kafka 데이터는 외부 볼륨 `tep-kafka-data`에 보존한다. 기존 브로커의 최초 이전은
`docs/08-kafka-persistence.md`를 따른다.
Unity는 사용자 집 PC 마무리 대상이다. PC 재부팅 복구·장시간 부하 검증,
17번 보정 기준 선택은 남아 있고 자동 재학습은 비활성 유지한다.
상세 진행표는 [docs/00-progress-status.md](docs/00-progress-status.md),
집 PC 재개/Unity 인계는 [docs/25-home-pc-handoff.md](docs/25-home-pc-handoff.md)를 따른다.
 
