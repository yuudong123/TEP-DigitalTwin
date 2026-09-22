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
Step 2. prediction schema를 TS 타입으로 이식하고 sample_prediction.json 값을 정적으로 렌더링
Step 3. 모의 실시간 스트림과 재생 제어를 연결하고 Unity WebGL에 같은 예측 전달
Step 4. Mock/API 데이터 소스 전환, API 응답 검증, 연결 상태와 오류 처리 기반 구현
```

진행 예정:

```text
Step 5. FastAPI endpoint 확정 후 실제 응답 통합
Step 6. (선택) RUL·risk score 시계열 그래프
```

Step 2 구현 내용:

- `web/src/types/prediction.ts` — `models/production/v1.0.0/prediction_schema.json`을 그대로
  옮긴 TypeScript 인터페이스(`Prediction`, `RiskEntry`, `RiskFactor`, `Status`, `RiskHorizon`).
- `web/src/mock/samplePrediction.ts` — `reports/06-final-model/sample_prediction.json`의 실제
  값을 하드코딩한 고정 스냅샷.
- `web/src/components/` — `Header`, `StatusBadge`, `RulCard`, `RiskPanel`, `RiskFactorList` 5개
  컴포넌트. 색상 규칙은 `docs/06-final-model.md` §9의 상태 우선순위(`CRITICAL > WARNING >
  CAUTION > NORMAL`)를 따른다.
- Playwright로 렌더링 결과를 스크린샷 검증: RUL 0.36h, 3개 horizon 모두 100.0%로 threshold를
  초과해 ALERT 표시, `Product Sep Level` 계열 5개 위험 요인이 `sample_prediction.json`과 정확히
  일치하는 것을 확인했다.

Step 3 구현 내용:

- `web/src/hooks/usePredictionStream.ts` — 2초 간격으로 네 예측 스냅샷을 순환하는 데이터 훅.
- `web/src/components/StreamControls.tsx` — 재생·일시정지·처음부터 및 마지막 갱신 시각 표시.
- `web/src/mock/predictionSequence.ts` — NORMAL, CAUTION, WARNING, CRITICAL 상태 시퀀스.
- Web 카드와 Unity WebGL에 같은 `Prediction` 객체를 전달한다. Unity가 준비되면
  `DigitalTwinRuntime.ApplyPredictionJson`을 호출하며 Unity 자체 모의 스트림은 자동으로 중지된다.

Step 4 구현 내용:

- `web/.env.example` — `VITE_PREDICTION_SOURCE`로 `mock`/`api` 모드를 선택하고 API URL,
  조회 주기, 요청 제한 시간을 환경변수로 관리한다.
- `web/src/config/predictionSource.ts` — 환경변수를 안전한 기본값과 함께 읽는 설정 계층.
- `web/src/services/predictionApi.ts` — 최신 예측 조회, 요청 타임아웃, HTTP 오류 및 Prediction
  응답 구조의 런타임 검증을 담당한다.
- API 모드에서는 연결 중·연결됨·일시정지·오류 상태와 마지막 정상 수신 시각을 표시한다.
  일시적 오류가 발생해도 마지막 정상 예측은 화면에 유지하며 `다시 연결`로 즉시 재시도할 수 있다.

API 모드 실행 예시:

```powershell
cd web
Copy-Item .env.example .env.local
# .env.local에서 VITE_PREDICTION_SOURCE=api 및 endpoint 수정
npm run dev
```

## 7. 현재 제한 사항

13번 FastAPI endpoint와 최종 전송 방식이 확정되기 전까지 실제 실시간 데이터 검증은 불가능하다.
현재 클라이언트는 `GET`으로 단일 Prediction JSON을 조회하는 계약을 가정한다. 실제 명세가 다르면
`web/src/services/predictionApi.ts`의 요청 및 응답 변환 부분만 조정한다.
