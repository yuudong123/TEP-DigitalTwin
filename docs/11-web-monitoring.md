# Web 모니터링 화면

## 1. 목적

`docs/00-team-roles.md` 기준 담당 C(Visualization + Model Lifecycle)의 시작 작업이다. 11 Kafka,
12 Inference, 13 FastAPI가 아직 구현되지 않은 상태이므로, 실제 API 없이 이미 확정된 예측 출력
계약(prediction schema)에 맞춰 모의 데이터로 동작하는 대시보드를 먼저 만든다. FastAPI가
완성되면 데이터 소스만 실제 API로 교체하고 화면은 다시 만들지 않는 것을 목표로 한다.

## 2. 계약 근거 문서

- `models/production/v1.0.0/prediction_schema.json` — 응답 필드 타입 정의
- `reports/06-final-model/sample_prediction.json` — 실제 값 예시
- `docs/06-final-model.md` §8~9 — `status` 우선순위 규칙과 SHAP 값 해석 시 주의사항

## 3. 기술 스택

- React + Vite + TypeScript, 저장소 루트의 `web/` 디렉터리.
- TypeScript로 `prediction_schema.json`을 타입으로 그대로 옮겨, 실제 FastAPI 응답이 스키마와
  어긋나면 컴파일 타임에 드러나게 한다.
- 별도 UI 프레임워크나 차트 라이브러리는 1차 구현에서는 추가하지 않는다.

## 4. 저장소 규칙

- 서브 프로젝트가 자체 생성하는 `README.md`(예: Vite 템플릿 기본 `web/README.md`)는 두지 않는다.
  프로젝트 문서는 전부 `docs/`에 번호 규칙으로 모은다. 앞으로 새로운 서브 프로젝트를 추가해도
  동일하게 적용한다.
- Git 브랜치는 `docs/00-team-roles.md` 예시를 따라 `feat/web-monitoring`을 사용한다.

## 5. 실행 방법

```powershell
cd web
npm install
npm run dev
npm run build
```

## 6. 현재 진행 상태

완료:

```text
Step 0. feat/web-monitoring 브랜치 생성
Step 1. Vite + React + TypeScript 스캐폴딩, dev 서버 정상 기동 확인
```

진행 예정:

```text
Step 2. prediction schema를 TS 타입으로 이식하고 sample_prediction.json 값을 정적으로 렌더링
Step 3. 모의 실시간 스트림(mock stream)으로 대시보드를 움직이게 연결
Step 4. (선택) RUL·risk score 시계열 그래프
Step 5. 본 문서 최신화
```

## 7. 현재 제한 사항

13번 FastAPI, 12번 Inference, 11번 Kafka가 구현되기 전까지는 실제 실시간 데이터 연동이
불가능하다. 화면은 전부 모의 데이터로 검증하며, 실제 API 연동 시점은 `web/src/hooks/`에 만들
예정인 데이터 소스 훅(`usePredictionStream` 등)의 내부 구현만 교체하는 것으로 한정한다.
