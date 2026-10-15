# Unity 디지털트윈

## 공정 개요 화면 — 2026-10-15

현재 기본 화면은 `Assets/TEP/Scenes/TEPProcessOverview.unity`다.
Unity 메뉴 `TEP Digital Twin > Generate Process Overview`로 생성할 수 있다.
기존 `TEPDigitalTwinDemo` 및 설비 프리팹은 유지한다.

- 원료 → 반응기(R-101) → 응축/냉각(E-101) → 분리기(V-101) → 정제기(T-101) → 제품.
- 분리기 기체는 압축기(C-101)를 거쳐 반응기로 재순환한다. 배관은 청록/황색으로 구분한다.
- 형상과 배관은 기획 흐름을 설명하는 모형이며 물리 공정 시뮬레이터가 아니다.
- 모든 설비의 상태 밴드는 **공정 전체 상태**를 표시한다. 개별 설비 고장 확률을 의미하지 않는다.
- 오른쪽 패널은 전체 상태·RUL·1/2/4시간 위험/threshold·상위 SHAP 변수·모델/trajectory/공정 시간을 표시한다.
- 화면·설비 이름·상태·주요 위험 변수·시간 단위는 한글로 표시한다. 예측 JSON의 식별자와 필드명은 원래 계약을 유지한다.
- 나눔고딕을 프로젝트에 포함하여 웹에서도 한글을 표시한다. 폰트의 OFL 라이선스는 `Assets/TEP/Resources/NanumGothic-OFL.txt`에 포함한다.
- 기본은 데이터 대기다. Web의 `ApplyPredictionEnvelope` 수신 후 표시한다. 서버의 원래 수신 시각을 기준으로 15초가 지나면 한글로 데이터 지연을 표시한다. 같은 예측을 다시 조회해도 수신 시각을 갱신하지 않는다.
- `showRecordedPreview`를 명시적으로 켜면 포함된 실제 기록 예측을 표시한다. 기록 미리보기 / 실시간 아님으로 구분한다.
- `-tepSnapshot <JSON>` / `-tepCapture <PNG>`는 독립 실행 파일에서 명시적 기록 화면 캡처에 사용한다.

WebGL은 `TEP Digital Twin > Build Process Overview WebGL`로 빌드한다.
출력은 `web/public/unity/`, 압축 없는 `.data` / `.framework.js` / `.wasm`을 사용한다.
웹 로더 경로도 이 설정에 맞췄다. 실제 WebGL/API 연결은 컴파일된 Unity가 적용한 예측을 JS ACK로 다시 보내 검증한다. 단순히 HTTP 200이나 캔버스 존재만으로 연결 성공을 판정하지 않는다.

프로젝트 지정 버전은 Unity `6000.3.24f1`을 유지한다. 현재 검증한 Windows 화면과 WebGL은
이 PC에 설치된 `6000.1.10f1`의 별도 프로젝트에서 동일한 표시 코드로 빌드했다.
원본 프로젝트의 버전과 URP 패키지 설정을 낮추지 않는다. 별도 검증 프로젝트는 built-in renderer를 사용한다.
6.3 설치는 당시 승인 정책에 막혀 진행하지 못했으므로 원본 버전/URP 렌더링까지 검증했다고 하지 않는다.

## 자동 빌드와 검증

`deploy/build-unity.ps1`은 원본에 지정된 에디터를 기본으로 요구한다. 다른 버전은
명시적 `-AllowCompatibleEditor` 옵션이 있을 때만 `logs/unity-build/compatible-project`에 격리해 빌드한다.
`09-manual-deploy.ps1`은 runtime `.env`의 `UNITY_EDITOR_PATH`, `UNITY_ALLOW_COMPATIBLE`만 읽어 이 빌드를 실행한다.
현재 집 PC는 설치된 6.1 경로와 `UNITY_ALLOW_COMPATIBLE=true`를 명시적으로 사용한다.
빌드 산출물은 대용량이므로 Git에 넣지 않고 배포 시 생성한다. 빌드 버전·호환 모드·소스 및 산출물 SHA는
`web/public/unity/build-info.json`에 남긴다. Unity 라이선스가 없는 실행 계정에서는 새 빌드가 실패할 수 있다.

실제 예측 fixture로 정상 데이터 적용, 숫자 상태 별칭 거부, 범위 밖 위험도 거부, 수신 시각 누락 거부를
에디터에서 검사한 뒤 WebGL을 생성한다. 해당 로그 표지는 `TEP_BRIDGE_CONTRACTS_PASSED`다.

```powershell
Set-Location D:\TEP_DigitalTwin
.\deploy\build-unity.ps1 -UnityEditor 'C:\Program Files\Unity\Hub\Editor\6000.1.10f1\Editor\Unity.exe' -AllowCompatibleEditor
Set-Location web
node verify-webgl.mjs http://127.0.0.1:8000 90 ../reports/26-final/webgl-smoke.json ../reports/26-final/unity-live.png
```

브라우저 검증은 실제 Edge의 컴파일된 WebGL과 운영 API를 사용한다. 모델/trajectory/공정 시각/RUL/세 위험 점수·임계값·alert 및 원래 수신 시각을 비교한다.
웹 표시 일시정지와 연결 오류/복구가 Unity까지 전달되는지도 확인한다. Mock 응답으로 실제 연결을 대체하지 않는다.

## 1. 목적

현재 기본 화면은 위 공정 개요이며 FastAPI의 실제 예측을 Web에서 전달한다.
아래 프리팹 데모는 초기 구현을 보존한 별도 예제다. Mock 데모를 운영 연결 증거로 사용하지 않는다.

## 2. 프로젝트

- Unity 6.3 (`6000.3.24f1`), Universal 3D/URP
- 위치: `unity/TEP-DigitalTwin-Unity/`
- 데모 씬: `Assets/TEP/Scenes/TEPDigitalTwinDemo.unity`

## 3. 프리팹 구조

```text
EquipmentBase.prefab
├─ Reactor.prefab (variant)
├─ Separator.prefab (variant)
├─ Compressor.prefab (variant)
└─ Stripper.prefab (variant)

ProcessLine.prefab
├─ Reactor
├─ Separator
├─ Compressor
└─ Stripper

DashboardCanvas.prefab
DigitalTwinRuntime.prefab
Environment.prefab
```

설비 형상과 공정 배치는 프리팹에서 관리한다. 씬은 위 프리팹 인스턴스만 조립하며 상태 색상은
공유 `StatusPalette.asset`을 사용한다.

## 4. 상태 규칙

| 상태 | 색상 |
| --- | --- |
| NORMAL | 초록 |
| CAUTION | 노랑 |
| WARNING | 주황 |
| CRITICAL | 빨강 |

색상 코드는 Web과 동일하게 NORMAL `#4caf50`, CAUTION `#f5a623`, WARNING `#ff7a00`,
CRITICAL `#e63946`을 사용한다. 모의 스트림의 마지막 CRITICAL 스냅샷도 Web이 사용하는
`reports/06-final-model/sample_prediction.json`의 trajectory, timestamp, RUL, risk, threshold와
동일하다.

기존 데모에서만 반응기는 전체 `status`, 분리기는 4시간 위험도, 압축기는 2시간 위험도, 스트리퍼는 1시간
위험도를 표시한다. 위험 점수/threshold 비율이 60%, 80%, 100%를 넘으면 각각 CAUTION,
WARNING, CRITICAL로 표시하며 `alert=true`는 CRITICAL이다.

## 5. 생성 및 실행

Unity 메뉴에서 `TEP Digital Twin > Generate Demo (Prefabs + Scene)`를 한 번 실행한다. 생성된
`TEPDigitalTwinDemo` 씬을 열고 Play하면 2초마다 NORMAL부터 CRITICAL까지 상태가 변한다.

생성 메뉴는 프리팹과 씬을 같은 경로에 다시 만들어 반복 실행할 수 있다.

카메라 조작:

- `W/A/S/D`: 전후좌우 이동
- `Q/E`: 아래/위 이동
- `Shift`: 빠르게 이동
- 마우스 오른쪽 버튼을 누른 채 이동: 시점 회전

Web 대시보드에 포함하려면 Unity 메뉴에서
`TEP Digital Twin > Build WebGL for Web Dashboard`를 실행한다. 빌드 결과는 자동으로
`web/public/unity/`에 생성되며 React 대시보드가 `/unity/Build/unity.loader.js`를 로드한다.
웹의 Unity 영역은 데스크톱에서 우측 아래 모서리로 가로·세로 크기를 조절할 수 있고 모바일에서는
세로 크기를 조절할 수 있다. `ResizeObserver`와 Unity의 `matchWebGLToCanvasSize` 설정이 CSS 크기,
WebGL 렌더 버퍼, 화면 DPR을 동기화한다.

## 6. 실제 API 연결 지점

운영 Web은 `/api/predictions/latest`와 응답 헤더 `X-Prediction-Received-At`를 읽는다.
React가 `WebPredictionBridge.ApplyPredictionEnvelope`로 `prediction`, `received_at_unix_ms`,
`source_mode`, `connection_state`를 함께 전달한다. 기존 `ApplyPredictionJson`은 호환용으로 유지한다.
첫 외부 예측을 받으면 내부 mock source를 중지한다. 오류·일시정지·지연은 마지막 예측과 구분해 표시한다.
유효하지 않은 데이터는 마지막 정상 예측을 유지하고 오류로 표시하며 ACK하지 않는다.

## 7. 검증 경계

- Windows 기록 화면 캡처 및 실제 WebGL/API 짧은 연동 테스트 완료.
- 합의된30분 연속 관찰 완료와 미실행 cold stop/start 경계는 `26-final-acceptance.md` 및 원본 보고서에서 확인한다.
- 원본 Unity 6.3/URP 동일 버전 빌드와 물리 공정 시뮬레이션은 이번 증거 범위가 아니다.
