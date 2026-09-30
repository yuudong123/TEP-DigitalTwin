# 운전상태 기준 후보 검증 — 2026-09-30

운영 Data Drift 라벨은 없으므로 운전상태·열화 변화 신호만 평가한다.
자동 재학습은 비활성화하고 후보를 기본 운영 설정에 자동 적용하지 않았다.

## 기준 생성

train만 사용: case당 70개 trajectory × 30~60시간의 120개 비중첩 창 5개,
총 2,100개 창. case·feature별 PSI/KS 경험적 99백분위(higher), 최소값 0.25/0.15.
두 통계량이 모두 임계값을 초과해야 Feature 변화로 기록한다. p/q-value는 판정에서 제외한다.
검증 전 고정한 기준으로 validation과 test를 평가했고 결과에 맞춰 재조정하지 않았다.

모델 파일: `models/monitoring/state-calibration-v1.0.0.json`.
SHA-256: `5e99120bdaf854e703c98ff8fca54f59e38544c3d57f818ef912d47713e600b1`.
동일 생성물: `train-calibration-2026-09-30.json`.

## 구간별 비교

| 기준 / split | 안정 30~60h 창 경보 | 70h 이후 창 경보 | 경보 trajectory |
|---|---:|---:|---:|
| 기존 / validation | 434/450 (96.44%) | 883/883 (100%) | 기존 구간별 보고서 참조 |
| 후보 / validation | 0/450 (0%) | 572/883 (64.78%) | 89/90 |
| 후보 / test | 0/450 (0%) | 567/885 (64.07%) | 87/90 |

완성된 120개 창을 6시간 가상 주기로 평가했다. 안정·70h 이후는 창 전체가 해당
구간에 포함되어야 하며 경계 창은 별도 전환 구간이다. 경보는 DRIFT/CONFIRMED_DRIFT.
정확한 고장 시작 라벨이 없으므로 위 수치는 정확도/재현율이 아니다.
안정 창의 관측 경보 0은 미래 오탐 0을 보장하지 않으며 창 간 상관도 존재한다.
기존 전체 수명 평가의 99.56%와 안정 구간 경보율은 서로 다른 지표다.

원본: `calibrated-validation-2026-09-30.json`, `calibrated-test-2026-09-30.json`.

## 실제 runtime 및 안전성

- 집컴 전체 Python 테스트: 최종 64 passed (설정의 NaN/무한대·초기 구간 혼입 방지 포함).
- 기존 영구 볼륨 `tep-kafka-data`를 사용하는 Kafka healthy 확인 후 격리 검증.
- UUID 전용 topic/container로 실제 센서 242개를 처리하고 Event 242개 수신.
- 마지막 정상 상태 NORMAL, 인위적으로 크게 이동한 입력 CONFIRMED_DRIFT.
- schema 오류 0, 자동 재학습 요청 0. 원본 증적: `calibrated-smoke-2026-09-30.json`.
- smoke의 검사 주기는 0초로 운영 기본 60초 및 장시간 성능을 입증하지 않는다.
- 발행 callback 성공 확인 후 offset commit. timeout/terminal failure는 commit 없이 종료.
- at-least-once이므로 중복 가능. 메모리 창/연속 상태는 재시작 시 다시 준비한다.

## 추가 실제 복구·주기 검증

- `timing-smoke-2026-09-30.json`: 실제 60초 설정에서 연속 판정 사이 61.016초씩
  두 번 관측, 242개 Event 및 최종 CONFIRMED_DRIFT. 약 2분 양성 대조이며 장시간 부하 검증은 아니다.
- `recovery-smoke-2026-09-30.json`: UUID 출력 topic에만 크기 제한을 넣어 실제 발행 실패 유도.
  실패 입력 offset 242에서 commit 위치도 242로 유지(다음 읽을 위치), Monitor 종료 확인.
  제한 복원·재시작 후 sequence 122를 재처리하고 INSUFFICIENT_DATA로 안전하게 재준비.
  추가 입력 후 CONFIRMED_DRIFT 회복, 총 364개 Event. 운영 topic/volume은 변경하지 않았다.
- `recovery-identified-smoke-2026-09-30.json`: 발행 실패·재시작에 더해 중복 sequence,
  sequence 누락·역전 입력으로 창 초기화와 양성 대조군 회복 확인. 총 488개 Event,
  재학습 요청 0, 모든 초기 판정 Event의 calibration_sha256이 후보 파일과 일치.
  Event의 선택 해시 필드로 기존 규칙과 후보를 구분하며 필수 필드/상태는 유지했다.

## 남은 승인·검증 (갱신)

1. 후보 기준 운영 승인 및 명시적 설정/재배포.
2. 실제 60초 검사 주기 장시간 재생 및 수신 지연 검증.
3. Kafka broker 재시작 및 장시간 중복·재처리 검증. Monitor 발행 실패·재시작 복구는 위 격리 검증 완료.

17번은 부분 완료다. 자동 재학습·모델 승격·hot apply는 이 검증의 범위가 아니다.
