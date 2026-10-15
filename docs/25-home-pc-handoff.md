# 집 PC 운영 · 인계 (2026-10-15)

집컴 `D:\TEP_DigitalTwin`, 노트북 `C:\TEP-DigitalTwin`.
현재 한글 Unity 공정 개요와 실제 WebGL/API bridge가 구현됐다. 검증 범위는 Unity6.1 격리 호환 빌드이며 원본6.3/URP는 미검증이다.
최신 dev에서 독립 feature branch→PR 규칙을 유지한다. 기존 미커밋 변경을 덮어쓰지 않는다.

## 재개 순서

1. 집컴 켜고 Windows 사용자 로그인. Docker Desktop/TEP-Jenkins-Agent 시작을 확인한다.
   자동 로그인은 설정하지 않았다. 10/15 사용자 재부팅/로그인 후 자동 서비스와 Jenkins의 dev 배포를 관찰했으나, 에이전트는 여전히 사용자 로그인이 필요하다.
2. `http://100.127.7.26:8000/health/ready` 200 확인 후 Web 접속.
3. 실제 Web에서 trajectory 선택·시작. 처음20행은 준비, 센서 전송 종료와 추론 완료는 다르다.
   새 데이터가 없으면 마지막 예측을 STALE로 유지한다. 임의 mock fallback은 없다.
4. Unity는 기존 `Prediction` v1.0 JSON을 envelope 안에 그대로 사용한다.
   latest: `/api/predictions/latest` (선택 `?trajectory_key=case1::1`).
   수신 timestamp header `X-Prediction-Received-At` 사용, 404/timeout/stale UI도 표시한다.
5. Unity 빌드는 `docs/15-unity-digital-twin.md`, 최종 검증 결과는 `docs/26-final-acceptance.md`를 따른다.
   원래 수신 시각과 error/stale/paused 상태를 함께 전달하고 실제 Unity ACK로 적용값을 확인한다.

## 바탕화면 시작·종료

- `C:\Users\User\Desktop\TEP-Start.cmd`: 필요 시 관리자 승격, Docker 준비 → 기존 이미지로 TEP4서비스 기동 → 기존 Jenkins 서비스/agent 시작 → API ready 확인.
- `C:\Users\User\Desktop\TEP-Stop.cmd`: TEP Compose down → Jenkins/TEP agent 중지 → 다른 Docker/WSL 작업이 없을 때만 Desktop 종료와 `wsl --shutdown`.
- 원본은 `deploy/TEP-Start.cmd`, `deploy/TEP-Stop.cmd`, 실제 처리는 같은 폴더의 PowerShell helper를 사용한다.
- Stop은 volume/image/prune/모델/데이터 삭제나 StartupType/예약 작업 비활성화를 하지 않는다. Tailscale·sshd는 중지하지 않는다.
- 다른 프로젝트의 컨테이너, Ubuntu 등 다른 WSL, 또는 인벤토리 확인 실패가 있으면 Docker/WSL 종료를 건너뛴다.
- Start는 빌드/배포 도구가 아니다. 코드 변경 배포는 `deploy/09-manual-deploy.ps1` 또는 dev 병합 후 Jenkins가 수행한다.
- 당일 Stop 뒤 다시 쓰려면 Start를 실행한다. 기존 자동시작 등록은 유지하므로 다음 Windows 시작/사용자 로그인 시 원래 항목이 다시 시작할 수 있다.

## 남은 별도 선택/검증

- 재부팅/로그인 후 기존 서비스 복구는 10/15 관찰했다. 최신 코드의 1시간 연속 및 cold stop/start 최종 결과는26번 문서를 참조한다.
- 17 train 보정 기준은 10/15 운영 `.env`에서 명시적으로 선택했다.
  `DRIFT_CALIBRATION_PATH=models/monitoring/state-calibration-v1.0.0.json`,
  `DRIFT_MIN_TIMESTAMP_HOURS=30`, 120개 window, `RETRAIN_ENABLED=false`다.
  SHA256: `5e99120bdaf854e703c98ff8fca54f59e38544c3d57f818ef912d47713e600b1`.
- 추론은 `INFERENCE_THREADS=1`로 단일 행/SHAP의 전체 코어 점유를 제한한다. 운영 모델 파일은 그대로 v1.0.0이다.
- 18 자동 재학습은 운영 Drift label/데이터가 없어 보류.
- 19·20 평가/승격/적용/rollback은 사용 가능하지만 기존 모델 복사 control로 검증했으며
  새 개선 모델을 학습/운영 적용했다는 뜻은 아니다. 승격은 정확한 보고서 SHA 수동 승인만 허용.
- 21은 요구사항 문서가 없다. 번호만 보고 새 기능을 임의 추가하지 않는다.

비밀번호·SSH private key·Jenkins secret은 업로드/commit하지 않는다.
평가·실증 파일은 `reports/16-integration`, `reports/19-20-lifecycle`, `reports/26-final` 참조.
