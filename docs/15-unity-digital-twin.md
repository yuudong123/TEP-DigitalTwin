# Unity 디지털트윈

## 1. 목적

담당 C의 Unity 초기 구현이다. FastAPI가 준비되기 전에는 Web과 동일한 예측 계약을 따르는
모의 JSON을 재생하고, 이후 `PredictionSource` 구현만 교체해 실제 API를 연결한다.

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

반응기는 전체 `status`, 분리기는 4시간 위험도, 압축기는 2시간 위험도, 스트리퍼는 1시간
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

`PredictionSource`를 상속한 `FastApiPredictionSource`를 추가하고 `DigitalTwinRuntime` 프리팹의
source 참조만 교체한다. 화면과 설비 코드는 변경하지 않는다. API 응답 필드와 상태 우선순위는
Web 및 `models/production/v1.0.0/prediction_schema.json`과 동일해야 한다.

WebGL로 실행할 때는 React가 `WebPredictionBridge.ApplyPredictionJson`에 현재 `Prediction` JSON을
전달한다. 첫 Web 예측을 받은 Unity는 내부 `MockPredictionSource`를 중지하므로 Web 카드와 3D 설비가
항상 같은 스냅샷을 표시한다.

## 7. 남은 통합 검증

- A의 FastAPI endpoint와 전송 방식 확정
- Unity 런타임 JSON 유효성 검사 및 연결 오류 UI
- Web/Unity에 같은 예측을 넣어 status, RUL, 세 위험 점수가 일치하는지 자동 테스트
- Windows 실행 파일 빌드 및 장시간 재생 검증
