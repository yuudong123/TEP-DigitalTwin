# 공정 화면 · 집 PC 운영 최종 검증

기준: 2026-10-15, Windows `tep-server`, `D:\TEP_DigitalTwin`.
이 문서는 새 증거에 따라 갱신한다. RUNNING이나 중간 snapshot은 통과가 아니다.

## 구현 범위

- 한글 Unity 공정 개요: 반응/응축/분리/정제/압축·재순환, 전체 상태·RUL·위험도·SHAP.
- 실제 API receipt/source/connection envelope와 Unity ACK. Mock/기록/실시간 구분.
- 추론 스레드1, 기존 v1.0.0 모델 유지, train 보정 기준 명시 적용, 자동 재학습=false.
- 안전한 바탕화면 시작/종료와 Docker/WSL 범위 보호. 설정 비활성화·데이터 삭제 없음.
- 재현 가능한 Unity→Web→Docker 배포 gate와 실제 체인/브라우저/복구 검증 도구.

## 현재 증거

| 검증 | 결과/원본 |
|---|---|
| Python | 112개 통과, `tests/`; 알려진 Starlette/httpx deprecation warning1개 |
| Web | 6개·lint·TypeScript/production build 통과 |
| Unity build | 6000.1.10f1, 격리 built-in renderer, JSON bridge 정상/거부 계약 검사 통과 |
| 기존 실제 전체 체인 | 센서2,929 → 예측2,909, 순서/직접예측 일치·재생 pause/resume/conflict, `reports/26-final/full-chain-2026-10-15.json` |
| 기존 실제 WebGL | 95초, API/Unity 일치8회, pause/error/복구 통과, `reports/26-final/webgl-smoke-2026-10-15.json` |
| 실제 WebGL 거부/resize | 숫자 상태·범위 밖 위험도·receipt 누락 거부, 1280/1920 canvas 크기 일치, `reports/26-final/webgl-contracts-2026-10-15.json` |
| 새 체크아웃 검증 | 로컬 commit7df947e를 새로 clone하여 Unity/Web 빌드와 Python105개 통과; 당시 gate 보고서는 `reports/26-final/clean-checkout-validation.json`. 이후 추가된7개는 컨테이너 교체/재시작 검증 도구 테스트 |
| 오전 중단된 부하 | 665.2초·예측6,322·오류0, **1시간 통과 아님** |
| 저녁 1시간 backend | 진행 중, `reports/26-final/soak-resumed-2026-10-15.progress.json` |
| 저녁 1시간 WebGL | 진행 중, 완료 시 `reports/26-final/webgl-soak-resumed-2026-10-15.json` |
| cold stop/start | 장시간 검증 뒤 실행 예정 |
| Windows 기존 자동 시작 | 18:05 재부팅 후 로그인, Jenkins/Tailscale/sshd Auto+Running, Docker 및 기존 agent/Jenkins dev 배포 관찰. 기준 snapshot: `reports/26-final/resume-baseline-2026-10-15.json` |

## 재실행

장시간 검증 중에는 다른 replay나 배포를 시작하지 않는다. 자동 배포 충돌을 피하기 위해
현재 Jenkins 서비스와 TEP agent만 잠시 중지했으며 자동시작 설정은 유지했다.

```powershell
Set-Location D:\TEP_DigitalTwin
powershell.exe -NoProfile -ExecutionPolicy Bypass -File deploy\09-manual-deploy.ps1
.\.venv\Scripts\python.exe -m deploy.verify_soak --seconds 3600 --interval .1 --output reports/26-final/soak-resumed-2026-10-15.json
# 위 replay가 실행 중인 동안 별도 터미널에서:
Set-Location web
node verify-webgl.mjs http://127.0.0.1:8000 3600 ../reports/26-final/webgl-soak-resumed-2026-10-15.json ../reports/26-final/unity-live.png
```

실제 test split의 case1–6 CSV를 반복 재생한다. 센서/예측 순서·중복·누락과 API readiness,
컨테이너 상태/재시작, 모니터 보정 SHA/자동 재학습=false를 검사한다.
브라우저는 실제 컴파일된 WebGL ACK와 API 예측/receipt를 비교한다.
추가 거부/resize 검증은 테스트 브라우저에서 loader factory를 감싸 공개 Unity instance만 캡처한다.
WASM/data와 API 응답은 실제 산출물/서비스이며 mock으로 대체하지 않는다.
브라우저 `js_heap_bytes`는 JS heap 측정이며 Unity WASM/GPU/전체 프로세스 메모리의 증거가 아니다.

Cold stop/start에서는 먼저 replay를 완료/중지하고 backlog를 비운다.

```powershell
.\.venv\Scripts\python.exe -m deploy.verify_recovery --mode capture --state reports/26-final/before-cold-start.json
# 관리자 권한으로 바탕화면 TEP-Stop.cmd, 이어서 TEP-Start.cmd 실행
.\.venv\Scripts\python.exe -m deploy.verify_recovery --mode verify --state reports/26-final/before-cold-start.json --output reports/26-final/cold-recovery.json
```

예측 전체 snapshot와 원래 receipt가 같고 Kafka high-water가 감소하지 않는지 확인한다.
이는 제어된 Desktop/WSL/컨테이너 재기동 증거이며 새로운 Windows 재부팅 시험이라고 하지 않는다.

## 남는 경계

- 원본 Unity6000.3.24f1/URP 동일 버전 빌드는 미검증이다. 설치 시도가 승인 정책에 막혀 설치된6.1을 명시적으로 사용했다. 원본 프로젝트 버전/패키지는 그대로 보존했다.
- 3D 형상은 기획 흐름을 표현하는 개요이지 물리 시뮬레이터가 아니다. 상태 밴드는 개별 설비 고장 위치를 뜻하지 않는다.
- 운영 Drift label 부재로 자동 재학습은 보류다. 새로운 개선 모델을 학습/승격한 것이 아니다.
- 21번은 요구사항 미정이므로 임의 기능으로 채우지 않았다.
- GitHub dev 병합/Jenkins 최종 배포 결과는 완료 후 따로 기록한다. feature branch를 로컬에 저장한 것만으로 원격 배포 완료라고 하지 않는다.
