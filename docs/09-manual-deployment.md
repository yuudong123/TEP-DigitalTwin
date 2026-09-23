# 집 Windows PC 개발서버 수동 배포

## 운영 기준

Oracle Cloud는 사용하지 않는다. 집 Windows PC를 켜두고 로그인 상태로 운영한다.
실제 프로젝트 경로는 `D:\TEP_DigitalTwin`이다. `D:\TEP-DigitalTwin`은 존재하지 않는다.
8번 Docker 개발환경 구성은 완료로 취급하며, 서비스 구현은 12·13·17번에서 진행한다.

- Jenkins Windows 서비스: 실행 중, 자동 시작, LocalSystem
- Docker Desktop/Engine: 로그인된 Windows 사용자에서 실행
- Git 기본 브랜치: `dev`
- 실제 환경변수: 기존 루트 `.env` (Git 제외, 내용 유지)
- 모델과 로그: 기존 `models/`, `logs/` 유지

## 수동 배포

```powershell
Set-Location D:\TEP_DigitalTwin
git status --short --branch
# 작업 트리가 깨끗하고 로컬 dev를 갱신할 때만 실행한다.
# git pull --ff-only origin dev
powershell.exe -NoProfile -ExecutionPolicy Bypass -File deploy\09-manual-deploy.ps1
```

`09-manual-deploy.ps1`은 Compose 구성을 검증하고, 테스트 파일이 있으면
집 PC의 `.venv\Scripts\python.exe`로 실행한다. 테스트가 없으면 건너뛰었다고
명시한다. 이어서 이미지 세 개를 빌드하고 구현된 서비스만 기동한다.

- `src/api/main.py`, `src/inference/main.py`, `src/monitoring/main.py`가 없는
  서비스는 기존 컨테이너를 중지하고 미구현으로 보고한다. 삭제하지 않는다.
- 해당 파일이 추가되면 다음 배포에서 자동 기동 대상이 된다.
- `up --detach --wait --wait-timeout 180` 후 10초 동안 재시작 여부를 추가 검증한다.
- Compose 프로젝트 이름은 기존과 동일한 `tep_digitaltwin`으로 고정한다.
- 환경변수 값은 콘솔에 출력하지 않는다. 임시 Compose override에는 경로만 쓴다.
- 기존 `.env`, 모델, 로그를 덮어쓰거나 Docker를 초기화하지 않는다.
- `logs/deployment.lock`으로 수동 배포와 Jenkins 배포의 동시 실행을 막는다.
- Compose `!override`를 지원하는 2.24.4 이상이 필요하다. 현재 설치본은 5.5.1이다.

종료 코드: `0` 전체 기동 검증 통과, `2` 기반 환경 배포 통과·미구현 서비스 존재,
`1` 설정/인증/빌드/테스트/기동 실패. `2`는 전체 서비스 정상 기동 성공이 아니다.

## 상태 확인

```powershell
docker compose ps --all
Get-Content .\logs\last-deployment.json
# 문제가 있는 서비스만 로그를 확인한다.
docker compose logs --tail 50 kafka
```

최근 배포 기록에는 실제 소스 경로, 커밋, 실행 서비스와 미구현 서비스가 저장된다.
Jenkins는 별도 checkout을 빌드하므로 로컬 개발 폴더의 미커밋 코드는 배포되지 않는다.
기존 Linux용 `09-manual-deploy.sh`는 보존하지만 집 PC 운영에는 사용하지 않는다.

## 전원과 로그인

AC 전원에서 절전·최대절전 대기시간을 0으로 설정했고 하이브리드 절전도 해제했다.
DC 설정과 화면 꺼짐 시간은 변경하지 않았다. 최대절전 기능 자체를 삭제하지 않았다.
Docker Desktop 로그인 자동 시작 설정 및 사용자 시작 항목을 설정했다.
Jenkins 실행기는 `10-jenkins-cicd.md`의 로그인 자동 시작 등록이 추가로 필요하다.
PC 재부팅 검증은 하지 않았으며, 로그아웃하면 사용자 실행기는 중단된다.

## 2026-09-11 검증

- [x] 실제 경로·dev 브랜치·원격 최신 상태 확인
- [x] 기존 .env 존재 및 Git 제외 확인
- [x] Compose 구성 검증과 이미지 세 개 빌드
- [x] Kafka healthy 및 추가 재시작 없음
- [x] 미구현 서비스 반복 재시작 중지, 컨테이너·데이터 보존
- [x] AC 절전·최대절전 설정 및 Docker 로그인 시작 설정
- [ ] API·inference·monitor 전체 정상 기동 (Inference·Monitor 통합 완료, API 구현 대기)
- [ ] 로그인 후 자동 복구와 재부팅 실증 (실행기 자동 시작 등록 후 검증)

## Tailscale 원격 접속

집 PC에는 Tailscale 1.102.4를 설치하고 `tep-server`라는 이름으로 연결했다.
Windows 서비스는 자동 시작이며, 로그아웃 뒤에도 연결을 유지하는 Unattended Mode와
자동 업데이트를 켰다. 공유기 포트포워딩이나 인터넷 공개 포트는 사용하지 않는다.

외부에서 접속할 노트북에도 Tailscale을 설치하고 같은 계정으로 로그인한 뒤 사용한다.

```text
Jenkins: http://tep-server:8080
Jenkins IP 주소: http://100.127.7.26:8080
향후 API/Web: http://tep-server:8000
```

`tep-server:8080`의 Jenkins 로그인 화면은 실제 HTTP 200 응답을 확인했다.
포트 8000은 API/Web 구현 전이라 현재 연결되지 않는 것이 정상이다.
Tailscale 장치 키 만료 예정일은 2027-03-10이며, 그 전에 갱신하거나
관리 콘솔에서 만료 정책을 검토해야 한다.
