# TEP-DigitalTwin 작업 진행표

기준일: 2026-10-16. **프로젝트 종료** — 합의한 구현·30분 검증 범위를 완료했다. 관제 UI PR #34는 dev 병합 및 Jenkins #30 배포 완료다. 종료 시점의 자동시작 해제와 보존 항목은 `28-project-closeout.md`를 따른다. 아래 미검증·보류 항목은 추가 작업 약속이 아닌 종료 시점의 경계다.
구현 증거와 실제 실행 증거를 구분한다. Unity는 6.1 격리 호환 빌드를 실제 검증했으며 원본 6.3/URP 검증과 구분한다.
✅ 정의된 구현/acceptance 완료 · 🟡 별도 검증/외부 선택 남음 · 보류: 현재 데이터·요구사항으로 실행 불가.

| 번호 | 상태 | 완료된 범위 | 남은 범위 |
|---:|---|---|---|
| 01–07 | ✅ | 기획·데이터·분할·모델·구조, v1.0.0 4모델·728 feature | 새 운영 학습은 별도 |
| 08 | 🟡 | 전체4서비스·Kafka 영구 저장, 10/15 사용자 재부팅/로그인 후 자동 서비스·Jenkins 배포 관찰 | 새 코드 cold stop/start 미실행 |
| 09 | ✅ | workspace/runtime 분리 배포·사전 gate·보고서, API 포함 전체 배포 | reboot은08 별도 |
| 10 | ✅ | dev H/2 Poll SCM·사용자 실행기, #25/#26 SUCCESS·보고서 archive | reboot 실행기 복구는08 별도 |
| 11 | ✅ | 실제 CSV replay·56 sensor schema·ACK·선택/시작/중지/제어 | 외부 같은 key 병렬 replay 금지 |
| 12 | ✅ | 실제2,929→2,909 Prediction, feature/SHAP 계약·ACK후commit·누락 재준비·발행 거부 복구 | 장시간 부하는22 별도 |
| 13 | ✅ | Live latest/list·동기 predict·replay·monitoring·health, SQLite durable cache | 인터넷 인증 서비스는 범위 밖 |
| 14 | ✅ | 실제 API Web·replay 제어·error/stale/backlog·Monitor 표시 | Unity와 혼동하지 않음 |
| 15 | ✅ 호환 빌드 | 한글 3D 공정 개요·실제 WebGL/API ACK·pause/error/receipt 보존·Windows 캡처 | 원본 Unity 6.3/URP 동일 버전 검증 별도 |
| 16 | ✅ 연결 | 실제 CSV→Kafka→Inference→API→Web 및 컴파일된 Unity 예측값 일치 | 장시간/복구는22·08 별도 |
| 17 | ✅ 합의 범위 | train 보정 기준 운영 선택·SHA 확인, 30분 이상 재생·보정 판정27건·자동 재학습 비활성 | 운영 label을 이용한 개선 모델 학습은18 별도 |
| 18 | 보류 | 자동 재학습=false 유지 | 운영 Drift label/데이터 및 별도 범위 승인 필요 |
| 19 | ✅ 계약/실증 | 실제 validation 전체238,872행·90 trajectories 평가, 동등 통과·악화 거부·승인 SHA 승격 | 실제 새 개선 후보 학습/운영 승격은18과 별도 |
| 20 | ✅ 계약/실증 | hash/원자 pointer·live hot application·실패시 직전 유지·restart fallback·rollback | 실제 운영 모델은 v1.0.0 유지 |
| 21 | 범위 미정 | 기존 문서에 번호/담당만 존재, 요구사항 미정임을 명시 | 임의 기능을 만들지 않음. 요구사항 확인 필요 |
| 22 | ✅ 30분 기준 | Python112개·Web6개·lint/build, 실제 WebGL 정상/거부·resize, 2054.4초/예측19,288건·오류0 | cold stop/start는08 별도·브라우저 최종 전체 집계 없음 |
| 23 | ✅ 합의 범위 | 사용자 합의한30분 연속 기준 완료·실제 Unity 연결 확인 | 병합/배포 상태는 PR과 Jenkins 기록 확인, 원본6.3/복구 경계는08·15 |
| 24 | ✅ 현재분 | API/lifecycle/운영 문서·본 표·원본 JSON/화면 증거 동기화 | 남은 실제 결과 발생 시 갱신 |

## 바로 볼 곳

- 기존 운영 주소: `http://100.127.7.26:8000/` (프로젝트 종료 후 자동 기동하지 않음. 수동으로 서비스를 실행할 때만 사용).
- API 계약/사설 네트워크 범위: `13-live-api.md`.
- 수동 승인·hot application·rollback: `19-20-model-lifecycle.md`.
- 현재 집 PC 운영과 검증 경계: `25-home-pc-handoff.md`, `26-final-acceptance.md`.
- 실제 증거: `reports/16-integration`, `reports/19-20-lifecycle`, `reports/17-drift`, `reports/08-operations`.

TEP의 “Drift” 클래스/topic은 호환 유지하되 실제 의미는 운전상태·열화 변화다.
99.56%는 과거 lifetime/global 판정 비율이지 안정 구간 오탐률이 아니다.
운영 label이 없는 상황에서 자동 재학습이나 새 개선 모델 운영 승격을 완료라고 하지 않는다.

10/15 오전 검증은 사용자의 즉시 종료 요청으로 665.2초에서 중단됐다. 예측6,322건·오류0은 중간 결과이지 1시간 통과가 아니다.
10/15 저녁도 사용자가 검증 중단 후 업로드/병합을 요청했다. 마지막 저장은2054.4초·예측19,288건·보정 판정27건·오류0이다.
이후 사용자가 완료 기준을30분으로 변경했다. 실제2054.4초가1800초를 넘으므로 `acceptance-30min-2026-10-15.json`에30분 기준 완료를 기록했다.
원래 실행 기록의 `passed=false`는 최초 계획한1시간을 완료하지 못했다는 의미로 그대로 보존하며, 1시간 완료나 오류 발생으로 바꾸지 않는다.
이번 작업 후 자동 PC 종료는 예약하지 않는다.
