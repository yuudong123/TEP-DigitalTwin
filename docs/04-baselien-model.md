# AI Baseline 모델

## 1. 목적

TEP Digital Twin 프로젝트에서 사용할 첫 번째 정식 AI Baseline 모델을 구축한다.

Baseline 단계의 목적은 복잡한 시계열 Feature Engineering을 적용하기 전에
현재 시점의 공정 변수만으로 어느 정도의 RUL 예측 및 고장 위험 예측이 가능한지 확인하는 것이다.

이 결과는 이후 시계열 Feature 모델의 비교 기준으로 사용한다.

---

## 2. 학습 알고리즘

Baseline 모델은 XGBoost를 사용한다.

GPU 가속은 NVIDIA CUDA를 이용하며 다음 설정을 기본으로 사용한다.

```python
tree_method="hist"
device="cuda"
```

학습 장비의 NVIDIA GPU를 사용하여 대용량 TEP 데이터를 처리한다.

---

## 3. 입력 Feature 구성

Baseline에서는 두 가지 Feature 구성을 비교한다.

### Model A - 측정 변수

TEP의 41개 XMEAS 측정 변수만 사용한다.

```text
41 XMEAS
```

목적은 공정 센서 및 조성 측정값만으로 열화와 고장 위험을 예측할 수 있는지 확인하는 것이다.

---

### Model B - 측정 변수 + 조작 변수

41개 XMEAS와 11개의 유효 XMV를 사용한다.

```text
41 XMEAS
+
11 XMV
=
52 features
```

원래 XMV는 12개이지만 `Agitator`는 전체 공식 데이터에서 값이 100으로 고정되어 있으므로 제외한다.

Model A와 Model B를 비교하여 제어기의 조작 정보가 모델 성능에 얼마나 영향을 주는지 확인한다.

---

## 4. Baseline에서 제외하는 변수

다음 변수는 모델 입력에서 제외한다.

```text
Id
Time
case
trajectory_key

rul_hours
rul_fraction

failure_within_4h
failure_within_2h
failure_within_1h

Agitator

Liquid Input Stripper
Liquid Input Separator
Liquid Input Reactor
```

`Id`, `Time`, case 정보와 target은 데이터 누수를 방지하기 위해 제외한다.

`Agitator`는 상수 변수이므로 제외한다.

세 개의 `Liquid Input ...` 변수는 기존 TEP 표준 XMEAS/XMV에 포함되지 않는 추가 변수이며,
열화 상태를 직접적으로 나타낼 가능성을 배제할 수 없으므로 Baseline에서는 사용하지 않는다.

---

## 5. 예측 문제

총 네 가지 모델을 각 Feature 구성별로 학습한다.

### RUL 회귀

```text
Target = rul_hours
```

현재 시점부터 시스템 EOL까지 남은 시간을 hour 단위로 예측한다.

### 4시간 고장 위험

```text
Target = failure_within_4h
```

### 2시간 고장 위험

```text
Target = failure_within_2h
```

### 1시간 고장 위험

```text
Target = failure_within_1h
```

따라서:

```text
Model A: 4 models
Model B: 4 models

총 8 models
```

을 학습한다.

---

## 6. 학습 데이터

Section 3에서 생성한 고정 데이터셋을 사용한다.

| Split | Trajectory |
|---|---:|
| Train | 420 |
| Validation | 90 |
| Test | 90 |

파일:

```text
data/processed/
├─ train.parquet
├─ validation.parquet
└─ test.parquet
```

동일 trajectory가 여러 split에 포함되지 않는다.

---

## 7. Validation 사용

Validation 데이터는 다음 용도로 사용한다.

- Early Stopping
- Classification threshold 결정
- Model A / Model B 비교
- 이후 모델 선택

Test 데이터는 모델 학습이나 threshold 결정에 사용하지 않는다.

---

## 8. Classification threshold

고장 위험 모델의 threshold를 무조건 `0.5`로 사용하지 않는다.

Baseline에서는 Validation 데이터의 Precision-Recall 결과를 이용해
F1 score가 가장 높은 threshold를 선택한다.

```text
Validation
→ threshold 결정

Test
→ 결정된 threshold 그대로 적용
```

이는 이전 실험에서 ranking 성능은 높지만 고정 threshold 0.5에서 recall이 크게 낮아지는 경우가 있었기 때문이다.

최종 시스템에서는 Event-level 요구조건을 이용한 threshold 정책으로 추가 개선할 수 있다.

---

## 9. Class imbalance

고장 직전 데이터는 전체 데이터에서 차지하는 비율이 매우 낮다.

Section 3에서 확인한 Train positive 비율은 다음과 같다.

| Target | Positive 비율 |
|---|---:|
| 4시간 | 3.0204% |
| 2시간 | 1.5287% |
| 1시간 | 0.7829% |

따라서 분류 모델 학습 시 Train 데이터에서 다음 값을 계산한다.

```text
scale_pos_weight
=
negative samples / positive samples
```

이를 XGBoost 분류 모델에 적용한다.

---

## 10. RUL 평가 지표

RUL 모델에서는 다음 지표를 사용한다.

- MAE
- Median Absolute Error
- RMSE
- R²

주요 기준은 MAE로 사용한다.

예측 RUL이 음수가 될 경우 실제 서비스에서는 의미가 없으므로 평가 시 최소값을 0으로 제한한다.

---

## 11. 고장 위험 Point-level 평가

분류 모델에서는 다음 지표를 사용한다.

- Average Precision
- ROC-AUC
- Precision
- Recall
- F1
- False Positive Rate

Class imbalance가 크기 때문에 Accuracy를 주요 성능 지표로 사용하지 않는다.

특히 Average Precision을 중요하게 본다.

---

## 12. Event-level 평가

각 trajectory 전체에서도 모델의 경고 성능을 평가한다.

경고는 threshold를 한 번 넘었다고 즉시 확정하지 않고
2개 연속 시점에서 threshold를 초과했을 때 지속 경고로 판단한다.

TEP의 sampling interval은 3분이므로:

```text
2 samples
=
약 6분 지속
```

이다.

평가 항목:

- Event Detection Rate
- 최초 지속 경고의 RUL
- Median Warning Lead Time
- 목표 horizon 이전 조기 경고 발생률

목표 horizon 이전의 경고는 반드시 잘못된 경고라고 볼 수 없으므로
별도의 `early alert` 항목으로 기록한다.

---

## 13. Baseline 확률값의 의미

분류 모델의 출력은 Baseline 단계에서는 고장 위험 score로 취급한다.

Class imbalance 보정을 위해 `scale_pos_weight`를 적용하므로
출력값을 완전히 보정된 실제 고장 확률이라고 단정하지 않는다.

필요한 경우 최종 모델 단계에서 probability calibration을 추가한다.

---

## 14. 모델 저장

학습된 모델은 다음 위치에 저장한다.

```text
models/candidates/04-baseline/
├─ model_a/
│  ├─ rul_hours.json
│  ├─ failure_within_4h.json
│  ├─ failure_within_2h.json
│  └─ failure_within_1h.json
│
└─ model_b/
   ├─ rul_hours.json
   ├─ failure_within_4h.json
   ├─ failure_within_2h.json
   └─ failure_within_1h.json
```

Baseline 결과는 다음 위치에 저장한다.

```text
reports/04-baseline/
└─ baseline_metrics.csv
```

---

## 15. 완료 기준

Baseline 단계는 다음 조건을 만족하면 완료한다.

1. CUDA를 이용하여 XGBoost가 정상 학습된다.
2. Model A의 네 모델이 생성된다.
3. Model B의 네 모델이 생성된다.
4. Validation을 이용한 classification threshold가 생성된다.
5. Test에서 RUL 및 고장 위험 성능을 평가한다.
6. Point-level 및 Event-level 결과를 저장한다.
7. Model A와 Model B의 성능 차이를 분석한다.
8. 이후 시계열 Feature 모델이 넘어야 할 Baseline 성능을 확정한다.

---

## 16. 실제 Baseline 학습 결과

XGBoost CUDA를 이용하여 Model A와 Model B 각각에 대해
RUL 회귀 모델과 4시간, 2시간, 1시간 고장 위험 분류 모델을 학습하였다.

총 8개의 Baseline 모델이 생성되었다.

### RUL 예측

| Feature 구성 | Test MAE | Median AE | RMSE | R² |
|---|---:|---:|---:|---:|
| Model A - XMEAS 41개 | 3.206 h | 2.065 h | 4.975 h | 0.9839 |
| Model B - XMEAS 41개 + XMV 11개 | **3.045 h** | **1.987 h** | **4.693 h** | **0.9857** |

Model B가 Model A보다 RUL MAE 기준 약 5% 개선되었다.

### 고장 위험 예측

| Horizon | Model | AP | Precision | Recall | F1 | Point FPR |
|---|---|---:|---:|---:|---:|---:|
| 4h | A | 0.9902 | 0.9319 | 0.9638 | 0.9476 | 0.00219 |
| 4h | B | **0.9907** | **0.9523** | 0.9553 | **0.9538** | **0.00149** |
| 2h | A | 0.9744 | 0.8551 | 0.9694 | 0.9086 | 0.00255 |
| 2h | B | **0.9775** | **0.8669** | **0.9713** | **0.9161** | **0.00231** |
| 1h | A | 0.9381 | 0.7968 | 0.9576 | 0.8699 | 0.00193 |
| 1h | B | **0.9418** | **0.7990** | **0.9582** | **0.8714** | **0.00190** |

모든 고장 위험 모델은 Test의 90개 trajectory에서 지속 경고 기준
100% Event Detection Rate를 기록하였다.

### Baseline 대표 모델

Model B를 프로젝트의 대표 Baseline으로 선정한다.

Model B의 입력은 다음과 같다.

- XMEAS 측정 변수 41개
- 상수 변수 `Agitator`를 제외한 XMV 조작 변수 11개
- 총 52개 feature

제어 변수를 추가했을 때 RUL과 고장 위험 예측 성능이 모두 소폭 개선되었으며,
비정상적으로 큰 성능 상승은 관찰되지 않았다.

따라서 이후 시계열 Feature 모델은 Model B의 성능을 주요 비교 기준으로 사용한다.

### Baseline 기준 성능

이후 모델이 비교해야 할 주요 Baseline은 다음과 같다.

| Task | Baseline |
|---|---:|
| RUL MAE | 3.045 h |
| RUL R² | 0.9857 |
| 4h AP | 0.9907 |
| 2h AP | 0.9775 |
| 1h AP | 0.9418 |