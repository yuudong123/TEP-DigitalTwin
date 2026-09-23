# Jenkins 통합 검증 체크리스트

집컴에서 수동으로 반복 실행하지 않는다. `dev` push 후 Poll SCM이 시작한 Jenkins build에서 확인한다.

## 현재 노트북 검증 완료

- Python 3.11 환경 생성 및 의존성 설치
- Python 소스 문법 검사
- Drift·Kafka·Inference·Monitor 전체 33개 테스트 통과 (2026-09-23)
- Python 패키지 충돌 없음
- Web TypeScript 및 Vite production build 통과
- npm 취약점 0개

## 집컴 Jenkins에서 확인

- [ ] Poll SCM이 새 `dev` commit 감지
- [ ] Python 3.11 의존성 설치 또는 기존 환경 확인
- [ ] `python -m compileall -q src kafka tests` 통과
- [ ] `python -m pytest tests -q` 통과 (함수형 pytest 테스트도 포함)
- [ ] `python -m pip check` 통과
- [ ] `web`에서 `npm ci` 통과
- [ ] `web`에서 `npm run build` 통과
- [ ] Kafka healthcheck 통과
- [x] Kafka Producer·Consumer 실제 송수신 및 sequence 순서 확인 (2026-09-21, 2,929건)
- [x] Drift Monitor 이미지 빌드·Kafka Event smoke test (2026-09-23, 40개 Event)
- [ ] API·inference·monitor Docker image build 통과
- [ ] 구현된 서비스 container가 재시작 없이 유지
- [ ] 실패 시 `docker compose ps --all`과 최근 로그 보존

API·inference·monitor 실행 모듈이 모두 구현되기 전에는 전체 Compose 기동 실패를
08~10번 완료로 처리하지 않는다.
