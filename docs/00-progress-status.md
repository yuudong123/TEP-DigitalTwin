# TEP-DigitalTwin 작업 진행표

기준일: 2026-09-30. PR #27·#28·#29·#30은 dev 병합 완료.
구현 증거와 실제 실행 증거를 구분한다. Unity는 사용자 집 PC 작업으로 제외했다.
✅ 정의된 구현/acceptance 완료 · 🟡 별도 검증/외부 선택 남음 · 보류: 현재 데이터·요구사항으로 실행 불가.

| 번호 | 상태 | 완료된 범위 | 남은 범위 |
|---:|---|---|---|
| 01–07 | ✅ | 기획·데이터·분할·모델·구조, v1.0.0 4모델·728 feature | 새 운영 학습은 별도 |
| 08 | 🟡 | 전체4서비스 기동·Kafka 영구 저장·격리 broker 재생성 보존 실증 | PC reboot/장시간 검증 |
| 09 | ✅ | workspace/runtime 분리 배포·사전 gate·보고서, API 포함 전체 배포 | reboot은08 별도 |
| 10 | ✅ | dev H/2 Poll SCM·사용자 실행기, #25/#26 SUCCESS·보고서 archive | reboot 실행기 복구는08 별도 |
| 11 | ✅ | 실제 CSV replay·56 sensor schema·ACK·선택/시작/중지/제어 | 외부 같은 key 병렬 replay 금지 |
| 12 | ✅ | 실제2,929→2,909 Prediction, feature/SHAP 계약·ACK후commit·누락 재준비·발행 거부 복구 | 장시간 부하는22 별도 |
| 13 | ✅ | Live latest/list·동기 predict·replay·monitoring·health, SQLite durable cache | 인터넷 인증 서비스는 범위 밖 |
| 14 | ✅ | 실제 API Web·replay 제어·error/stale/backlog·Monitor 표시 | Unity와 혼동하지 않음 |
| 15 | 🟡 사용자 | 기존 prefab/mock/bridge 존재. 이번에는 변경 안 함 | 사용자 집 PC Unity build·실제 연결 |
| 16 | 🟡 | 비 Unity 실제 CSV→Kafka→Inference→API→Web 및 Jenkins 배포 | Unity 포함 최종 acceptance |
| 17 | 🟡 | train 보정 후보·validation/test 안정 각0/450·60초 판정·offset/중복/복구 증거 | 운영 후보 기준 승인/선택·장시간 |
| 18 | 보류 | 자동 재학습=false 유지 | 운영 Drift label/데이터 및 별도 범위 승인 필요 |
| 19 | ✅ 계약/실증 | 실제 validation 전체238,872행·90 trajectories 평가, 동등 통과·악화 거부·승인 SHA 승격 | 실제 새 개선 후보 학습/운영 승격은18과 별도 |
| 20 | ✅ 계약/실증 | hash/원자 pointer·live hot application·실패시 직전 유지·restart fallback·rollback | 실제 운영 모델은 v1.0.0 유지 |
| 21 | 범위 미정 | 기존 문서에 번호/담당만 존재, 요구사항 미정임을 명시 | 임의 기능을 만들지 않음. 요구사항 확인 필요 |
| 22 | 🟡 | 최신 Python89개, Web3개·lint/build, 실제 전달 실패·재시작·모델 거부/복구 | 장시간 부하·PC reboot |
| 23 | 🟡 | 비 Unity 정의된 acceptance 통과·Jenkins 배포 | Unity 및 장시간/재부팅 포함 최종 종료 판정 |
| 24 | ✅ 현재분 | API/lifecycle/운영 문서·본 표·원본 JSON/화면 증거 동기화 | 남은 실제 결과 발생 시 갱신 |

## 바로 볼 곳

- 실제 주소: `http://100.127.7.26:8000/` (집컴 켜짐·Docker/실행기 로그인 조건).
- API 계약/사설 네트워크 범위: `13-live-api.md`.
- 수동 승인·hot application·rollback: `19-20-model-lifecycle.md`.
- 집 PC Unity 마무리 및 운영 보류: `25-home-pc-handoff.md`.
- 실제 증거: `reports/16-integration`, `reports/19-20-lifecycle`, `reports/17-drift`, `reports/08-operations`.

TEP의 “Drift” 클래스/topic은 호환 유지하되 실제 의미는 운전상태·열화 변화다.
99.56%는 과거 lifetime/global 판정 비율이지 안정 구간 오탐률이 아니다.
운영 label이 없는 상황에서 자동 재학습이나 새 개선 모델 운영 승격을 완료라고 하지 않는다.

사용자는 검증/저장 완료 후 집컴과 노트북 즉시 종료를 승인했다. 종료는 reboot 복구 검증이 아니다.
