# 모델 검증용 데이터셋 설계

## 1. 문서 목적

이 문서는 TEP Digital Twin 프로젝트에서 사용할 학습·검증·테스트 데이터의 구성 원칙을 정의한다.

주요 목적은 다음과 같다.

- 동일 Run-to-Failure trajectory가 학습과 평가에 동시에 포함되는 데이터 누수 방지
- 시스템 RUL 정답 생성 규칙 확정
- 고장 위험 분류 정답 생성 규칙 확정
- 일반적인 unseen trajectory 평가와 unseen scenario 평가를 분리
- 모델 간 비교 시 동일한 평가 데이터를 사용하도록 기준 고정
- 비공식 추가 CSV를 공식 데이터와 분리

---

## 2. 기본 사용 데이터

기본 학습 및 평가에는 공식 통합 HDF5에 포함된 다음 6개 시나리오만 사용한다.

```text
case1
case2
case3
case4
case5
case6
```

각 case에는 100개의 독립 Run-to-Failure trajectory가 존재한다.

따라서 기본 데이터는:

```text
6 scenarios
×
100 trajectories
=
600 independent trajectories
```

로 구성한다.

---

## 3. 추가 데이터의 처리

다음 두 CSV는 기본 학습 데이터에서 제외한다.

```text
case5_1.csv
case7.csv
```

두 파일은 공식 6개 시나리오와 동일한 컬럼 구조를 가지고 있으며 각각 100개의 독립 trajectory를 포함하지만,
공식 통합 HDF5에는 포함되어 있지 않고 정확한 시나리오 정의가 확인되지 않았다.

따라서 기본 모델의 학습, validation, test에는 사용하지 않는다.

향후 다음 목적으로 별도 사용할 수 있다.

- 추가 일반화 테스트
- 외부 데이터 성격의 보조 평가
- 모델 강건성 검증

---

## 4. trajectory 식별자

CSV 내부의 `Id`는 파일별로 반복되므로 `Id`만으로 trajectory를 식별하지 않는다.

프로젝트 내부의 고유 trajectory 식별자는 다음과 같이 정의한다.

```text
trajectory_key = case + "::" + Id
```

예:

```text
case1::1
case1::2
case2::1
```

따라서 `case1::1`과 `case2::1`은 완전히 다른 Run-to-Failure trajectory이다.

여기서 trajectory는 **하나의 독립적인 Run-to-Failure 시뮬레이션이 정상 상태에서 시작해 열화되고 종료 조건에 도달할 때까지의 전체 시계열 기록**을 의미한다.

---

## 5. 시간축

데이터의 `Time` 단위는 hour이며 기본 간격은:

```text
0.05 hour
=
3 minutes
```

이다.

원본 시간 순서는 유지한다.

trajectory 내부 데이터를 임의로 shuffle해서 시계열의 의미를 훼손하지 않는다.

---

## 6. End of Life

각 trajectory의 마지막 `Time`을 해당 Run의 시스템 EOL로 정의한다.

```python
eol_time = trajectory["Time"].max()
```

각 Run은 반응기, 분리기 또는 정제기 중 하나가 shutdown threshold에 도달했을 때 종료되므로,
마지막 관측값은 해당 시뮬레이션의 시스템 종료 시점이다.

---

## 7. RUL target

각 시점의 시스템 잔여수명은 다음과 같이 생성한다.

```python
rul_hours = eol_time - current_time
```

예:

```text
현재 시간 = 120.0 h
EOL       = 137.5 h

RUL       = 17.5 h
```

추가로 trajectory 길이가 서로 다른 영향을 줄이기 위해 정규화 RUL도 생성한다.

```python
rul_fraction = rul_hours / trajectory_duration
```

값의 의미:

```text
1.0에 가까움 = 수명 초반
0.0에 가까움 = EOL 직전
```

---

## 8. 고장 위험 target

고장 위험 분류에서는 현재 시점부터 EOL까지 남은 시간을 기준으로 정답을 생성한다.

### 4시간 이내 고장

```python
failure_within_4h = int(rul_hours <= 4.0)
```

### 2시간 이내 고장

```python
failure_within_2h = int(rul_hours <= 2.0)
```

### 1시간 이내 고장

```python
failure_within_1h = int(rul_hours <= 1.0)
```

예를 들어:

```text
RUL = 0.8 h
```

이면:

```text
failure_within_4h = 1
failure_within_2h = 1
failure_within_1h = 1
```

이 된다.

---

## 9. 데이터 분할의 최소 단위

데이터 분할의 최소 단위는 행(row)이 아니라 **trajectory 전체**이다.

금지되는 예:

```text
case1::17의 0~100시간
→ train

case1::17의 100시간 이후
→ test
```

이렇게 하면 같은 Run의 패턴을 모델이 학습과 평가에서 동시에 보게 된다.

반드시:

```text
case1::17 전체 → train
```

또는:

```text
case1::17 전체 → validation
```

또는:

```text
case1::17 전체 → test
```

중 하나만 선택한다.

---

## 10. 기본 Train / Validation / Test 분할

일반적인 모델 개발에서는 모든 공식 시나리오가 train, validation, test에 포함되도록 한다.

각 case의 100 trajectory를 다음 비율로 나눈다.

```text
Train      70
Validation 15
Test       15
```

6개 case 전체에서는:

```text
Train      = 70 × 6 = 420 trajectories
Validation = 15 × 6 = 90 trajectories
Test       = 15 × 6 = 90 trajectories
```

총 600 trajectory이다.

---

## 11. 분할 재현성

trajectory 배정은 고정된 random seed를 사용한다.

```python
RANDOM_STATE = 42
```

한 번 결정된 split은 CSV 또는 JSON으로 저장하여 이후 모든 모델이 동일한 train / validation / test를 사용하도록 한다.

예:

```text
data/metadata/split_manifest.csv
```

예상 형식:

| trajectory_key | case | Id | split |
|---|---|---:|---|
| case1::1 | case1 | 1 | train |
| case1::2 | case1 | 2 | test |
| case1::3 | case1 | 3 | validation |

모델마다 새로 랜덤 분할하지 않는다.

---

## 12. 기본 Test의 목적

기본 Test는 다음 질문에 답하기 위한 평가이다.

> 이미 학습한 열화 시나리오에서 새롭게 생성된 Run-to-Failure trajectory를 모델이 예측할 수 있는가?

예:

```text
case1의 일부 Id
→ train

case1의 처음 보는 다른 Id
→ test
```

같은 case이지만 noise, 열화 시작 시점, 열화 속도 등이 다른 새로운 Run을 평가한다.

---

## 13. Leave-One-Case-Out 검증

기본 Test와 별도로 더 강한 일반화 검증을 수행한다.

하나의 case 전체를 test에서 제외한다.

예:

```text
Train
case2
case3
case4
case5
case6

Test
case1 전체
```

이 과정을 6개 case에 대해 반복한다.

```text
Fold 1 → case1 hold-out
Fold 2 → case2 hold-out
Fold 3 → case3 hold-out
Fold 4 → case4 hold-out
Fold 5 → case5 hold-out
Fold 6 → case6 hold-out
```

이를 Leave-One-Case-Out(LOCO) 평가로 사용한다.

LOCO 평가의 목적은 다음 질문에 답하는 것이다.

> 학습 과정에서 보지 못한 새로운 열화 시나리오에서도 모델이 위험도를 구별하거나 RUL을 추정할 수 있는가?

---

## 14. Validation의 역할

Validation 데이터는 모델 선택과 threshold 결정에 사용한다.

사용 예:

- XGBoost hyperparameter 선택
- feature 구성 선택
- classification threshold 결정
- Baseline과 시계열 Feature 모델 비교
- 모델 승격 기준 설정

Test 데이터로 threshold를 정하거나 hyperparameter를 선택하지 않는다.

---

## 15. Classification threshold

고장 위험 모델의 기본 확률 cutoff를 무조건 `0.5`로 고정하지 않는다.

이전 LOCO 사전검증에서 일부 case는:

```text
AP / ROC-AUC는 매우 높지만
threshold 0.5에서 recall이 낮음
```

현상이 확인되었다.

따라서 threshold는 validation 데이터에서 결정한다.

다음 조건을 함께 고려한다.

- Event Detection Rate
- 사전 경고시간
- False Alarm Rate
- Recall

최종 test에는 validation에서 결정된 threshold를 그대로 적용한다.

---

## 16. 평가 단위

시계열 예지보전에서는 개별 row 정확도만 평가하지 않는다.

### Point-level 평가

각 3분 시점에 대한 예측 품질이다.

예:

- Average Precision
- ROC-AUC
- Recall
- False Positive Rate
- MAE
- R²

### Event-level 평가

한 trajectory 전체에서 실제 종료를 얼마나 유용하게 예측했는지 평가한다.

예:

- Event Detection Rate
- 최초 경고시간
- 지속 경고 여부
- 고장 이전 False Alarm
- trajectory별 최대 위험 확률

최종 프로젝트 판단에서는 Event-level 결과를 중요하게 본다.

---

## 17. 지속 경고

단 한 번의 3분짜리 위험 확률 상승만으로 실제 경고를 발생시키지 않는다.

예를 들어:

```text
2개 연속 위험 판정
=
약 6분 지속
```

같은 조건을 적용할 수 있다.

정확한 지속시간은 validation 단계에서 확정한다.

목적은 일시적인 sensor noise로 인한 경고를 줄이는 것이다.

---

## 18. 학습 feature에서 제외하는 값

다음 값은 모델 feature에 포함하지 않는다.

```text
Id
Time
trajectory_key
case 번호
source filename
EOL time
rul_hours
rul_fraction
life_fraction
failure target
```

특히 `Time`은 현재 Run이 얼마나 진행되었는지를 직접 알려주므로,
모델이 센서 열화 패턴 대신 단순 경과시간만 학습할 위험이 있다.

---

## 19. Baseline feature 정책

Baseline에서는 우선 **공정 측정값 중심의 모델**을 만든다.

### Model A

```text
측정 변수만 사용
```

### Model B

```text
측정 변수
+
조작 변수
```

두 모델의 성능을 비교한다.

조작 변수를 추가했을 때 성능이 지나치게 상승한다면,
모델이 공정의 물리적 열화보다 제어기의 보상 행동에 의존하는지 확인한다.

최종 feature 구성은 이 비교 이후 결정한다.

---

## 20. 데이터 정규화

XGBoost 기반 Baseline에서는 feature scaling을 필수로 사용하지 않는다.

이후 신경망 또는 거리 기반 모델을 사용할 경우 별도의 scaling을 적용할 수 있다.

scaler를 사용하는 경우 반드시 train 데이터로만 fit한다.

```text
Train
→ scaler.fit()

Validation / Test
→ scaler.transform()
```

Validation이나 Test 통계를 preprocessing에 사용하지 않는다.

---

## 21. 결측치 처리

원본 데이터에 결측치가 존재하는지 먼저 검사한다.

결측치가 없다면 별도의 보간을 하지 않는다.

향후 실시간 Kafka 환경에서 센서 누락이 발생할 경우의 처리 방식은 서비스 구현 단계에서 별도로 정의한다.

---

## 22. 기본 데이터 해상도

원본의 3분 간격을 유지한다.

Baseline 단계에서는 각 시점의 현재 센서값을 사용한다.

시계열 Feature 단계에서는 과거 데이터만 사용하여 rolling feature를 생성한다.

미래 데이터는 어떠한 형태로도 feature 생성에 사용하지 않는다.

---

## 23. 공식 평가 데이터와 추가 평가 데이터 구분

평가 데이터는 다음 두 종류로 관리한다.

### 공식 평가

```text
case1 ~ case6
```

에서 생성한 Train / Validation / Test와 LOCO.

### 추가 평가

```text
case5_1
case7
```

정확한 공식 scenario 정의가 확인되지 않은 추가 CSV.

이 둘의 결과를 합산하지 않는다.

포트폴리오의 주요 성능은 공식 `case1~case6` 결과를 기준으로 제시한다.

---

## 24. 데이터셋 생성 결과물

데이터 구축 단계가 완료되면 최소 다음 파일을 생성한다.

```text
data/
├─ raw/
├─ processed/
│  ├─ train.*
│  ├─ validation.*
│  └─ test.*
│
└─ metadata/
   ├─ split_manifest.csv
   ├─ feature_schema.csv
   └─ trajectory_summary.csv
```

대용량 데이터는 CSV보다 Parquet 사용을 우선 검토한다.

---

## 25. 최종 원칙

본 프로젝트의 데이터 구성은 다음 원칙을 따른다.

1. 하나의 trajectory는 하나의 split에만 존재한다.
2. Test 정보를 학습이나 threshold 결정에 사용하지 않는다.
3. RUL은 실제 trajectory EOL로부터 계산한다.
4. 고장 위험 target은 EOL까지 남은 시간으로 계산한다.
5. `Time`과 RUL 관련 정답 정보는 feature에서 제외한다.
6. 모든 모델은 가능한 한 동일 split에서 비교한다.
7. 일반 unseen trajectory 성능과 unseen scenario 성능을 따로 평가한다.
8. 공식 6개 scenario와 추가 CSV 결과를 섞지 않는다.
9. Point metric뿐 아니라 Event metric을 반드시 사용한다.
10. 시계열 feature에는 현재와 과거 데이터만 사용한다.

---

## 26. 실제 데이터셋 생성 결과

공식 `case1`~`case6`을 기준으로 총 600개의 Run-to-Failure trajectory를 검증하였다.

검증 결과:

- 결측치 없음
- infinite value 없음
- trajectory 내부 중복 timestamp 없음
- 모든 sampling interval은 0.05 hour(3분)
- `Agitator` 컬럼은 전체 데이터에서 100으로 고정된 상수 변수로 확인되어 feature에서 제외

trajectory 단위 고정 split은 다음과 같다.

| Split | Trajectory 수 |
|---|---:|
| Train | 420 |
| Validation | 90 |
| Test | 90 |

가공 데이터는 Parquet 형식으로 저장하였다.

```text
data/processed/
├─ train.parquet
├─ validation.parquet
└─ test.parquet
```

고장 위험 target의 positive 비율은 각 split에서 거의 동일하게 유지되었다.

| Target | Train | Validation | Test |
|---|---:|---:|---:|
| 4시간 이내 고장 | 3.0204% | 3.0290% | 3.0197% |
| 2시간 이내 고장 | 1.5287% | 1.5332% | 1.5281% |
| 1시간 이내 고장 | 0.7829% | 0.7853% | 0.7823% |