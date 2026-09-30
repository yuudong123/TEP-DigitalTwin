# Jenkins · 비 Unity 통합 acceptance

기준 2026-09-30. dev 병합 후 기존 H/2 Poll SCM 자동 배포를 사용한다.

- [x] PR #27·#28·#29·#30 dev 병합, 최신 dev 기반 독립 feature branch 규칙 준수
- [x] Jenkins #25/#26 실제 새 dev 감지·SUCCESS 및 배포 JSON 보관
- [x] Python compileall/pip check/pytest gate (최신89개 테스트)
- [x] Web npm ci/test/lint/build, API와 동일 origin 서비스
- [x] Kafka healthy/영구 볼륨, API healthy, Inference/Monitor 실행 및 재학습 false
- [x] 실제 CSV 전체2,929개 → Prediction2,909개, 시간/개수/key/schema
- [x] 동기 `/v1/predict`와 첫 Kafka Prediction JSON 일치
- [x] 실제 replay pause/resume/충돌409, 없는 raw/없는 예측404 및 stale/backlog 표시
- [x] 실제 API restart 후 SQLite snapshot/수신 시각 유지
- [x] 실제 Inference 발행 거부 시 offset미commit, restart 후 21행 재준비·복구
- [x] 실제 validation 전체238,872행·90 trajectories, 동등 후보 통과·열화 후보 거부
- [x] 실제 Kafka/API control version 적용·손상 pointer 거부·rollback (운영 모델 미변경)
- [ ] Unity 실제 API/WebGL 연결·오류 UI·Windows build (사용자 집 PC 작업)
- [ ] 운영 Monitor 후보 보정 기준 명시 선택/승인 (기본 자동 적용 아님)
- [ ] 집컴 재부팅→로그인→Docker/실행기 복구 실증
- [ ] 장시간 부하·운영 장애 endurance

기동 성공과 기능 acceptance, 컨테이너 restart와 PC reboot는 서로 다른 증거다.
실제 결과: `reports/16-integration`, `reports/19-20-lifecycle`, `reports/17-drift`, `reports/08-operations`.
