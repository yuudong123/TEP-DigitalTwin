# 프로젝트 종료 — 2026-10-16

사용자 요청에 따라 합의한 구현·검증 범위를 마무리하고 개발 및 집 PC 상시 운영을 종료한다. 저장소를 삭제하거나 GitHub의 별도 archive 상태로 변경하는 것은 아니다.

## 최종 산출물

- 실제 CSV → Kafka → 추론 → FastAPI → 한글 Web/Unity 공정 관제 연결.
- 단일 화면 관제 UI와 실제 컴파일된 Unity ACK 확인. 최종 화면은 `images/tep-control-room.jpg`에 보존한다.
- Python 112개, 웹 6개 테스트 및 합의한 30분 acceptance 완료. UI PR #34의 dev 병합본 `5bab7df`를 Jenkins #30으로 배포했다.
- 원본 Unity 6.3/URP 빌드·별도 cold restart는 미검증, 운영 정답 없는 자동 재학습은 보류, 21번 요구사항은 미정으로 남긴다. 완료 범위를 확대해 주장하지 않는다.

## Windows 자동시작 해제

- Jenkins: Automatic → Manual, 현재 서비스 중지. 설치와 작업 이력은 보존.
- `TEP-Jenkins-Agent`: 기존 작업 XML 백업 후 예약 작업 등록 제거, 해당 실행기 프로세스 중지.
- Docker Desktop: 현재 사용자의 Run 자동실행 값 제거, `settings-store.json`의 `AutoStart=false`.
- TEP Compose: 서비스 재시작 정책을 `no`로 변경. 종료 조사 당시 현재 Docker 엔진에 등록된 컨테이너는 없었으므로 컨테이너/볼륨/이미지를 삭제하거나 새로 생성하지 않음.
- `com.docker.service`는 이미 Manual/Stopped였으므로 변경하지 않음.
- Tailscale·OpenSSH(sshd)는 Automatic/Running 유지. Ollama·Voicemeeter 등 무관한 자동실행도 변경하지 않음.

변경 전 설정과 예약 작업 XML은 작업 폴더의 `outputs/TEP-autostart-backup-20261016-170909/`에 로컬 보존한다. 개인 설정 백업은 Git에 올리지 않는다. 기존 바탕화면의 수동 시작/종료 파일과 소스·모델·데이터는 유지한다.

이번 종료 설정은 재부팅 전 구성 조회로 확인하며, 실제 PC 재부팅 시험을 수행했다는 뜻은 아니다. 필요하면 Docker Desktop을 직접 켠 뒤 `docker compose up -d`로 수동 실행할 수 있다.
