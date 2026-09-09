# Jenkins 기본 CI/CD

## 1. 목적

3인 팀의 `dev` 브랜치 변경을 Jenkins가 검증하고 개발서버에 배포하는
기본 CI/CD 흐름을 정의한다. 모델 재학습과 production 모델 승격은
Jenkins가 아닌 이후 Python MLOps 작업에서 담당한다.

## 2. 파이프라인 원칙

루트 `Jenkinsfile`은 Multibranch Pipeline 기준으로 작성했다.

| 대상 브랜치 | 수행 작업 |
| --- | --- |
| 모든 감지 브랜치 | checkout, Compose 구성 검증, 가능한 경우 테스트 |
| `dev` | 위 검증 후 Docker 이미지 빌드 및 개발서버 배포 |

배포 단계는 `dev`에만 적용한다. 기능 브랜치나 Pull Request가 개발서버를
덮어쓰지 않게 하기 위해서다. 동시에 둘 이상의 배포가 실행되지 않도록
`disableConcurrentBuilds()`를 적용한다.

## 3. Jenkins 서버 준비

Jenkins는 개발서버 또는 Docker daemon에 접근할 수 있는 전용 agent에서
실행한다. agent에는 아래 항목이 필요하다.

- Git
- Docker Engine 및 Docker Compose v2
- Docker daemon 접근 권한
- `tep-development-env` 이름의 Secret file credential
- 선택 사항: 테스트 실행용 프로젝트 `.venv`

Jenkins는 패키지를 설치하거나 가상환경을 새로 만들지 않는다. 테스트가
추가된 뒤에도 프로젝트 `.venv/bin/python`이 존재할 때만 해당 가상환경으로
`pytest`를 실행한다.

## 4. Jenkins Job 설정

1. Jenkins에서 **Multibranch Pipeline** Job을 만든다.
2. GitHub 저장소 `yuudong123/TEP-DigitalTwin`를 branch source로 연결한다.
3. Pipeline 정의는 저장소의 `Jenkinsfile`을 사용한다.
4. 서버용 `.env`를 Jenkins의 **Secret file** credential로 등록하고 ID를
   `tep-development-env`로 설정한다. Jenkinsfile은 빌드 중에만 이를
   작업 경로의 `.env`로 복사하고, 빌드 종료 시 삭제한다.
5. `dev` 브랜치 검색 및 최초 빌드를 실행한다.

GitHub access token, Jenkins credential, 서버 주소는 Jenkins
Credentials 또는 서버 환경설정에만 보관한다.

## 5. GitHub Webhook 설정

GitHub 저장소의 **Settings → Webhooks**에서 Jenkins 공개 주소에 다음
endpoint를 추가한다.

```text
https://<jenkins-host>/github-webhook/
```

- Content type: `application/json`
- Event: `Just the push event`
- Secret: Jenkins와 GitHub에 동일한 값으로 등록

Webhook 설정 뒤 `dev`에 테스트 push를 수행하고, Jenkins build 기록에서
branch 감지와 실행 로그를 확인한다.

## 6. 실패 처리와 로그

파이프라인 실패 시 Jenkins console log에 Compose 서비스 상태와 최근
컨테이너 로그를 남긴다. 이를 통해 build 실패, Docker daemon 접근 실패,
컨테이너 기동 실패를 구분한다.

배포 후 운영 로그는 다음 명령으로 추가 확인한다.

```bash
docker compose ps --all
docker compose logs --tail 100 kafka
docker compose logs --tail 100 api inference monitor
```

## 7. 현재 완료 범위

저장소 내부에서는 Jenkinsfile과 배포 연동 규칙을 준비했다. Jenkins 설치,
GitHub credential·Webhook 등록, 실제 `dev` push 감지와 개발서버 배포는
Jenkins 및 Oracle 개발서버 접근 권한이 있어야 검증할 수 있다.

또한 API, inference, monitor 구현 전에는 Compose 전체 기동이 실패하므로,
10번 체크리스트의 실제 배포 완료 항목은 해당 서비스 구현과 서버 검증 뒤에
완료 처리한다.
