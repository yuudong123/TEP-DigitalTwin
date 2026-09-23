# 실시간 AI 추론 서비스

> 작성 기준: 2026-09-15  
> 현재 상태: 구현 및 실제 Kafka 통합 검증 완료  
> 선행 작업: 11번 Kafka 원격 송수신 검증 완료

## 1. 목적

Kafka의 `tep-sensor-data` topic으로 들어오는 TEP 센서 메시지를 실시간으로
수신하고, trajectory별 최근 60분 데이터를 메모리에 유지한다.

최근 데이터로 학습 당시와 동일한 728개 Temporal Feature를 생성한 뒤
Production XGBoost 모델 4개를 실행하여 다음 결과를 만든다.

- 잔여수명(RUL)
- 4시간 이내 고장 위험 점수
- 2시간 이내 고장 위험 점수
- 1시간 이내 고장 위험 점수
- 공정 상태
- SHAP 기반 주요 위험 요인

추론 결과는 `tep-predictions` topic으로 발행하여 FastAPI, Web, Unity가
같은 결과를 사용할 수 있도록 한다.

---

## 2. 현재까지 준비된 것

| 구분                  | 상태 | 내용                                             |
| --------------------- | ---- | ------------------------------------------------ |
| Sensor Schema v1.0    | 완료 | `Id`·`Time` 제외 공정 변수 56개                  |
| Kafka Producer        | 완료 | case와 trajectory 선택 및 순차 발행              |
| 확인용 Consumer       | 완료 | Schema·key·개수·sequence 검증                    |
| 원격 Kafka 연결       | 완료 | Tailscale `100.127.7.26:9092`                    |
| 전체 송수신 검증      | 완료 | `case1::1` 2,929개, 오류 0개                     |
| Temporal Feature 설계 | 완료 | 5·15·30·60분, 총 728개                           |
| Production 모델 선정  | 완료 | Temporal XGBoost 모델 4개                        |
| 실시간 추론 서비스    | 완료 | Feature 일치·모델 예측·Kafka 전체 흐름 검증 완료 |

---

## 3. 작업 범위

12번 작업에서 구현할 기능은 다음과 같다.

1. Kafka sensor topic 구독
2. Sensor Schema v1.0 검증
3. trajectory별 sequence와 시간 순서 확인
4. 최근 60분 데이터 인메모리 버퍼링
5. 모델 원본 입력 변수 52개 선택
6. 5·15·30·60분 Temporal Feature 728개 생성
7. `feature_list.json` 순서 검증
8. Production XGBoost 모델 4개 로드 및 추론
9. threshold 기반 공정 상태 결정
10. TreeSHAP 주요 위험 요인 5개 생성
11. Prediction Schema 생성 및 검증
12. `tep-predictions` topic 발행
13. 처리 성공 후 Kafka offset commit
14. warm-up, 잘못된 메시지, 중복, 순서 오류 및 추론 실패 처리

다음 기능은 12번 범위에서 제외한다.

- FastAPI endpoint 구현
- Web·Unity 화면 구현
- Drift 감지
- 자동 재학습 및 모델 교체
- Kafka 센서 메시지 장기 보관

---

## 4. 전체 처리 흐름

```text
case1~case6 CSV
→ Kafka Producer
→ tep-sensor-data
→ Inference Consumer
→ Sensor Schema 검증
→ trajectory별 최근 60분 메모리 버퍼
→ Temporal Feature 728개 생성
→ Production XGBoost 모델 4개 추론
→ 상태 판정 및 SHAP 설명
→ Prediction Schema 생성
→ tep-predictions
→ FastAPI / Web / Unity
```

확인용 `kafka/consumer.py`는 Kafka 전송 검증 도구로 그대로 유지한다.
AI 추론은 별도의 Inference Service에서 수행한다. 두 Consumer의 역할을
한 파일에 섞지 않는다.

---

## 5. Kafka 설정

사용할 환경변수는 다음과 같다.

```text
KAFKA_BOOTSTRAP_SERVERS=100.127.7.26:9092
KAFKA_SENSOR_TOPIC=tep-sensor-data
KAFKA_PREDICTION_TOPIC=tep-predictions
KAFKA_CONSUMER_GROUP=inference-service
```

실행 위치에 따른 bootstrap server는 다음과 같다.

| 실행 위치                | Kafka 주소          |
| ------------------------ | ------------------- |
| 개발 PC에서 직접 실행    | `100.127.7.26:9092` |
| Docker Compose 내부 실행 | `kafka:19092`       |

확인용 Consumer와 AI 추론 Consumer는 group을 분리한다.

| Consumer            | Group 용도                         |
| ------------------- | ---------------------------------- |
| `kafka/consumer.py` | 송수신 검증용 `tep-replay-check-*` |
| Inference Service   | 실제 추론용 `inference-service`    |

group이 다르므로 동일한 Sensor 메시지를 각 Consumer가 독립적으로 받을 수 있다.

---

## 6. 입력 Sensor 메시지

Inference Service는 11번 Sensor Schema v1.0을 입력으로 사용한다.

```json
{
  "schema_version": "1.0",
  "event_type": "tep_sensor_reading",
  "trajectory_key": "case1::1",
  "case": "case1",
  "trajectory_id": 1,
  "sequence": 20,
  "timestamp_hours": 1.0,
  "replayed_at": "2026-09-15T10:00:00+09:00",
  "values": {
    "D feed": 0.0,
    "Reactor Pressure": 0.0
  }
}
```

실제 `values`에는 공정 변수 56개가 들어간다.

Inference Service는 최소한 다음을 검사한다.

- `schema_version`과 `event_type`
- Kafka key와 `trajectory_key` 일치
- `case`, `trajectory_id`, `sequence`
- `timestamp_hours`가 0 이상의 유한한 숫자인지
- `values`가 정확히 56개인지
- 모든 공정값이 유한한 숫자인지
- 같은 trajectory 안에서 sequence와 시간이 증가하는지

---

## 7. 시간 기준

TEP 데이터의 sampling interval은 다음과 같다.

```text
0.05 hour = 3 minutes
```

Producer의 `0.1초` 전송 간격은 테스트를 빠르게 재생하기 위한 실제 대기시간이다.
Temporal Feature의 시간 기준으로 사용하지 않는다.

```text
전송 간격 0.1초
→ 프로그램 실행 속도

timestamp_hours
→ 모델이 사용하는 시뮬레이션 시간
```

모든 5·15·30·60분 계산은 `timestamp_hours`를 기준으로 수행한다.

---

## 8. trajectory별 인메모리 버퍼

각 trajectory는 서로 독립된 공정 실행이므로 버퍼를 분리한다.

```text
case1::1 → 전용 최근 60분 버퍼
case1::2 → 전용 최근 60분 버퍼
case2::1 → 전용 최근 60분 버퍼
```

버퍼에는 Feature 728개 전체를 매번 저장하지 않고, Sensor 메시지의 시간과
모델에 필요한 원본 변수 52개를 보관한다.

```text
timestamp_hours
+ 원본 변수 52개
```

새 메시지가 들어오면 현재 시점보다 60분보다 오래된 관측값을 제거한다.
메모리 사용량이 trajectory 수에 따라 무한히 증가하지 않도록 종료된
trajectory의 버퍼를 제거하는 정책도 필요하다.

---

## 9. Warm-up

가장 긴 window는 60분이다.

```text
20 intervals × 3 minutes = 60 minutes
```

trajectory의 처음 20개 row는 완전한 60분 과거 데이터가 없으므로 모델
추론을 수행하지 않는다.

| sequence | 처리                              |
| -------: | --------------------------------- |
| `0`~`19` | 버퍼에 저장하고 warm-up 상태 출력 |
| `20`부터 | 60분 데이터가 준비되어 추론 시작  |

`sequence=20`에서 현재 행을 포함하여 21개 시점이 존재한다.

서비스가 재시작되면 메모리 버퍼는 사라진다. MVP에서는 Consumer를 Producer보다
먼저 실행하여 trajectory 처음부터 버퍼를 다시 구성한다. 운영 단계에서 중간
재시작 복구가 필요하면 Kafka 과거 메시지 재조회 또는 별도 상태 저장 방식을
추가한다.

---

## 10. 모델 입력 원본 변수 52개 선택

Kafka Sensor 메시지에는 56개 공정 변수가 있지만 최종 모델의 현재값 입력은
52개이다.

```text
XMEAS 41개
+ 유효 XMV 11개
= 52개
```

제외할 변수와 입력 순서를 코드에서 임의로 정하지 않는다. 다음 Production
artifact를 기준으로 선택한다.

```text
models/production/v1.0.0/feature_list.json
models/production/v1.0.0/feature_schema.csv
```

Kafka의 56개 값 중 필요한 원본 변수 52개가 모두 존재하는지 시작 시 검증한다.
누락되거나 이름이 다른 경우 추론하지 않고 오류로 처리한다.

---

## 11. Temporal Feature 728개 생성

학습 당시와 동일하게 다음 Feature를 생성한다.

| 구간     | 계산 종류                        | Feature 수 |
| -------- | -------------------------------- | ---------: |
| 현재     | 현재값                           |         52 |
| 5분      | 변화량, 변화속도                 |        104 |
| 15분     | 평균, 표준편차, 변화량, 변화속도 |        208 |
| 30분     | 평균, 표준편차, 최대값, 최소값   |        208 |
| 60분     | 변화량, 변화속도, 선형 기울기    |        156 |
| **합계** |                                  |    **728** |

### 11.1 현재값

현재 메시지에서 선택한 원본 변수 52개를 사용한다.

### 11.2 5분 Feature

정확한 5분 전 sample이 없으므로 3분 전과 6분 전 값으로 선형보간한다.

```text
3분 전 값 + 6분 전 값
→ 5분 전 추정값
→ 현재값 - 5분 전 추정값
→ 5분 변화속도
```

보간에는 현재 또는 과거 데이터만 사용하며 미래 데이터는 사용하지 않는다.

### 11.3 15분 Feature

각 원본 변수에 대해 다음을 계산한다.

```text
최근 15분 평균
최근 15분 표준편차
현재값 - 15분 전 값
15분 변화속도
```

### 11.4 30분 Feature

각 원본 변수에 대해 다음을 계산한다.

```text
최근 30분 평균
최근 30분 표준편차
최근 30분 최대값
최근 30분 최소값
```

### 11.5 60분 Feature

각 원본 변수에 대해 다음을 계산한다.

```text
현재값 - 60분 전 값
60분 변화속도
최근 60분 전체 관측값의 선형 기울기
```

---

## 12. 학습·실시간 Feature 동일성

실시간 추론의 가장 중요한 조건은 학습 때 생성한 Feature와 이름, 계산식,
자료형, 순서가 완전히 동일한 것이다.

새 계산식을 별도로 다시 작성하기보다 5번 학습 데이터 생성에 사용한 공통
Feature 함수를 재사용한다.

생성 후 다음을 검사한다.

- Feature 개수가 728개인지
- 이름의 누락·중복·추가가 없는지
- 모든 값이 유한한 숫자인지
- `feature_list.json` 순서와 정확히 일치하는지
- 동일한 과거 데이터에 대해 offline 결과와 online 결과가 같은지

허용 오차를 정한 뒤 `numpy.allclose()` 방식으로 offline·online Feature를
비교하는 parity test를 작성한다.

---

## 13. Production 모델과 artifact

실시간 추론에 필요한 Production 파일은 다음과 같다.

```text
models/production/v1.0.0/
├─ rul_hours.json
├─ failure_within_4h.json
├─ failure_within_2h.json
├─ failure_within_1h.json
├─ feature_list.json
├─ feature_schema.csv
└─ metadata.json
```

서비스 시작 시 다음을 한 번만 수행한다.

1. 모델 4개 로드
2. Feature 목록과 순서 로드
3. 모델 버전 로드
4. threshold 로드
5. 각 모델의 입력 Feature 수가 728개인지 검증

메시지마다 모델 파일을 다시 읽지 않는다.

필요한 파일이 하나라도 없으면 Consumer만 실행한 상태로 진행하지 않고 서비스
시작을 실패 처리한다.

---

## 14. Threshold와 risk score

Validation 데이터로 결정한 threshold는 다음과 같다.

| Target               |  Threshold |
| -------------------- | ---------: |
| 4시간 이내 고장 위험 | `0.622766` |
| 2시간 이내 고장 위험 | `0.610441` |
| 1시간 이내 고장 위험 | `0.783028` |

실제 서비스는 코드에 숫자를 중복 작성하지 않고 Production `metadata.json`에
저장된 threshold를 읽는 방식으로 통일한다. `reports/05-temporal/thresholds.json`은
학습 결과 확인용 artifact로 사용한다.

분류 모델의 출력은 보정된 실제 확률이 아니라 `risk score`로 표현한다.

---

## 15. 공정 상태 판정

상태는 위험도가 높은 조건부터 다음 순서로 검사한다.

```text
1시간 risk score ≥ 1시간 threshold → CRITICAL
2시간 risk score ≥ 2시간 threshold → WARNING
4시간 risk score ≥ 4시간 threshold → CAUTION
모든 score가 threshold 미만          → NORMAL
```

동시에 여러 조건이 참이어도 가장 높은 상태 하나를 선택한다.

---

## 16. SHAP 설명

상태에 따라 설명할 위험 모델을 선택한다.

```text
CRITICAL → 1시간 모델
WARNING  → 2시간 모델
CAUTION  → 4시간 모델
NORMAL   → 4시간 모델
```

선택한 모델의 TreeSHAP 값 중 위험도를 증가시키는 양수 Feature 상위 5개를
주요 위험 요인으로 출력한다.

각 위험 요인은 다음 필드를 포함한다.

```text
rank
feature
source_feature
transform
window_minutes
shap_value
```

SHAP 값은 모델 raw margin에 대한 기여도이며 실제 고장 확률의 직접 증가량으로
표현하지 않는다.

---

## 17. Prediction 메시지 Schema v1.0

12번 작업의 출력 메시지는 다음 구조를 사용한다.

```json
{
  "schema_version": "1.0",
  "event_type": "tep_prediction",
  "model_version": "v1.0.0",
  "trajectory_key": "case1::1",
  "sequence": 20,
  "timestamp_hours": 1.0,
  "predicted_at": "2026-09-15T10:00:02+09:00",
  "rul": {
    "hours": 120.5
  },
  "risk": {
    "failure_within_4h": {
      "score": 0.12,
      "threshold": 0.622766,
      "alert": false
    },
    "failure_within_2h": {
      "score": 0.08,
      "threshold": 0.610441,
      "alert": false
    },
    "failure_within_1h": {
      "score": 0.03,
      "threshold": 0.783028,
      "alert": false
    }
  },
  "status": "NORMAL",
  "explanation_model": "failure_within_4h",
  "top_risk_factors": []
}
```

Kafka message key는 Sensor 메시지와 같은 `trajectory_key`를 사용한다.

---

## 18. Kafka 처리 신뢰성

Inference Consumer는 메시지 처리와 Prediction 발행이 모두 성공한 뒤 offset을
commit한다.

```text
Sensor 수신
→ Schema 검증
→ 버퍼 갱신
→ Feature 생성
→ 모델 추론
→ Prediction 발행 성공
→ Sensor offset commit
```

중간에 오류가 발생하면 성공으로 commit하지 않아 재처리할 수 있도록 한다.
재처리 과정에서 같은 Prediction이 두 번 발행될 수 있으므로 다음 조합을 결과의
고유 식별 기준으로 사용한다.

```text
model_version + trajectory_key + sequence
```

FastAPI 또는 저장 계층은 이 기준으로 중복 결과를 덮어쓰거나 무시할 수 있어야
한다.

---

## 19. 오류 처리

| 상황                     | 처리 원칙                              |
| ------------------------ | -------------------------------------- |
| 잘못된 JSON              | 오류 로그 후 메시지 격리 또는 건너뛰기 |
| Schema 불일치            | 추론하지 않고 오류 기록                |
| 변수 56개 미만·초과      | 추론하지 않음                          |
| 모델 원본 변수 52개 누락 | 추론하지 않음                          |
| NaN·무한대               | 추론하지 않음                          |
| sequence 중복            | 이미 처리한 결과인지 확인 후 중복 방지 |
| sequence 누락·역순       | 버퍼 신뢰 불가 상태로 표시하고 재구성  |
| warm-up 미완료           | 버퍼만 갱신하고 예측하지 않음          |
| Feature 728개 불일치     | 모델을 호출하지 않음                   |
| 모델·metadata 로드 실패  | 서비스 시작 실패                       |
| Prediction 발행 실패     | offset commit하지 않고 재시도          |

MVP에서는 오류 내용을 로그로 남긴다. 운영 확장 시에는 별도의 dead-letter
topic을 추가할 수 있다.

---

## 20. 최종 구현 파일 구조

실시간 추론 코드는 프로젝트 루트의 `inference/`가 아닌
`src/inference/`에 배치한다. 실제 구현 구조는 다음과 같다.

```text
src/inference/
├─ __init__.py             # Python package 인식
├─ main.py                 # Kafka 수신·추론·Prediction 발행
├─ temporal_features.py    # trajectory별 60분 버퍼·728개 Feature 생성
├─ model_loader.py         # Production 모델 4개·threshold·SHAP 로드
├─ prediction_schema.py    # Prediction 메시지 검증
├─ validate_temporal.py    # offline·online Feature 일치 검증
└─ README.md               # 실행 방법·환경변수·파일 역할
```

`main.py`와 `validate_temporal.py`는 `src/inference/`에서 프로젝트
루트까지 두 단계 올라가야 하므로 다음 경로를 사용한다.

```python
PROJECT_ROOT = Path(__file__).resolve().parents[2]
```

`kafka/producer.py`, `kafka/consumer.py`, `tests/test_inference_runtime.py`는
프로젝트 루트 아래 한 단계에 있으므로 `parents[1]`을 유지한다.

### 20.1 원격 Kafka 기준 실행 방법

Docker PC에서 Kafka를 실행하고, 개발 PC에서 Inference와 Producer를
Python으로 실행한다.

데이터 처리 흐름은 다음과 같다.

```text
개발 PC의 Producer
→ 원격 Docker PC의 Kafka
→ 개발 PC의 Inference
→ 원격 Kafka의 tep-predictions topic
```

개발 PC의 `.env`는 다음과 같이 설정한다.

```env
KAFKA_BOOTSTRAP_SERVERS=100.127.7.26:9092
KAFKA_SENSOR_TOPIC=tep-sensor-data
KAFKA_PREDICTION_TOPIC=tep-predictions
KAFKA_CONSUMER_GROUP=inference-service
MODEL_DIR=models/production/v1.0.0
```

원격 Kafka 연결 여부는 다음 명령으로 확인한다.

```powershell
Test-NetConnection 100.127.7.26 -Port 9092
```

정상 연결 시 다음 결과가 출력된다.

```text
TcpTestSucceeded : True
```

첫 번째 PowerShell에서 Inference를 먼저 실행한다.

```powershell
cd C:\TEP-DigitalTwin
.\.venv\Scripts\Activate.ps1
python -m src.inference.main
```

정상적으로 실행되면 다음 내용이 출력된다.

```text
Kafka 서버: 100.127.7.26:9092
입력 토픽: tep-sensor-data
출력 토픽: tep-predictions
[수신 대기] Producer를 실행하세요. 첫 20개 메시지는 60분 준비 구간입니다.
```

Inference PowerShell을 종료하지 않고 유지한 상태에서 두 번째 PowerShell을
열어 Producer를 실행한다.

```powershell
cd C:\TEP-DigitalTwin
.\.venv\Scripts\Activate.ps1
python .\kafka\producer.py --case case1 --id 1 --send
```

빠른 동작 확인이 필요한 경우 25개 메시지만 전송한다.

```powershell
python .\kafka\producer.py --case case1 --id 1 --limit 25 --send
```

처음 20개 메시지는 60분 Temporal Feature 생성을 위한 warm-up으로 사용한다.
따라서 `sequence=20`부터 실제 Prediction이 생성된다.

전체 `case1::1` 데이터를 전송하면 다음 결과가 출력된다.

```text
========== Producer 전송 결과 ==========
전송 요청: 2929
전송 성공: 2929
전송 실패: 0
최종 결과: 정상
```

Inference는 마지막 메시지까지 정상적으로 처리한다.

```text
[추론 완료] case1::1 sequence=2928, time=146.4,
status=CRITICAL, rul=0.348h
```

`case1::1`의 전체 Sensor 메시지는 2,929개이며 처음 20개를 warm-up으로
사용하므로 총 2,909개의 Prediction이 생성된다.

```text
2,929 - 20 = 2,909
```

Inference를 종료할 때는 Inference를 실행한 PowerShell에서 `Ctrl+C`를 누른다.

---

## 21. 구현 순서

### 1단계: Production artifact 확인

```powershell
Get-ChildItem .\models\production\v1.0.0
```

모델 4개, Feature 파일 2개, metadata가 모두 있는지 확인한다.

### 2단계: 기존 Temporal Feature 코드 확인

학습 때 사용한 728개 Feature 생성 함수와 Feature 이름 규칙을 찾는다.

### 3단계: Offline·online parity test

저장된 trajectory의 동일 시점에 대해 기존 offline Feature와 실시간 버퍼로
계산한 Feature가 동일한지 검증한다.

### 4단계: 모델 추론 모듈

728개 Feature로 RUL과 위험 모델 3개를 동시에 실행하고 threshold 상태를 만든다.

### 5단계: Prediction Schema와 SHAP

Prediction 메시지 생성·검증과 주요 위험 요인 5개 출력을 구현한다.

### 6단계: Kafka Inference Service 연결

Sensor 수신, 버퍼, Feature, 모델, Prediction 발행을 하나의 실행 흐름으로 연결한다.

### 7단계: 전체 통합 검증

Producer를 실행하고 warm-up 이후 모든 예측 결과를 검사한다.

---

## 22. 완료 검증 기준

### 22.1 시작 검증

- 모델 4개를 정상적으로 로드한다.
- 모델 버전과 threshold를 metadata에서 읽는다.
- `feature_list.json`에 Feature가 정확히 728개 있다.
- 각 모델의 입력 Feature 수가 728개이다.

### 22.2 Feature 검증

- `sequence=0`~`19`에서는 예측하지 않는다.
- `sequence=20`부터 예측한다.
- 5분 보간에 미래 데이터를 사용하지 않는다.
- 생성 Feature 이름과 순서가 `feature_list.json`과 일치한다.
- offline·online Feature가 허용 오차 안에서 동일하다.

### 22.3 추론 검증

- 한 입력에서 RUL과 위험 점수 3개를 모두 생성한다.
- threshold 우선순위에 따라 상태를 결정한다.
- SHAP 양수 기여도 상위 5개를 출력한다.
- 모든 결과 값이 JSON 직렬화 가능한 유한한 숫자이다.

### 22.4 Kafka 통합 검증

- `tep-sensor-data`를 정상적으로 수신한다.
- warm-up 이후 메시지마다 Prediction을 발행한다.
- Prediction key와 `trajectory_key`가 일치한다.
- Prediction 발행 성공 후 Sensor offset을 commit한다.
- 같은 입력을 재처리해도 결과 식별 기준이 동일하다.

### 22.5 `case1::1` 예상 결과 개수

`case1::1`은 총 2,929개 Sensor 메시지이고 처음 20개는 warm-up이다.

```text
2,929 - 20 = 2,909
```

모든 메시지가 정상이라면 Prediction 메시지는 2,909개가 생성되어야 한다.

### 22.6 실제 통합 검증 결과

2026-09-22에 Tailscale로 연결된 원격 Kafka에서 `case1::1` 전체 흐름을
검증했다.

| 확인 항목                 | 결과                                          |
| ------------------------- | --------------------------------------------- |
| Sensor 전송 요청          | 2,929개                                       |
| Sensor 전송 성공          | 2,929개                                       |
| Sensor 전송 실패          | 0개                                           |
| warm-up                   | `sequence=0`~`19`, 20개                       |
| Prediction 생성 구간      | `sequence=20`~`2928`                          |
| Prediction 예상·처리 개수 | 2,909개                                       |
| 마지막 처리               | `sequence=2928`, `time=146.4`                 |
| 상태 변화                 | `NORMAL` → `CAUTION` → `WARNING` → `CRITICAL` |
| 마지막 결과               | `CRITICAL`, RUL 약 `0.348h`                   |

Producer, Inference Service와 Prediction 발행 과정에서 전송 실패 또는 입력
오류가 발생하지 않았다. 첫 20개 Sensor 메시지는 최근 60분 Feature를 만들기
위한 준비 데이터이므로 Prediction 개수에서 제외한다.

---

## 23. 실행 원칙

- Kafka는 Sensor 데이터의 실시간 전달 통로로 사용한다.
- 원본 장기 보관은 `data/raw/case1.csv`~`case6.csv`가 담당한다.
- Inference Service의 60분 버퍼는 메모리에만 유지한다.
- Kafka 메시지와 버퍼의 영구 저장은 12번 필수 범위가 아니다.
- 예측 결과의 장기 저장 여부는 FastAPI·DB 설계 단계에서 결정한다.
- 코드 구현 전에 Production artifact와 기존 Feature 생성 코드를 먼저 확인한다.
- 학습과 실시간 추론에서 같은 Feature 함수를 사용한다.

---

## 24. 현재 상태와 다음 작업

실시간 추론 서비스의 구현, 자동 검증 및 실제 Kafka 통합 검증을 완료했다.

- 학습·실시간 Temporal Feature 728개 완전 일치
- 최초 20개 메시지 warm-up 및 21번째 메시지부터 추론 확인
- Production 모델 4개 로딩 및 Prediction 생성 확인
- Sensor Schema, Kafka key 및 Prediction Schema 검증 구현
- 잘못된 입력 메시지 격리 처리 구현
- Sensor 2,929개 전송 및 Prediction 2,909개 처리 확인
- 마지막 `sequence=2928`까지 추론 및 Prediction 발행 확인
- `NORMAL`부터 `CRITICAL`까지 상태 변화 확인

자동 검증은 다음 명령으로 실행한다.

```powershell
python -m inference.validate_temporal --case case1 --id 1 --row 20
python -m unittest tests.test_inference_runtime -v
```

12번 실시간 추론 작업의 필수 구현과 검증은 완료했다. 다음 작업은 13번
FastAPI에서 `tep-predictions` 결과를 조회·전달하는 API를 구현하는 것이다.
