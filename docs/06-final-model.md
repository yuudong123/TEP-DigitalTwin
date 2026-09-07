# 최종 모델 선정 및 설명 기능

## 1. 최종 RUL 모델 선정

최종 RUL 모델은 728개의 시계열 Feature를 사용하는 Temporal XGBoost 모델로 선정한다.

| 모델 | Feature 수 | Test MAE | Test R² |
|---|---:|---:|---:|
| Baseline Model B | 52 | 3.0446 h | 0.9857 |
| Temporal XGBoost | 728 | **2.1877 h** | **0.9930** |

Temporal 모델은 Baseline 대비 RUL MAE를 약 28.1% 감소시켰다.

따라서 최종 RUL 예측 모델은 Temporal XGBoost를 사용한다.

---

## 2. 최종 고장 위험 모델 선정

4시간, 2시간, 1시간 고장 위험 모델 모두
728개의 시계열 Feature를 사용하는 Temporal XGBoost 모델로 선정한다.

| Horizon | Baseline AP | Temporal AP | Baseline F1 | Temporal F1 |
|---|---:|---:|---:|---:|
| 4시간 | 0.9907 | **0.9948** | 0.9538 | **0.9619** |
| 2시간 | 0.9775 | **0.9833** | 0.9161 | **0.9276** |
| 1시간 | 0.9418 | **0.9648** | 0.8714 | **0.8993** |

Temporal 모델은 모든 horizon에서 Baseline보다 높은 Average Precision과 F1을 기록하였다.

또한 세 horizon 모두 Test trajectory 기준 Event Detection Rate 100%를 유지하였다.

따라서 최종 고장 위험 예측 모델은 다음과 같이 확정한다.

```text
4시간 이내 고장 위험 → Temporal XGBoost
2시간 이내 고장 위험 → Temporal XGBoost
1시간 이내 고장 위험 → Temporal XGBoost
```

---

## 3. 최종 Threshold 확정

고장 위험 분류 모델의 최종 threshold는 Validation 데이터에서
F1 Score가 가장 높아지는 지점을 기준으로 결정하였다.

| Target | Threshold |
|---|---:|
| 4시간 이내 고장 위험 | 0.622766 |
| 2시간 이내 고장 위험 | 0.610441 |
| 1시간 이내 고장 위험 | 0.783028 |

Threshold 결정에는 Validation 데이터만 사용하였으며,
Test 데이터는 최종 성능 평가에만 사용하였다.

실제 시스템에서는 `reports/05-temporal/thresholds.json`에 저장된
전체 정밀도의 값을 사용한다.

XGBoost 분류 모델은 class imbalance 보정을 적용했으므로
모델 출력값은 보정된 실제 고장 확률이라기보다 `risk score`로 취급한다.

---

## 4. 모델 저장 형식

최종 XGBoost 모델은 JSON 형식으로 저장한다.

최종 모델은 다음 네 개의 파일로 구성한다.

```text
rul_hours.json
failure_within_4h.json
failure_within_2h.json
failure_within_1h.json
```

XGBoost JSON 형식은 `Booster.load_model()`을 이용해 직접 로드할 수 있으며,
향후 candidate 모델과 production 모델을 파일 단위로 비교하고 교체하기에도 적합하다.

최종 production 모델은 버전별 디렉터리에서 관리한다.

```text
models/production/v1.0.0/
```

---

## 5. 모델 버전 관리

최초 Production 모델 버전은 `v1.0.0`으로 정의한다.

```text
models/production/v1.0.0/
```

각 Production 버전에는 모델 파일과 함께 `metadata.json`을 저장한다.

Metadata에는 다음 정보를 기록한다.

- 모델 버전
- 생성 시각
- Git commit
- 모델 알고리즘
- Feature 구성 및 개수
- Sampling interval
- Temporal warm-up 시간
- 학습에 사용된 case
- 각 모델 파일명
- Classification threshold
- Test 성능
- Candidate 모델 출처

이를 통해 실제 추론 또는 모델 교체 시 어떤 코드와 모델이 사용되었는지 추적할 수 있도록 한다.

---

## 6. Feature 목록 저장

Production 모델이 사용하는 728개의 Feature 이름과 입력 순서를
모델 버전과 함께 저장한다.

```text
models/production/v1.0.0/
├─ feature_list.json
└─ feature_schema.csv
```

`feature_list.json`에는 XGBoost 추론 시 사용할 정확한 Feature 순서를 저장한다.

`feature_schema.csv`에는 각 Feature의 다음 정보를 저장한다.

- Feature 이름
- 원본 변수
- 변환 종류
- 시간 window

실시간 추론 서비스는 `feature_list.json`의 순서에 따라
728개의 입력 Feature를 구성한다.

---

## 7. SHAP 설명 기능

최종 고장 위험 XGBoost 모델의 개별 예측을 설명하기 위해
XGBoost의 TreeSHAP 기능을 사용한다.

각 입력 Feature에 대해 현재 예측에 미친 SHAP 기여도를 계산한다.

```text
SHAP > 0
→ 고장 위험 점수를 증가시키는 방향

SHAP < 0
→ 고장 위험 점수를 감소시키는 방향

|SHAP|가 클수록
→ 현재 예측에 미친 영향이 큼
```

SHAP 계산 후 모든 Feature의 기여도와 base value의 합이
XGBoost 모델의 raw prediction과 일치하는지 검사하여
TreeSHAP additivity를 검증한다.

분류 모델의 SHAP 값은 raw margin에 대한 기여도이므로
실제 고장 확률의 직접적인 변화량으로 해석하지 않는다.

---

## 8. 주요 위험 요인 출력 형식

고장 위험 예측의 설명에는 TreeSHAP을 사용한다.

현재 공정 상태에 따라 설명 대상으로 사용할 모델을 다음과 같이 결정한다.

```text
CRITICAL → 1시간 고장 위험 모델
WARNING  → 2시간 고장 위험 모델
CAUTION  → 4시간 고장 위험 모델
NORMAL   → 4시간 고장 위험 모델
```

주요 위험 요인은 선택된 모델에서 SHAP 값이 양수인 Feature 중
현재 위험도를 가장 크게 증가시킨 상위 5개 Feature를 사용한다.

각 위험 요인은 다음 정보를 포함한다.

```text
rank
feature
source_feature
transform
window_minutes
shap_value
```

SHAP 값은 모델의 raw margin에 대한 기여도이며
실제 확률 증가량으로 해석하지 않는다.

---

## 9. 최종 예측 결과 Schema

최종 AI 추론 결과는 RUL, 세 개의 고장 위험 점수,
공정 상태와 주요 위험 요인을 하나의 결과로 출력한다.

주요 구조는 다음과 같다.

```text
model_version
trajectory_key
timestamp_hours

rul
└─ hours

risk
├─ failure_within_4h
│  ├─ score
│  ├─ threshold
│  └─ alert
├─ failure_within_2h
│  ├─ score
│  ├─ threshold
│  └─ alert
└─ failure_within_1h
   ├─ score
   ├─ threshold
   └─ alert

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

공정 상태는 다음 우선순위로 판정한다.

```text
1시간 위험 threshold 이상 → CRITICAL
2시간 위험 threshold 이상 → WARNING
4시간 위험 threshold 이상 → CAUTION
모두 threshold 미만       → NORMAL
```

각 classification 출력값은 실제 보정 확률이 아닌 `risk score`로 취급한다.

주요 위험 요인은 현재 상태를 판정하는 데 사용된 위험 모델의
TreeSHAP 결과 중 위험도를 증가시키는 상위 5개 Feature를 사용한다.

---

## 10. Section 6 완료 검증

Production 모델 한 입력에 대해 다음 결과를 동시에 생성하는
통합 검증을 수행하였다.

- RUL
- 4시간 고장 위험
- 2시간 고장 위험
- 1시간 고장 위험
- 공정 상태
- SHAP 기반 주요 위험 요인

검증 결과는 다음 위치에 저장한다.

```text
reports/06-final-model/sample_prediction.json
```

이를 통해 최종 모델이 이후 실시간 Inference 및 FastAPI에서 사용할
예측 출력 계약을 확정하였다.