# Web 모니터링 화면

## 1. 목적

`docs/00-team-roles.md` 기준 담당 C(Visualization + Model Lifecycle)의 시작 작업이다. 11 Kafka,
12 Inference와 13 FastAPI 모두 dev에 통합되었다. 확정된 예측 출력 계약에 맞춰
모의 대시보드로 시작했고 2026-09-30 실제 API·CSV replay·Monitor 표시까지 연결했다.
현재 기본 실행은 실제 API이며 mock은 명시 선택한 개발 모드다.

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
Step 5. 실제 FastAPI 응답·수신 시각 stale·CSV replay 제어·Monitor 통합
```

진행 예정:

```text
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

현재 FastAPI 계약이 확정되었고 실제 CSV→Kafka→Inference→API→Web을 검증했다.
기본 source는 api, endpoint는 동일 origin `/api/predictions/latest`다.
mock은 `VITE_PREDICTION_SOURCE=mock` 명시 시에만 사용한다. 배포 gate는 api/동일 origin을 강제한다.
서버 수신 시각을 유지해 기본15초 이후 DATA STALE로 표시한다. 오류 시 mock으로 바꾸지 않는다.
실제 trajectory 선택 및 replay 시작/일시정지/재개/중지, 센서 전송 종료와 추론 backlog를 구분한다.
운전상태 Monitor Event도 표시하되 Data Drift 정답/오탐률로 해석하지 않는다.
Unity는 사용자 집 PC 마무리 범위이며 이번 작업에서 소스/빌드를 변경하지 않았다.
계약/보안 범위는 `docs/13-live-api.md`, 실제 증거는 `reports/16-integration` 참조.
