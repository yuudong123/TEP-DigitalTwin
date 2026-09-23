# TEP-DigitalTwin 작업 진행표

기준일: 2026-09-23  
기준 브랜치: `dev` (`0380467`, origin과 동기화)  
최근 병합: PR #24(실시간 추론), PR #25(Kafka 영구 저장), PR #26(Drift runtime)

상태 표기: ✅ 완료 · 🟡 부분 완료/검증 필요 · ⬜ 미착수

| 번호 | 담당 | 현재 상태 | 완료된 범위 | 아직 필요한 작업 |
|---:|---|---|---|---|
| 01 | 공통 | ✅ | 프로젝트 범위·역할·일정 문서화 | 문서 최신화만 필요 |
| 02 | 공통 | ✅ | TEP 데이터 구조·전처리 기준 정리 | 없음 |
| 03 | 공통 | ✅ | train/validation/test 및 trajectory 분할 기준 확정 | 없음 |
| 04 | 공통 | ✅ | baseline 모델과 비교 기준 산출 | 없음 |
| 05 | 공통 | ✅ | 728개 temporal feature 생성·검증 | 없음 |
| 06 | 공통 | ✅ | Production 4종 XGBoost 모델 v1.0.0 산출 | 운영 재학습 모델은 별도 |
| 07 | 공통 | ✅ | 저장소 구조·실행 문서 정리 | 없음 |
| 08 | B | 🟡 | Docker Compose, Kafka/Inference/Monitor 실행 및 Kafka 영구 볼륨 구성 | 재부팅 복구·전체 스택 가동 검증 |
| 09 | B | 🟡 | 수동 배포 스크립트·runtime 보고서 구현 | 실제 운영 배포 성공 증적 정리 |
| 10 | B | 🟡 | Jenkins dev 감시·자동 배포 연결 | API 포함 전체 체인 성공 검증 |
| 11 | A | 🟡 | Producer/Consumer·Schema·Kafka replay 구현, 실제 2,929건 replay | 실패·재시도·중복/순서 보장 검증 |
| 12 | A | 🟡 | 실시간 추론 병합, 2,929건 중 2,909건 예측 확인 | reliable delivery·API 연동 |
| 13 | A | ⬜ | FastAPI 구현 | `/v1/predict` 및 운영 API 구현·검증 |
| 14 | C | 🟡 | React/Vite 대시보드·mock stream·API client | 실제 API 연결·라이브 검증 |
| 15 | C | 🟡 | Unity prefab/mock·WebGL bridge·Prediction 모델 | API 연결·오류 UI·자동/장시간/Windows 검증 |
| 16 | A/B/C | 🟡 | 서비스 간 일부 계약·Jenkins checklist | API→Inference→Kafka→Web/Unity 전체 통합 |
| 17 | B | 🟡 | TEP 운전상태·열화 변화 모니터링, PSI/KS/BH, trajectory window, runtime 연결 | trajectory 자연 변동을 반영한 기준 재설계·운영 Data Drift 분리 |
| 18 | C | 🟡 | 자동 재학습 연계 보류 결정 | 운영 Drift 데이터·label 확보 후 범위 재확정 |
| 19 | C | ⬜ | candidate 평가·승격 미구현 | 평가 기준·승격/거부·rollback 계약 |
| 20 | B | ⬜ | Production 모델 hot application/rollback 미구현 | 19번 계약 이후 적용 |
| 21 | B | ⬜ | 상세 작업 문서 미확정 | 요구사항 확인 후 범위 확정 |
| 22 | 공통 | 🟡 | 단위·고정 데이터 테스트 일부 통과 | 장애 복구·통합 테스트·운영 시나리오 |
| 23 | 공통 | ⬜ | 최종 통합 미착수 | 전체 live chain 및 acceptance |
| 24 | 공통 | 🟡 | 핵심 설계/운영 문서 존재 | 상태·증적을 본 표와 동기화 |

## 이번 작업 순서

1. 17번 안정 기준과 trajectory 자연 변동을 재현 가능한 오프라인 평가로 측정한다.
2. 평가 중 드러난 안전성 결함(trajectory 상태 격리, KS 동일표본 경계 등)을 테스트와 함께 보완한다.
3. 결과와 한계를 `docs/17-drift-detection.md`에 반영한다.
4. 변경을 `feat/drift-validation` 작업 단위로 커밋하고 PR 대상으로 정리한다.

17번 평가는 “운영 Data Drift 오탐률 통과”를 미리 가정하지 않는다. 현재 TEP에는
별도 운영 Drift label이 없으므로 재학습 Trigger는 기본 비활성화한다.
