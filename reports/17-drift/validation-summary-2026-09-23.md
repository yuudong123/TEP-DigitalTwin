# TEP 운전상태·열화 변화 기준 보정 결과

> 2026-09-30 정정: 아래 수치는 30시간 이후 **전체 수명**을 평가한 기록이다.
> 기존 평가기는 60시간 종료 조건이 없어 열화 이후도 포함했다. 99.56%를 정상성
> proxy/오탐률로 설명하거나 이 수치만으로 과민반응을 확정한 결론은 철회한다.
> 구간별 재평가는 `validation-phases-2026-09-30.md`를 따른다.

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
이 합산 평균 비교만으로 case별 분포나 개별 창의 경보 원인을 설명할 수 없다.
정상 구간에 한정한 경보율과 열화 이후 경보율을 먼저 분리해야 한다.

## 판정

전체 수명에서 경보가 많이 발생했다는 사실만 확인된다. 열화 구간의 기대되는 변화와
안정 구간의 경보를 구분하지 않아 오탐 여부는 이 보고서로 판단할 수 없다.
`RETRAIN_ENABLED=false`를 유지하고 구간별 평가 후 기준 변경 여부를 결정한다.
