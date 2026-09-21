# Drift Detection 설계

## 1. 목적

실시간 TEP 센서 분포가 Production 모델 `v1.0.0`의 학습 기준 분포에서
지속적으로 벗어나는지 감지하고, 재학습 후보를 생성할 근거를 남긴다.
Drift는 고장 예측 결과가 아니며, Drift 감지만으로 Production 모델을 자동 교체하지 않는다.

## 2. 입력과 출력

입력은 `tep-sensor-data` topic의 Sensor Schema v1.0 메시지다.

- `trajectory_key`, `case`, `sequence`, `timestamp_hours`
- `values`: `Id`, `Time`을 제외한 공정 변수 56개

감시 대상은 Production 모델의 원천 입력 52개다.

- XMEAS 측정 변수 41개
- 상수가 아닌 XMV 조작 변수 11개

`Agitator`는 상수이므로 제외하고, `Liquid Input Reactor`,
`Liquid Input Separator`, `Liquid Input Stripper`는 모델 입력에서 제외된
추가 상태 변수이므로 1차 Drift 판정에서도 제외한다.

출력은 `tep-drift-events` topic의 Drift Event Schema v1.0 메시지다.

## 3. 기준 데이터

- `data/metadata/split_manifest.csv`의 train trajectory만 사용한다.
- 각 trajectory의 안정 운전 구간인 30시간 이상 60시간 미만을 기준 구간으로 사용한다.
- 운전 모드 차이를 열화로 오판하지 않도록 case별 기준 분포를 별도로 만든다.
- 각 Feature의 기준 통계, PSI 구간, 결측률은 버전이 지정된 JSON으로 저장한다.
- 기준 데이터 버전에는 dataset split, feature schema, 생성 시각을 함께 기록한다.

실제 구현 전에 30~60시간 구간에 열화가 섞이지 않았는지 case별 분포와 원본 데이터 설명을
다시 검증한다. 검증 결과에 따라 기준 구간은 변경할 수 있지만, train 이외 데이터는 사용하지 않는다.

## 4. 판정 창과 검사 주기

- trajectory별로 독립된 Sliding Window를 유지한다.
- 최근 6시간, 즉 기본 3분 간격 기준 120개 관측값을 판정 창으로 사용한다.
- 20개 미만 관측값에서는 `INSUFFICIENT_DATA`로 기록하고 판정하지 않는다.
- 서비스의 실제 검사 주기는 기본 60초다.
- sequence 누락, 역전, trajectory 변경 시 창 상태를 로그에 남기고 안전하게 초기화한다.

## 5. 통계량과 Feature 판정

각 Feature에 PSI와 two-sample KS test를 함께 계산한다.

### PSI

- 기준 데이터의 10분위 구간을 고정해서 사용한다.
- 빈 구간의 0 나눗셈을 막기 위해 작은 epsilon을 적용한다.
- `PSI < 0.10`: 안정
- `0.10 <= PSI < 0.25`: 주의
- `PSI >= 0.25`: 강한 변화

### KS test

- 기준 표본과 현재 창을 비교한다.
- 52개 동시 검정에는 Benjamini-Hochberg 방식으로 다중 검정을 보정한다.
- `q_value < 0.01`이면서 `KS statistic >= 0.15`일 때만 유의 변화로 본다.

Feature Drift는 다음 중 하나를 만족할 때 발생한다.

1. `PSI >= 0.25`
2. `PSI >= 0.10`이고 KS 조건도 만족

## 6. 전체 상태와 재학습 Trigger

단일 Feature의 일시적 변화로 재학습하지 않는다.

- `NORMAL`: Drift Feature 비율 10% 미만
- `CAUTION`: Drift Feature 비율 10% 이상 20% 미만
- `DRIFT`: Drift Feature 비율 20% 이상
- `CONFIRMED_DRIFT`: `DRIFT` 상태가 3회 연속 발생

재학습 요청은 다음 조건을 모두 만족할 때만 생성한다.

1. `CONFIRMED_DRIFT`
2. 같은 case에서 직전 재학습 요청 이후 cooldown 24시간 경과
3. 기준 창과 현재 창의 데이터 품질 검사 통과
4. `RETRAIN_ENABLED=true`

재학습 요청은 Candidate 모델 생성만 시작한다. 19번 평가·승격 기준을 통과하기 전에는
Production 모델을 교체하지 않는다.

## 7. 고장 위험과 Drift 구분

Inference의 risk/status와 Drift 상태는 별도 축으로 보존한다.

| 예측 위험 | Drift | 해석 |
| --- | --- | --- |
| 낮음 | 없음 | 정상 운전 |
| 높음 | 없음 | 학습 범위 안에서 감지된 고장 위험 |
| 낮음 | 있음 | 운전조건·센서 분포 변화 또는 미학습 상태 |
| 높음 | 있음 | 고장 위험과 분포 변화가 동시에 존재, 우선 점검 |

위험도가 높다는 이유로 Drift를 확정하지 않고, Drift가 있다는 이유로 고장을 확정하지 않는다.

## 8. Drift Event Schema v1.0

```json
{
  "schema_version": "1.0",
  "event_type": "tep_drift_event",
  "event_id": "uuid",
  "detected_at": "2026-09-14T12:00:00+09:00",
  "trajectory_key": "case1::17",
  "case": "case1",
  "sequence": 120,
  "timestamp_hours": 36.0,
  "reference_version": "v1.0.0",
  "model_version": "v1.0.0",
  "window": {
    "samples": 120,
    "start_timestamp_hours": 30.05,
    "end_timestamp_hours": 36.0
  },
  "status": "NORMAL | CAUTION | DRIFT | CONFIRMED_DRIFT | INSUFFICIENT_DATA",
  "drifted_feature_count": 0,
  "monitored_feature_count": 52,
  "drifted_feature_ratio": 0.0,
  "features": [
    {
      "feature": "Reactor Pressure",
      "psi": 0.0,
      "ks_statistic": 0.0,
      "q_value": 1.0,
      "drifted": false
    }
  ],
  "prediction_context": {
    "status": "NORMAL",
    "risk_score_4h": 0.0,
    "risk_score_2h": 0.0,
    "risk_score_1h": 0.0
  },
  "retraining_requested": false,
  "reason": ""
}
```

Inference 결과가 아직 없으면 `prediction_context`는 `null`로 전송한다.

## 9. 구현 단위

1. 기준 분포 생성기와 버전 파일
2. Sliding Window 및 데이터 품질 검사
3. PSI·KS·다중 검정 계산기
4. 연속 상태와 cooldown 상태 저장
5. Kafka Consumer 및 Drift Event Producer
6. 단위 테스트와 고정 데이터 통합 테스트
7. `src.monitoring.main` 실행 모듈 및 Docker 연결

## 10. 완료 기준

- 같은 입력으로 항상 같은 판정 결과가 나온다.
- 정상 기준 구간에서는 오탐률을 별도로 측정해 보고한다.
- 인위적으로 이동시킨 Feature를 탐지하는 테스트를 통과한다.
- 결측, 순서 역전, trajectory 전환을 안전하게 처리한다.
- Drift Event가 schema 검증을 통과하고 Kafka에서 실제 수신된다.
- 재학습 요청 중복 방지와 cooldown을 검증한다.
- Inference risk와 Drift 상태가 독립적으로 보존된다.

## 11. 현재 구현 상태

완료:

- 실제 train trajectory의 30시간 이상 60시간 미만 구간으로 case별 기준 분포 생성
- 공식 case별 train trajectory 70개·42,000행, 감시 Feature 52개 확인
- 기준 구간 전체 Feature 결측률 0 확인
- 평균·표준편차·최솟값·최댓값·10분위 경계와 KS 기준 표본 저장
- split manifest와 feature schema SHA-256을 기준 분포 파일에 기록
- trajectory별 독립 120개 Sliding Window 관리
- 최소 20개 관측값 준비 상태와 최신 관측값 유지
- sequence 누락·역전 및 timestamp 역전 시 해당 trajectory 창만 초기화
- 감시 Feature 누락·비수치·NaN·무한대 입력 거부
- PSI와 KS statistic/p-value 계산
- Benjamini-Hochberg 다중 검정 보정
- Feature별 Drift 및 전체 상태 판정
- 3회 연속 Drift 확인 상태 관리
- Drift Event Schema v1.0 생성·검증
- 정상, 분포 이동, 표본 부족, event schema, 기준 분포와 Sliding Window
  단위 테스트 14개 통과
- Python 문법 검사와 패키지 충돌 검사 통과

남음:

- Kafka Consumer·Producer 연결
- 재학습 cooldown 상태 저장과 trigger 연결
- 실제 Kafka 송수신 및 정상 구간 오탐률 검증

기준 분포 파일:

```text
models/monitoring/drift-reference-v1.0.0.json
```

- 파일 SHA-256: `954F22ACF9E2A08DB7A4F5860B120A91415EC5E22DB948CB03A89CF281D2C5B8`
- 재생성: `python -m src.monitoring.reference_builder`
