# TEP 데이터 구조 및 고장 시나리오 분석

## 1. 문서 목적

이 문서는 TEP Digital Twin 프로젝트에서 사용하는 Run-to-Failure 데이터셋의 구조와 변수 역할을 정리하고, 이후 모델 학습에서 사용할 변수와 제외할 변수를 결정하기 위한 기준 문서이다.

특히 다음 문제를 명확히 하는 것을 목적으로 한다.

- 하나의 시뮬레이션 실행 단위가 무엇인지
- 시간축과 잔여수명(RUL)을 어떻게 정의하는지
- 각 변수가 실제 측정값인지 제어값인지
- 반응기, 분리기, 정제기와 어떤 변수가 관련되는지
- 열화 시나리오와 운전조건을 어떻게 구분할지
- 모델 학습 과정에서 데이터 누수를 일으킬 수 있는 변수가 무엇인지

---

# 2. 데이터셋 개요

사용 데이터는 **Tennessee Eastman Process Run-to-Failure Dataset**이다.

TEP(테니시 이스트만 프로젝트)는 연속 화학 생산공정을 모사한 시뮬레이션 공정이며, 이번 데이터셋은 일반적인 TEP 이상진단 데이터와 달리 예지보전을 위해 정상 상태부터 시스템 종료까지의 전체 수명 주기를 생성한 데이터이다.

데이터는 실제 공장에서 측정한 값이 아니라 **시뮬레이션으로 생성된 산업공정 데이터**이다.

주요 연구 목적은 다음과 같다.

- 설비 및 전체 시스템 상태지표 생성
- 잔여수명 예측
- 열화 및 고장 탐지
- 설명 가능한 예지보전
- 여러 설비가 동시에 열화될 때의 상호작용 분석
- 유지보수 의사결정 지원

공식 데이터 설명에서는 다음 세 설비를 주요 열화 대상으로 다룬다.

1. 반응기
2. 제품 분리기
3. 정제기

---

# 3. 데이터 파일 구조

현재 확보한 데이터에는 다음 CSV가 존재한다.

```text
case1.csv
case2.csv
case3.csv
case4.csv
case5.csv
case5_1.csv
case6.csv
case7.csv
```

각 파일에서 확인된 구조는 동일하다.

- 총 58개 컬럼
- `Id`
- `Time`
- 공정 관련 변수 56개

공식 통합 HDF5 파일인 `tep.h5`에는 다음 6개의 Run-to-Failure 열화 시나리오 그룹이 존재한다.

- case1
- case2
- case3
- case4
- case5
- case6

각 시나리오에는 100개의 독립 Run-to-Failure simulation이 존재하므로,
공식 분석 대상은 총 600개의 Run-to-Failure trajectory로 정의한다.

`case5_1.csv`와 `case7.csv`는 별도로 생성된 추가 실험 데이터로 판단되지만,
정확한 생성 목적과 시나리오 정의는 현재 제공된 공식 문서만으로 확인되지 않는다.

본 프로젝트에서는 재현성과 공식 시나리오 정의를 우선하여
기본 학습 및 평가 데이터는 `case1`~`case6`만 사용한다.

`case5_1.csv`와 `case7.csv`는 향후 추가 일반화 테스트 또는 보조 실험 데이터로 별도 보관한다.

| 시나리오 | 열화 진행 | 운전 모드 |
|---|---|---|
| 1 | 반응기 (상승, 느림) → 분리기 (상승, 중간) | 6 |
| 2 | 반응기 (상승, 중간) → 정제기 (상승, 중간) | 4 |
| 3 | 분리기 (상승, 중간) → 정제기 (상승, 빠름) | 6 |
| 4 | 반응기 (상승, 느림) → 분리기 (상승, 중간) → 정제기 (상승, 빠름) | 2 |
| 5 | 반응기 (하강, 느림) → 정제기 (하강, 중간) → 정제기 (상승, 높음) | 1 |
| 6 | 분리기 (상승, 느림) → 정제기 (상승, 중간) → 분리기 (상승, 높음) | 5 |

각 시나리오는 하나의 설비에 독립적인 고장을 주는 방식보다는,
첫 번째 설비의 열화가 다른 설비의 열화로 이어지는 연쇄적 또는 상호작용형 열화를 포함한다.

또한 시나리오마다 서로 다른 운전 모드가 사용되므로,
운전조건의 차이와 열화에 의한 변화를 구분해야 한다.

---

## 데이터 생성 과정

각 Run-to-Failure 시뮬레이션은 다음 순서로 생성된다.

1. 공정을 초기화한다.
2. 약 30시간 동안 안정 상태에 도달하도록 운전한다.
3. 이후 정상 운전을 계속한다.
4. 약 60~70시간 사이의 무작위 시점에 열화를 시작한다.
5. 반응기, 분리기, 정제기 중 하나 이상의 설비에 열화를 적용한다.
6. 열화는 가속되는 지수형 형태로 진행된다.
7. 열화 방향은 증가 또는 감소 방향일 수 있다.
8. 열화 속도는 느림, 중간, 빠름으로 구성된다.
9. 단일 설비뿐 아니라 두 개 또는 세 개 설비의 연쇄 열화도 존재한다.
10. 반응기, 분리기, 정제기 중 하나가 shutdown threshold에 도달하면 시뮬레이션을 종료한다.
11. 정상 상태부터 종료까지의 전체 기록을 하나의 Run-to-Failure trajectory로 저장한다.

# 4. `Id`의 의미

`Id`는 하나의 독립적인 Run-to-Failure 시뮬레이션을 의미한다.

예:

```text
Id = 17
```

이면 해당 `Id`의 모든 행은 **17번째 독립 시뮬레이션이 정상 운전에서 시작하여 시스템 종료에 도달할 때까지 기록된 하나의 수명 주기**이다.

따라서 다음 두 데이터는 서로 다른 설비 수명 실험으로 취급한다.

```text
case1.csv / Id 17
case1.csv / Id 18
```

서로 다른 파일의 동일한 `Id`도 동일 trajectory가 아니다.

따라서 프로젝트 내부에서는 다음과 같이 고유 ID를 생성하는 것이 안전하다.

```text
case1.csv::17
case2.csv::17
```

---

# 5. `Time`의 의미

`Time`은 해당 Run이 시작된 이후 경과한 시뮬레이션 시간이다.

실제 CSV에서 다음과 같이 증가한다.

```text
0.00
0.05
0.10
0.15
...
```

시간 단위는 hour이므로:

```text
0.05 hour × 60
= 3 minutes
```

즉 기본 샘플링 간격은 **3분**이다.

한 행은 해당 시뮬레이션의 특정 3분 시점에서 측정된 공정 상태를 의미한다.

---

# 6. End of Life 정의

각 시뮬레이션은 반응기, 분리기 또는 정제기 중 하나가
사전에 정의된 임계 운전조건 또는 shutdown threshold에 도달하면 종료된다.

따라서 각 trajectory의 마지막 관측값은 단순한 데이터 파일 종료가 아니라
해당 시뮬레이션에서 정의된 시스템 End of Life에 해당한다.

단, 이는 실제 화학공장에서 관측된 물리적 고장이 아니라
수정된 TEP 시뮬레이션 모델 내부에 정의된 운전 한계에 따른 EOL이다.

---

# 7. RUL 정의

시스템 잔여수명은 다음과 같이 계산한다.

```text
RUL = trajectory 종료시간 - 현재 Time
```

예:

```text
현재 Time = 120.00 h
EOL        = 137.35 h

RUL        = 17.35 h
```

Python 표현:

```python
rul_hours = trajectory_end_time - current_time
```

정규화한 RUL은 다음과 같이 계산할 수 있다.

```python
rul_fraction = rul_hours / trajectory_duration
```

따라서:

```text
1.0에 가까움 = 수명 초반
0.0에 가까움 = EOL에 가까움
```

이다.

---

# 8. 전체 변수 구성

공정 관련 56개 변수는 크게 다음과 같이 구분할 수 있다.

```text
공정 측정값
+
조작 변수
+
추가 공정 상태 변수
```

모든 컬럼을 단순히 "센서 56개"라고 부르지 않는다.

---

# 9. 공정 측정 변수

기존 TEP 구조를 기준으로 **41개의 측정 변수**가 존재한다.

## 9.1 유량 및 공정 측정값

- A 원료 유량
- D 원료 유량
- E 원료 유량
- A/C 혼합 원료 유량
- 재순환 유량
- 반응기 투입 유량

## 9.2 반응기

- 반응기 압력
- 반응기 액위
- 반응기 온도

## 9.3 배출 및 분리기

- 퍼지 유량
- 제품 분리기 온도
- 제품 분리기 액위
- 제품 분리기 압력
- 제품 분리기 하부 배출량

## 9.4 정제기

- 정제기 액위
- 정제기 압력
- 정제기 하부 배출량
- 정제기 온도
- 정제기 증기 유량

## 9.5 기타 설비

- 압축기 부하
- 반응기 냉각수 출구 온도
- 분리기 냉각수 출구 온도

---

# 10. 성분 분석 측정값

공정에는 물질 조성을 측정하는 분석값도 포함된다.

## 반응기 유입 성분

- Component A to Reactor
- Component B to Reactor
- Component C to Reactor
- Component D to Reactor
- Component E to Reactor
- Component F to Reactor

## 퍼지 가스 성분

- Component A to Purge
- Component B to Purge
- Component C to Purge
- Component D to Purge
- Component E to Purge
- Component F to Purge
- Component G to Purge
- Component H to Purge

## 제품 성분

- Component D to Product
- Component E to Product
- Component F to Product
- Component G to Product
- Component H to Product

이 값들도 공정에서 관측되는 **측정 변수**로 분류한다.

---

# 11. 조작 변수

TEP에는 **12개의 조작 변수**가 존재한다.

조작 변수란 단순히 센서로 읽는 값이 아니라, 공정을 원하는 상태로 유지하기 위해 제어기가 직접 변경하는 값이다.

현재 CSV에서 다음과 같은 `msv` 계열 컬럼이 이에 해당한다.

- D 원료 제어
- E 원료 제어
- A 원료 제어
- A/C 원료 제어
- 압축기 재순환 밸브
- 퍼지 밸브
- 분리기 액체 배출 제어
- 정제기 제품 배출 제어
- 정제기 증기 제어
- 반응기 냉각수 제어
- 응축기 냉각수 제어
- 교반기 제어

이 값들은 공정 상태의 결과라기보다 **제어 시스템이 공정을 유지하기 위해 취한 행동**을 나타낸다.

따라서 모델 입력에 사용할 경우 주의가 필요하다.

예를 들어 설비가 열화됨에 따라 제어기가 밸브를 적극적으로 조절하기 시작한다면:

```text
열화
→ 제어기의 보상 동작 증가
→ msv 변화
```

가 발생할 수 있다.

모델이 이 값을 이용하면 열화를 잘 예측할 수도 있지만, 실제 사용 목적에 따라 제어 행동을 입력으로 허용할 것인지 별도로 결정해야 한다.

---

# 12. 추가 공정 상태 변수

현재 데이터에는 기존 41개 측정값 + 12개 조작값 외에 다음과 같은 추가 변수가 존재한다.

- Liquid Input Reactor
- Liquid Input Separator
- Liquid Input Stripper

이 세 변수는 원래 일반적인 TEP 41개 측정값 + 12개 조작변수 목록에는 포함되지 않는 추가 상태 변수다.

따라서 최종 모델 입력으로 사용하기 전에 데이터 생성 방식과 물리적 의미를 추가 확인한다.

---

# 13. 주요 설비별 변수 매핑

## 반응기

우선 주요 모니터링 변수로 다음을 사용한다.

- Reactor Pressure
- Reactor Level
- Reactor Temperature
- Reactor Feed Rate
- Reactor Cooling Water Outlet Temp
- 반응기 관련 원료 유량
- 반응기 유입 물질 조성

관련 제어 변수:

- 원료 공급 제어
- Reactor Cooling Water
- Agitator

---

## 분리기

주요 변수:

- Product Sep Temp
- Product Sep Level
- Product Sep Pressure
- Product Sep Underflow
- Separator Cooling Water Outlet Temp
- Liquid Input Separator

관련 제어 변수:

- Separator
- Condenser Coolant

---

## 정제기

주요 변수:

- Stripper Level
- Stripper Pressure
- Stripper Underflow
- Stripper Temp
- Stripper Steam Flow
- Liquid Input Stripper

관련 제어 변수:

- Stripper
- Steam

---

# 14. 전체 공정 및 보조 변수

다음 값은 특정 설비 하나보다 전체 공정 상태와 연결될 수 있다.

- Recycle
- Purge
- Compressor Work
- 제품 성분
- 퍼지 성분
- 공정 유입량

따라서 설비별 AI 설명에서는 특정 장비에 무조건 귀속시키지 않고 **공정 전체 영향 변수**로 별도 표현할 수 있다.

---

# 15. 운전 모드

공식 데이터 설명에 따르면 데이터는 **6개의 서로 다른 운전 모드**를 포함한다.

운전 모드란 고장 종류가 아니라:

```text
공장이 어떤 생산 조건에서 운전되고 있는가
```

를 나타낸다.

즉:

```text
운전 모드 변화 ≠ 열화
```

이다.

이 구분은 향후 데이터 드리프트 감지에서도 매우 중요하다.

정상적인 운전 모드 변경 때문에 센서 분포가 바뀐 것을 무조건 데이터 드리프트 또는 고장으로 판단하면 안 된다.

현재 확보한 8개 CSV가 각 운전 모드와 어떻게 대응하는지는 추가 확인한다.

---

# 16. 열화 시나리오

공식 데이터 설명에서는 총 **6개의 열화 시나리오**가 존재한다고 설명한다.

시나리오에는 다음 조건들의 조합이 포함된다.

- 하나의 설비가 열화
- 두 설비가 동시에 열화
- 세 설비가 동시에 열화
- 값이 증가하는 방향의 열화
- 값이 감소하는 방향의 열화
- 느린 열화
- 중간 속도 열화
- 빠른 열화
- 시간이 지날수록 가속되는 열화
- 여러 설비가 동시에 열화될 때의 상호작용

각 Run에서는 측정 노이즈, 열화 시작 시점, 열화 속도 등의 값에 무작위 차이를 주어 반복 시뮬레이션한다.

따라서 같은 case 안의 100개 `Id`도 완전히 똑같은 데이터가 아니다.

---

# 17. 현재 미확정 사항

다음 사항은 공식 시나리오 표 또는 데이터 생성 문서를 추가 확인한 후 확정한다.

## 17.1 case 파일 매핑

현재 다음 관계가 미확정이다.

```text
case1.csv   = ?
case2.csv   = ?
case3.csv   = ?
case4.csv   = ?
case5.csv   = ?
case5_1.csv = ?
case6.csv   = ?
case7.csv   = ?
```

특히 공식 설명의 "6개 열화 시나리오"와 실제 확보된 "8개 CSV 파일" 사이의 차이를 설명해야 한다.

---

## 17.2 운전 모드 대응

각 파일 또는 각 Run이 6개의 운전 모드 중 어느 조건에 해당하는지 확인해야 한다.

---

## 17.3 설비별 실제 열화 Ground Truth

현재 CSV에는 다음과 같은 직접적인 상태 컬럼이 없다.

```text
reactor_health
separator_health
stripper_health
reactor_rul
separator_rul
stripper_rul
```

따라서 시스템 EOL과 시스템 RUL은 직접 계산할 수 있지만, **설비별 RUL을 그대로 지도학습하기 위해서는 시나리오 메타데이터가 추가로 필요하다.**

---

# 18. 데이터 누수 가능성이 있는 변수

현 단계에서는 다음 변수를 무조건 모델 입력에 넣지 않는다.

## 위험도가 높은 후보

- `Time`
- `Id`
- source file / case 번호
- 계산된 RUL
- life fraction
- EOL 관련 파생값

이 값들은 모델에 정답 또는 수명 진행도를 직접 알려줄 수 있으므로 feature에서 제외한다.

특히:

```text
Time
```

을 입력하면 trajectory가 일정한 수명을 갖는 경우 모델이 센서 상태를 배우지 않고:

```text
시간이 많이 지났음
→ 고장 임박
```

만 학습할 위험이 있다.

---

## 별도 검토 대상

- 조작 변수(msv 계열)
- Liquid Input 계열
- 운전 모드를 직접적으로 식별할 수 있는 변수

이 값들은 반드시 누수라고 할 수는 없지만 모델의 실제 활용 목적을 고려하여 포함 여부를 결정한다.

---

# 19. 모델 입력 기본 원칙

1차 모델에서는 가능한 한 **실제 측정 변수 중심**으로 학습한다.

우선순위:

```text
실제 공정 측정값
↓
성분 분석값
↓
필요 시 조작 변수 추가
```

그리고 다음 실험을 비교한다.

```text
A. 측정값만 사용

B. 측정값 + 조작 변수
```

두 모델의 성능 차이를 비교하여 조작 변수에 모델이 과도하게 의존하는지 확인한다.

---

# 20. 학습/검증 분할 원칙

같은 `Id`의 데이터가 train과 test에 동시에 들어가면 안 된다.

따라서 최소 분할 단위는:

```text
trajectory_key = source_file + Id
```

이다.

기본 평가:

```text
처음 보는 trajectory 예측
```

강화 평가:

```text
하나의 case 전체를 제외하고 학습
→ 해당 case 전체를 test
```

즉 Leave-One-Case-Out 검증을 사용한다.

이 방식은 이미 데이터셋 사전 검증에서 사용했고, TEP가 프로젝트에 사용 가능한 수준의 일반화 성능을 보이는 것을 확인했다.

---

# 21. 현재 데이터 구조 결론

현재까지 확인한 결과 TEP 데이터는 본 프로젝트에 필요한 다음 조건을 만족한다.

- 시간 순서가 존재하는 다변량 시계열
- 완전한 Run-to-Failure trajectory
- 800개의 독립 trajectory
- 3분 단위의 세밀한 시간축
- 시스템 EOL 정의 가능
- 시스템 RUL 계산 가능
- 반응기, 분리기, 정제기의 물리적 측정값 존재
- 여러 설비 간 상호작용 존재
- 여러 운전조건 존재
- 여러 열화 패턴 존재
- Kafka를 이용한 순차 재생 가능
- 디지털트윈에 표시할 물리적 센서명이 존재

따라서 TEP Run-to-Failure 데이터셋을 **TEP Digital Twin 프로젝트의 기본 데이터셋으로 채택한다.**

단, 설비별 RUL 또는 설비별 고장원인을 직접 지도학습하기 전에는 case/열화 시나리오 메타데이터를 먼저 확정해야 한다.

---

# 22. 출처

- Recherche Data Gouv  
  Tennessee Eastman Process Run-to-Failure Dataset  
  DOI: `10.57745/1KATN7`

- Duc An Nguyen, Khanh T. P. Nguyen, Kamal Medjaher  
  *Advancing Explainable Prognostics and Health Management: Insights from New Run-to-Failure Data of the Tennessee Eastman Process*  
  Proceedings of the Institution of Mechanical Engineers, Part O: Journal of Risk and Reliability, 2026.

- Tennessee Eastman Process 기본 변수 구조  
  41 measurement variables / 12 manipulated variables