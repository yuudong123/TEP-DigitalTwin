# TEP 운전상태·열화 변화 기준 보정 결과

실행 시각: 2026-09-23 15:54 KST  
대상: `validation` split, case1~case6, trajectory 90개  
기준: `drift-reference-v1.0.0.json` (SHA-256 `954f22acf9e2a08db7a4f5860b120a91415ec5e22db948cb03a89cf281d2c5b8`)  
판정 창: 120 samples, 최소 20 samples, 기준 시작 30시간  
오프라인 계산 주기: 6시간 가상 주기(원본 행 간격 180초). 운영 Data Drift 오탐률 확정용이 아닌 기준 보정용.

| 지표 | 결과 |
|---|---:|
| 평가 창 | 1,579 |
| Drift/Confirmed Drift 창 | 1,572 |
| Alert window rate | 99.56% |
| 최대 Drift feature 비율 | 98.08% |
| CAUTION 창 | 7 |

상위 Feature alert rate:

| Feature | Alert rate |
|---|---:|
| Component E to Product | 94.68% |
| Component H to Product | 89.55% |
| Component F to Product | 89.23% |
| Component D to Product | 88.41% |
| Separator | 86.13% |

추가 점검으로 30~60시간 전체 행을 train/validation으로 합산 비교했을 때 상위
Feature의 평균은 거의 일치했다(예: `Component E to Product` train 0.679775,
validation 0.679457; `Separator` train 39.486257, validation 39.485116).
따라서 현재 결과는 단순한 split 전체 평균 이동보다는, pooled train 기준 분포와
단일 trajectory 6시간 창의 분포를 비교하는 현재 방식에서 발생하는 구조적 오탐
가능성을 우선 조사해야 한다.

## 판정

현재 pooled train 기준과 단일 trajectory 창 조합은 변화 신호를 과도하게 발생시킨다.
따라서 이 결과를 운영 Data Drift 통과나 재학습 근거로 사용하지 않는다.
`RETRAIN_ENABLED=false`를 기본으로 유지하고, trajectory 간 자연 변동을 반영한
변화 신호 기준을 재설계해야 한다.
