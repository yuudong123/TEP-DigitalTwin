# 팀 역할 분담 및 작업 시작 기준

## 1. 공통 원칙

이 프로젝트는 3인 팀 프로젝트이며, `dev`가 통합 브랜치다.
각 담당자는 최신 `dev`에서 독립 feature branch를 만든 뒤 Pull Request로
병합한다. 다른 feature branch를 기반으로 새 작업을 시작하지 않는다.

공통 schema, Kafka topic, API contract처럼 다른 작업에 영향을 주는 결정은
문서와 Pull Request에서 먼저 공유한다.

## 2. 담당 범위

| 담당 | 영역 | 시작 작업 | 이후 작업 |
| --- | --- | --- | --- |
| A | Backend | 11 Kafka 실시간 데이터 재생 | 12 실시간 추론, 13 FastAPI, 16 일부 통합 |
| B | Infrastructure / Operations | 08 Docker 개발환경 유지·보완, 17 Drift 감지 설계 | 09 수동 배포 검증, 10 Jenkins 실운영 설정, 20 모델 적용, 21·16 일부 통합 |
| C | Visualization + Model Lifecycle | 14 Web 화면·모의 데이터 기반 UI, 15 Unity 설계 | 18 자동 재학습, 19 후보 모델 평가·승격, 16 일부 통합 |
| 공통 | 품질·마무리 | 22 테스트 및 장애 대응 | 23 최종 통합, 24 문서화 |

## 3. 바로 시작할 수 있는 작업

### A — Kafka 재생

- `feat/kafka-replay`에서 11번을 시작한다.
- sensor topic, 메시지 schema, trajectory·case 선택 방식은 구현 전에 문서로
  확정한다.
- 12번 inference와 13번 API가 같은 메시지 schema를 사용한다.

### B — 운영 기반 및 Drift 설계

- Docker Compose는 구성 완료 상태이며, API·inference·monitor 실행 모듈이
  구현되면 전체 기동을 다시 검증한다.
- 17번에서는 drift event schema와 재학습 trigger 조건을 먼저 정한다.
- 09·10번의 실제 서버 배포와 Jenkins 검증은 집 컴퓨터를 배포 대상으로
  준비한 뒤 진행한다.

### C — Web·Unity 및 모델 생명주기 준비

- `feat/web-monitoring`, `feat/unity-digital-twin`처럼 작업 단위별 branch에서
  UI·레이아웃·모의 데이터 기반 화면을 먼저 구현한다.
- FastAPI endpoint와 응답 schema는 A와 합의한 뒤 실시간 연결한다.
- 18·19번은 B의 drift event와 A의 inference 결과 schema가 확정된 뒤
  본격 구현한다.

## 4. 주요 의존성

```text
11 Kafka 재생 ──→ 12 Inference ──→ 13 FastAPI ──→ 14 Web / 15 Unity
                     │
                     └──────────→ 17 Drift ──→ 18 재학습 ──→ 19 평가·승격 ──→ 20 적용

08 Docker ──→ 16 통합 ──→ 09 수동 배포 ──→ 10 Jenkins
```

09·10번은 배포 대상 컴퓨터가 준비될 때까지 문서·스크립트 수준으로만
완료된 상태다. 08번도 API·inference·monitor 구현 전에는 전체 기동 완료로
체크하지 않는다.

## 5. 공유해야 하는 산출물

- A: Kafka topic, 메시지 schema, inference 입력·출력 schema, API contract
- B: Compose 환경변수, 로그·배포 규칙, drift event와 모델 적용 규칙
- C: Web·Unity가 필요한 API 필드, 화면 상태 정의, 재학습·모델 승격 결과 schema

공통 파일(`src/common/config.py`, `src/common/logger.py` 등)을 수정할 때는
영향 범위를 Pull Request에 적고 담당자에게 알린다.
