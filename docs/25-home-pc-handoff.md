# 집 PC 재개 · Unity 마무리

이번 구현은 Unity 제외. 집컴 `D:\TEP_DigitalTwin`, 노트북 `C:\TEP-DigitalTwin`.
최신 dev에서 독립 feature branch→PR 규칙을 유지한다. 기존 미커밋 변경을 덮어쓰지 않는다.

## 재개 순서

1. 집컴 켜고 Windows 사용자 로그인. Docker Desktop/TEP-Jenkins-Agent 시작을 확인한다.
   자동 로그인은 설정하지 않았다. 종료했다고 자동 부팅/재연결을 검증한 것은 아니다.
2. `http://100.127.7.26:8000/health/ready` 200 확인 후 Web 접속.
3. 실제 Web에서 trajectory 선택·시작. 처음20행은 준비, 센서 전송 종료와 추론 완료는 다르다.
   새 데이터가 없으면 마지막 예측을 STALE로 유지한다. 임의 mock fallback은 없다.
4. Unity는 기존 `Prediction` v1.0 JSON을 그대로 사용한다.
   latest: `/api/predictions/latest` (선택 `?trajectory_key=case1::1`).
   수신 timestamp header `X-Prediction-Received-At` 사용, 404/timeout/stale UI도 표시한다.
5. Unity는 기존 `docs/15-unity-digital-twin.md`에 따라 WebGL/Windows 빌드·bridge·장시간 재생을 검증한다.
   기존 Unity 파일 및 Web `UnityDigitalTwin` component는 이번 작업에서 바꾸지 않았다.

## 남은 별도 선택/검증

- PC reboot 이후 Docker/실행기 복구와 장시간 부하 테스트는 미실증.
- 17 새 train 보정 후보는 코드/평가 완료, 기본 자동 적용하지 않았다.
  명시 선택 시 `DRIFT_CALIBRATION_PATH=models/monitoring/state-calibration-v1.0.0.json`,
  120개 window/min30h/RETRAIN_ENABLED=false 유지. 파일 SHA와 host 모델 경로를 먼저 확인한다.
- 18 자동 재학습은 운영 Drift label/데이터가 없어 보류.
- 19·20 평가/승격/적용/rollback은 사용 가능하지만 기존 모델 복사 control로 검증했으며
  새 개선 모델을 학습/운영 적용했다는 뜻은 아니다. 승격은 정확한 보고서 SHA 수동 승인만 허용.
- 21은 요구사항 문서가 없다. 번호만 보고 새 기능을 임의 추가하지 않는다.

비밀번호·SSH private key·Jenkins secret은 업로드/commit하지 않는다.
평가·실증 파일은 `reports/16-integration`, `reports/19-20-lifecycle` 참조.
