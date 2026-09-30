# Docker 개발환경

## 1. 목적

Kafka, API, inference, monitoring 서비스를 동일한 Docker Compose
네트워크에서 실행할 수 있는 개발환경의 공통 규칙을 정의한다.

## 2. 서비스 구성

| 서비스 | 역할 | 컨테이너 이름 |
| --- | --- | --- |
| `kafka` | 센서·예측·드리프트 이벤트 메시지 브로커 | `tep-kafka` |
| `api` | 외부 조회용 FastAPI 서비스 | `tep-api` |
| `inference` | Kafka 센서 메시지 기반 실시간 추론 | `tep-inference` |
| `monitor` | 운전상태·열화 변화 감시 | `tep-monitor` |

모든 서비스는 `tep-network` bridge 네트워크를 사용한다. 애플리케이션
컨테이너는 Kafka healthcheck가 성공한 뒤에 시작한다.

## 3. 환경변수 관리

- 저장소에는 공유 가능한 기본값만 `.env.example`에 둔다.
- 실제 실행값은 Git에서 제외되는 루트 `.env`에 둔다.
- `compose.yaml`은 각 애플리케이션 서비스에 `env_file: .env`를 적용한다.
- 컨테이너 내부 Kafka 주소는 서비스 DNS를 사용해 `kafka:19092`로 덮어쓴다.
- Kafka는 외부 볼륨 `tep-kafka-data`를 사용한다. 최초 이전·준비 절차는
  `08-kafka-persistence.md`를 따른다.

첫 실행 전에는 다음과 같이 설정 파일을 만든다.

```powershell
Copy-Item .env.example .env
```

## 4. 모델 공유 방식

개발환경에서는 호스트의 `./models`를 세 애플리케이션 컨테이너에
`/app/models`로 읽기 전용 마운트한다.

- API, inference, monitor가 같은 production 모델 버전을 읽는다.
- 호스트에서 model version을 바꿔도 컨테이너 이미지 재빌드 없이 파일이
  반영된다. 실제 hot reload 정책은 20번 작업에서 결정한다.
- 읽기 전용 마운트로 서비스가 production 모델을 덮어쓰지 못하게 한다.

Dockerfile의 `COPY models`는 Compose 없이 이미지를 단독 실행할 때를 위한
기본 포함본으로 유지한다. Compose 실행 시에는 공유 마운트가 이를 대체한다.

## 5. 로그 구조와 확인 방법

호스트의 `./logs`를 각 애플리케이션 컨테이너의 `/app/logs`에 마운트한다.
공통 logger가 파일 로그를 만들면 호스트에서도 바로 확인할 수 있다.

컨테이너 표준 출력 로그는 다음으로 확인한다.

```powershell
docker compose logs --follow kafka
docker compose logs --follow api
docker compose logs --follow inference
docker compose logs --follow monitor
```

파일 로그는 `logs/`에서 서비스별 파일명으로 확인한다. 로그 파일 자체는
Git에 포함하지 않고, 빈 디렉터리 유지를 위한 `.gitkeep`만 포함한다.

## 6. 현재 검증 상태

`docker compose config`와 `docker compose up --build -d`로 Compose 문법,
환경변수·볼륨 해석, 이미지 빌드 및 기동을 확인했다.

- `tep-kafka`는 healthcheck를 통과해 `healthy` 상태로 실행됐다.
- API, inference, monitor 이미지는 정상 빌드됐다.
- 초기에는 미구현 실행 모듈로 재시작했으나, 2026-09-30 현재 모두 구현되었다.
  Jenkins #25/#26에서 Kafka/API/Inference/Monitor 전체 정상 기동·재시작 증가 없음 확인.

전체 기동에 필요한 다음 구현은 완료했다.

1. Docker Desktop 또는 Docker Engine 실행
2. 12번 inference 서비스 구현
3. 13번 FastAPI 서비스 구현
4. 17번 monitor 서비스 구현 또는 monitor 임시 실행 정책 결정

따라서 최소 시스템 실행 기준은 통과했다. 기동과 도메인 acceptance는 별도로 검증한다.
API 이미지는 배포 gate가 검사·빌드한 `web/dist`를 포함하고 실제 raw CSV를 읽기 전용 mount한다.
집컴 재부팅/장시간 테스트는 아직 별도 항목이며 자동 로그인/재부팅을 무단 수행하지 않는다.
