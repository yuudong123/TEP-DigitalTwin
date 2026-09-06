# 시계열 Feature 모델

## 1. 목적

Section 4의 Baseline 모델은 각 시점의 현재 공정값만 사용하여
RUL 및 고장 위험을 예측하였다.

Section 5에서는 현재값뿐 아니라 최근 공정값의 변화 방향,
변화속도, 변동성 및 추세를 Feature로 추가한다.

동일한 Train / Validation / Test split과 XGBoost를 사용하여
성능 향상이 Feature 복잡도 증가를 정당화하는지 평가한다.

---

## 2. 비교 대상 Baseline

대표 Baseline은 Model B이다.

```text
XMEAS 41개
+
유효 XMV 11개
=
52 features
```

주요 Test 결과:

| Task | Baseline |
|---|---:|
| RUL MAE | 3.045 h |
| RUL R² | 0.9857 |
| 4h AP | 0.9907 |
| 2h AP | 0.9775 |
| 1h AP | 0.9418 |

---

## 3. Sampling Interval

TEP 데이터의 sampling interval은 다음과 같다.

```text
0.05 hour = 3 minutes
```

따라서:

| 시간 | 시간 차이 |
|---|---:|
| 15분 | 5 sample interval |
| 30분 | 10 sample interval |
| 60분 | 20 sample interval |

5분 전에는 정확한 sample이 존재하지 않으므로
3분 전과 6분 전 값을 이용한 선형보간으로 5분 전 값을 추정한다.

보간에는 현재보다 과거인 데이터만 사용한다.

---

## 4. 현재값

Baseline Model B와 동일한 52개 현재값을 유지한다.

```text
52 features
```

---

## 5. 과거 5분 Feature

5분 전 값을 과거 관측값으로 선형보간한다.

생성 Feature:

- 변화량
- 변화속도

변화량:

```text
현재값 - 5분 전 추정값
```

변화속도:

```text
변화량 / (5 / 60 hour)
```

총:

```text
52 × 2 = 104 features
```

---

## 6. 과거 15분 Feature

생성 Feature:

- 이동평균
- 표준편차
- 변화량
- 변화속도

총:

```text
52 × 4 = 208 features
```

---

## 7. 과거 30분 Feature

생성 Feature:

- 이동평균
- 표준편차
- 최대값
- 최소값

총:

```text
52 × 4 = 208 features
```

---

## 8. 과거 60분 Feature

생성 Feature:

- 변화량
- 변화속도
- 선형 기울기

기울기는 최근 60분의 전체 관측값에 선형 회귀선을 적용하여 계산한다.

단순히 처음과 마지막 값만 비교하지 않고
60분 구간 전체 추세를 사용한다.

총:

```text
52 × 3 = 156 features
```

---

## 9. 전체 Feature 수

| 종류 | Feature 수 |
|---|---:|
| 현재값 | 52 |
| 5분 | 104 |
| 15분 | 208 |
| 30분 | 208 |
| 60분 | 156 |
| **총계** | **728** |

모든 Feature 종류를 모든 시간 window와 조합하지 않는다.

과도한 Feature 증가를 방지하면서
단기 변화, 중기 변동성, 장기 추세를 모두 표현하도록 구성하였다.

---

## 10. Warm-up

가장 긴 window는 60분이다.

따라서 각 trajectory의 처음 20개 row는 완전한 60분 과거 데이터가 없으므로
Temporal 모델용 데이터에서 제외한다.

```text
20 intervals × 3 minutes
=
60 minutes
```

---

## 11. 미래 데이터 누수 방지

모든 Feature는 현재 시점 또는 과거 데이터만 이용한다.

허용:

```text
t
t-3m
t-6m
...
t-60m
```

금지:

```text
t+3m
t+6m
...
```

Feature 생성 후 별도의 leakage validation을 수행한다.

검증 방법:

1. 전체 trajectory로 Feature 생성
2. 특정 시점 이후 데이터를 제거
3. 동일 시점까지의 데이터만 이용해 다시 Feature 생성
4. 두 결과가 동일한지 비교
5. 미래 값을 인위적으로 변경한 경우에도 현재 Feature가 변하지 않는지 비교

---

## 12. 출력

```text
data/processed/temporal/
├─ train.parquet
├─ validation.parquet
└─ test.parquet
```

Feature 정의:

```text
data/metadata/temporal_feature_schema.csv
```

생성 결과:

```text
data/metadata/temporal_dataset_summary.csv
```

---

## 13. 모델

동일한 XGBoost CUDA 환경으로 다음 네 모델을 학습한다.

- RUL 회귀
- 4시간 이내 고장 위험
- 2시간 이내 고장 위험
- 1시간 이내 고장 위험

Classification threshold는 Validation 데이터로 결정한다.

---

## 14. 최종 판단

Temporal 모델과 Section 4 Baseline Model B를 비교한다.

비교 항목:

- RUL MAE
- RUL R²
- Average Precision
- Recall
- False Positive Rate
- Event Detection Rate
- Warning Lead Time
- Feature 수
- 학습시간
- 실시간 Feature 계산 비용

단순히 성능이 더 높다는 이유만으로 Temporal 모델을 선택하지 않는다.

Feature 수가 52개에서 728개로 증가하므로
성능 향상이 운영 복잡도를 정당화하는지 함께 판단한다.

---

## 15. 실제 학습 결과

728개의 시계열 Feature를 사용하여 XGBoost CUDA 기반 RUL 회귀 모델과
4시간, 2시간, 1시간 고장 위험 모델을 학습하였다.

### RUL 성능

| 지표 | Baseline Model B | Temporal | 변화 |
|---|---:|---:|---:|
| MAE | 3.045 h | **2.188 h** | **28.1% 개선** |
| Median AE | 1.987 h | **1.531 h** | 23.0% 개선 |
| RMSE | 4.693 h | **3.248 h** | 30.8% 개선 |
| R² | 0.9857 | **0.9930** | 개선 |

시계열 Feature를 사용했을 때 RUL 평균 오차가 약 0.857시간 감소하였다.

---

### 고장 위험 성능

| Horizon | 지표 | Baseline Model B | Temporal |
|---|---|---:|---:|
| 4h | AP | 0.9907 | **0.9948** |
| 4h | F1 | 0.9538 | **0.9619** |
| 2h | AP | 0.9775 | **0.9833** |
| 2h | F1 | 0.9161 | **0.9276** |
| 1h | AP | 0.9418 | **0.9648** |
| 1h | F1 | 0.8714 | **0.8993** |

모든 horizon에서 Test trajectory Event Detection Rate는 100%를 유지하였다.

Temporal 모델의 Median Warning Lead Time은 다음과 같다.

| Horizon | Median Warning Lead |
|---|---:|
| 4h | 4.0 h |
| 2h | 2.0 h |
| 1h | 1.0 h |

---

## 16. 복잡도 대비 성능 판단

Baseline Model B는 52개 Feature를 사용하고,
Temporal 모델은 728개 Feature를 사용한다.

Feature 수는 약 14배 증가하였지만 다음과 같은 성능 개선이 확인되었다.

- RUL MAE 약 28.1% 감소
- RUL RMSE 약 30.8% 감소
- 모든 고장 위험 horizon에서 Average Precision 개선
- 특히 1시간 고장 위험 AP가 0.9418에서 0.9648로 개선
- Event Detection Rate 100% 유지
- 2시간 및 1시간 모델의 Point False Positive Rate 감소

예지보전 시스템에서 RUL 예측 정확도가 핵심 기능이라는 점을 고려하면
시계열 Feature의 성능 향상은 증가한 Feature 복잡도를 감수할 가치가 있다고 판단한다.

따라서 Section 6의 최종 모델 후보는 Temporal Feature 모델로 선정한다.

단, 728개 Feature 전체를 최종 운영 환경에 그대로 사용할지는
Feature Importance 및 SHAP 분석을 통해 추가 검토한다.