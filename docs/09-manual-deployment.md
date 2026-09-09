# 개발서버 수동 배포

## 1. 목적

Oracle Cloud 개발서버에 프로젝트를 수동 배포하고, Docker Compose 기반
서비스를 운영할 수 있는 표준 절차를 정의한다. 이 문서는 3인 팀이 같은
서버 절차와 환경변수 규칙을 사용하도록 하는 운영 기준이다.

## 2. 배포 전제조건

서버 관리자 또는 배포 담당자가 다음을 준비한다.

- Oracle Cloud 개발서버 접근 권한
- Git 및 Docker Engine, Docker Compose v2
- Docker daemon을 실행하고 접근할 수 있는 배포 사용자
- GitHub 저장소 읽기 권한
- 서버 전용 `.env` 값

민감한 값과 서버별 주소는 저장소에 넣지 않는다. `.env.example`을 복사한
뒤 서버 환경에 맞게 `.env`를 작성한다.

```bash
cp .env.example .env
chmod 600 .env
```

## 3. 최초 배포

서버의 원하는 배포 경로에서 저장소를 clone한다.

```bash
git clone https://github.com/yuudong123/TEP-DigitalTwin.git
cd TEP-DigitalTwin
git switch dev
cp .env.example .env
```

`.env`의 최소 확인 대상은 다음과 같다.

- `APP_ENV=development`
- `API_PORT`
- `KAFKA_*` topic 및 consumer group
- `MODEL_VERSION`, `MODEL_DIR`
- `DATA_*_DIR`, `LOG_DIR`

이후 배포 스크립트를 실행한다.

```bash
bash deploy/09-manual-deploy.sh
```

`PROJECT_DIR` 환경변수로 저장소 경로를 명시할 수도 있다.

```bash
PROJECT_DIR=/opt/tep-digitaltwin bash deploy/09-manual-deploy.sh
```

## 4. 코드 갱신 배포

배포 전에 작업 트리가 깨끗한지 확인한 뒤 `dev`의 최신 코드를 반영한다.

```bash
git status --short
git pull --ff-only origin dev
bash deploy/09-manual-deploy.sh
```

`--ff-only`를 사용해 서버에서 의도하지 않은 병합 커밋이 생기지 않게 한다.

## 5. 배포 후 확인

```bash
docker compose ps --all
docker compose logs --tail 100 kafka
docker compose logs --tail 100 api inference monitor
```

서비스 구현 완료 후에는 다음도 확인한다.

- FastAPI endpoint 응답
- Kafka topic 생성 및 메시지 송수신
- 서버 재부팅 뒤 Docker 서비스 재기동

## 6. 현재 제한 사항

Docker Engine 연결, 이미지 빌드, Kafka healthcheck는 로컬 개발환경에서
검증했다. 하지만 API, inference, monitor 실행 모듈은 각각 13번, 12번,
17번 작업에서 구현할 예정이므로, 현재는 전체 서비스가 정상 기동하지 않는다.

따라서 이 문서는 수동 배포 절차와 사전 검증 도구를 제공하지만, 체크리스트
09의 서버 배포 완료 항목과 완료 기준은 실제 Oracle 개발서버에서 전체
서비스를 기동·검증한 뒤에만 완료 처리한다.
