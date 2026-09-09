# 프로젝트 기본 구조

## 1. 목적

3인 팀이 같은 규칙으로 개발하고, 이후 Kafka·추론·API·모니터링 서비스를
독립적으로 추가할 수 있도록 저장소의 기본 구조와 공통 파일의 역할을 정리한다.

## 2. 디렉터리 구조

```text
TEP-DigitalTwin/
├─ data/             # 원본·가공 데이터와 공통 metadata
├─ deploy/           # 개발서버 수동 배포 스크립트
├─ docker/           # 서비스별 Dockerfile
├─ docs/             # 번호별 작업 문서
├─ logs/             # 실행 로그 (내용은 Git 제외)
├─ models/           # candidate·production 모델
├─ reports/          # 데이터·모델 검증 결과
├─ src/
│  ├─ common/        # 설정, logger, 모델 공통 유틸리티
│  ├─ data/          # 데이터 탐색·가공·feature 생성
│  ├─ training/      # 모델 학습
│  └─ evaluation/    # 검증 및 모델 비교
├─ compose.yaml      # Kafka·API·inference·monitor 개발환경
├─ requirements.txt  # Python 의존성
└─ .env.example      # 공유 가능한 환경변수 기본값
```

`src/api`, `src/inference`, `src/monitoring`, `src/streaming` 등은 이후
번호 작업에서 추가한다. README의 최종 목표 구조에 이 디렉터리가 보이더라도,
현재는 아직 구현 전이다.

## 3. 공통 설정 규칙

- 실제 실행값은 루트 `.env`에 두고 Git에 커밋하지 않는다.
- 공유 가능한 키 이름과 기본값은 `.env.example`에만 둔다.
- Python 코드에서는 `src/common/config.py`로 환경변수를 읽는다.
- 공통으로 재사용할 설정·logger·모델 유틸리티는 번호 파일명 대신
  `src/common/`에 둔다.
- 작업 산출물은 특별한 공통 라이브러리가 아닌 한
  `04-train_baseline.py`처럼 체크리스트 번호를 파일명 앞에 붙인다.

## 4. Git 협업 규칙

`dev`는 팀 통합 브랜치다. 새 작업은 최신 `dev`에서 독립 feature branch를
만들고 Pull Request로 `dev`에 병합한다.

```text
dev
├─ feat/docker              # 08번 Docker 개발환경
├─ feat/manual-deployment   # 09번 수동 배포 절차
└─ feat/jenkins-cicd        # 10번 Jenkins 파이프라인
```

feature branch는 서로의 미병합 변경을 포함하지 않는다. 공통 기반이 필요하면
먼저 해당 Pull Request를 `dev`에 병합한 뒤 최신 `dev`에서 새 branch를 만든다.

## 5. 개발환경 재현

프로젝트 루트의 `.venv`를 사용한다. 작업 중 필요한 패키지를 전역 Python에
설치하지 않는다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Docker 개발환경과 서비스별 실행 상태는 `docs/08-docker-development.md`에서
확인한다. 현재 API·inference·monitor 실행 모듈은 구현 전이므로 Compose의
전체 정상 기동은 아직 완료 기준을 통과하지 않았다.
