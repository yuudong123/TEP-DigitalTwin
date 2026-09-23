# Jenkins 기본 CI/CD — 집 Windows PC

## 실제 구성

Oracle Cloud와 GitHub 공개 webhook을 사용하지 않는다.

```text
GitHub origin/dev
  → Jenkins TEP-dev (2분마다 Poll SCM)
  → TEP-Windows 실행기 (로그인된 Windows 사용자)
  → 별도 checkout → Compose 검증 → 테스트가 있으면 실행
  → 이미지 3개 빌드 → 구현된 서비스 기동 및 상태 검증
```

- Jenkins: http://localhost:8080/
- 작업: http://localhost:8080/job/TEP-dev/
- 실행기: `TEP-Windows`, 라벨 `tep-windows`, 동시 실행 1개, 해당 라벨 작업만 수행
- 실행기 루트: `D:\TEP_DigitalTwin\.jenkins-agent`
- 배포 코드: `.jenkins-agent\workspace\TEP-dev`의 GitHub `dev` checkout
- 환경변수·모델·로그: `D:\TEP_DigitalTwin`의 기존 파일/디렉터리
- Windows 실행은 `bat`를 사용하고 PowerShell 배포 스크립트를 호출한다.
- `disableConcurrentBuilds()`와 45분 제한을 적용한다.
- Docker 연결: `npipe:////./pipe/dockerDesktopLinuxEngine`

## Git 인증과 Poll SCM

Jenkins 서비스는 기존 LocalSystem 계정을 유지한다. 이 계정은 사용자 Git
인증이 없어 최초 빌드에서 비공개 저장소 checkout이 실패했다.
전용 실행기를 로그인된 Windows 사용자로 연결한 후 기존 Git Credential Manager
인증으로 checkout과 polling이 통과했다. GitHub 토큰을 복사하거나 새로 만들지 않았다.

`pollSCM('H/2 * * * *')`는 2분마다 변경을 확인하며, 변경이 있을 때만 빌드한다.
Git 확장 `DisableRemotePoll`로 polling도 실행기 workspace에서 수행한다.
이를 제거하면 controller의 LocalSystem 계정에서 인증 실패가 다시 발생할 수 있다.

사용자 Git 로그인이 만료되면 해당 Windows 사용자로 GitHub 인증을 갱신해야 한다.
새 커밋 감지부터 자동 배포까지의 검증은 실제 `dev` 변경이 생길 때 추가 확인한다.
테스트를 위해 팀 브랜치에 임의의 커밋을 push하지 않았다.

## 파이프라인 원본과 변경 반영

현재 Jenkins 작업의 Definition은 **Pipeline script**다. 로컬 루트 `Jenkinsfile`의
Windows용 내용을 동일하게 등록했다. 원격 `dev`의 기존 Jenkinsfile은 아직 Linux용이므로
**Pipeline script from SCM**으로 전환하지 않았다. 프로젝트 수정은 미커밋 상태로 보존했다.

Jenkins는 매 빌드 GitHub의 최신 `dev` 소스를 checkout한다. 배포 도구 자체는
집 PC의 `deploy/09-manual-deploy.ps1`을 사용하므로 미커밋 도구도 현재 동작한다.
Jenkinsfile을 수정하면 작업 Configure의 Script에도 동일하게 반영해야 한다.

팀 규칙대로 변경을 기능 브랜치/PR로 `dev`에 반영한 뒤에는 다음으로 전환할 수 있다.

- Definition: Pipeline script from SCM
- SCM: Git / 저장소 URL / Branch `*/dev`
- Script Path: `Jenkinsfile`
- 비공개 저장소를 controller에서 읽을 인증정보가 별도로 필요하다.
  현재 인증 구성에서는 Inline Script 방식을 유지한다.

## 실행기 로그인 자동 시작 — 등록 대기

실행기는 Jenkins에 WebSocket으로 연결한다. 추가 inbound TCP 포트를 열지 않는다.
연결 키는 `.jenkins-agent/agent.secret`에만 저장하며 Git/Docker build에서 제외한다.
실행기 폴더 접근은 현재 사용자, SYSTEM, Administrators로 제한했다.

현재 세션의 임시 실행으로 실제 빌드와 polling을 검증했다.
자동 실행 예약 작업 등록·시작 명령은 도구의 자동 승인 검토에서
`blocked by policy`로 거부되어 등록하지 않았다.

등록할 내용은 `deploy/10-register-agent.ps1`에 준비했다.
현재 사용자 로그인 시, 관리자 권한·비밀번호 저장 없이 `TEP-Jenkins-Agent` 작업을
실행한다. 기존 같은 이름의 작업이 있으면 덮어쓰지 않고 중단한다.
`10-start-agent.ps1`은 실행기를 연결하고 프로세스 종료 시 15초 후 재접속한다.

사용자가 등록하기로 한 경우 일반 PowerShell에서 실행한다.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File D:\TEP_DigitalTwin\deploy\10-register-agent.ps1
```

등록 후 확인:

```powershell
Get-ScheduledTask -TaskName TEP-Jenkins-Agent
Get-ScheduledTaskInfo -TaskName TEP-Jenkins-Agent
```

Jenkins Nodes에서 `TEP-Windows`가 online인지 확인한다. Docker Desktop이 올라온 뒤
TEP-dev의 지금 빌드를 실행해 재검증한다. PC는 로그인 상태로 켜둬야 한다.

## 결과 해석

- `SUCCESS`: 모든 구현 서비스의 기동 검증까지 통과
- `UNSTABLE`: 이미지 빌드·Kafka 기동 통과, 이후 단계의 서비스 코드 미구현
- `FAILURE`: checkout·설정·테스트·빌드·기동 중 실제 실패

현재 미구현 entrypoint는 `src/api/main.py`, `src/monitoring/main.py`다.
`src/inference/main.py`는 PR #24로 dev에 통합되었다. 각각 구현되면 다음 배포에서 기동 대상에 포함된다.
기동 성공은 도메인 기능 검증을 대체하지 않으며 API·Kafka 흐름은 구현 후 별도 검증한다.

## 2026-09-11 확인 기록

- [x] Jenkins 기존 서비스와 test 작업 보존
- [x] TEP-dev 및 Windows 전용 실행기 구성
- [x] Windows 사용자 Git 인증으로 비공개 dev checkout
- [x] 빌드 #2: 이미지 세 개 빌드·Kafka healthy 확인, UNSTABLE
- [x] 00:20 KST Poll SCM: 실제 원격 fetch 후 No changes 확인
- [x] 공개 webhook/추가 inbound 포트 없이 구성
- [ ] 실행기 로그인 자동 시작 등록 (자동 승인 검토 거부)
- [ ] 실제 새 dev 커밋으로 자동 빌드 발생 확인
- [ ] 재부팅 후 로그인·Docker·실행기·배포 복구 검증
- [ ] API/inference/monitor 전체 서비스 검증

공식 참고: [Pipeline 문법](https://www.jenkins.io/doc/book/pipeline/syntax/),
[Windows bat](https://www.jenkins.io/doc/pipeline/steps/workflow-durable-task-step/),
[Compose up](https://docs.docker.com/reference/cli/docker/compose/up/).
