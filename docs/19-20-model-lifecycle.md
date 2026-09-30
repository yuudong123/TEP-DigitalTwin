# 19·20 · 후보 평가·수동 승격·hot application·rollback

자동 재학습(18)은 구현/활성화하지 않는다. 현재 TEP에는 별도 운영 Drift label이 없다.
19·20은 **독립적으로 제공된 후보**를 기존 validation과 비교하고 운영자가 승인한 경우에만
교체하는 흐름이다. 변화 Event는 승격 권한이나 학습 label이 아니다.

## 계약과 보수적 기본 기준

후보는 기존 Production과 동일한 728개 ordered feature, 3분 간격, 60분 준비,
4개 XGBoost 모델 및 Prediction v1.0을 사용해야 한다. metadata의 버전은 다른 고유 버전이어야 한다.
모델4개·feature list/schema·thresholds·metadata·Prediction schema 총9개 파일의 SHA256을 고정한다.

- `validation.parquet`만 평가. 학습·threshold 재조정·test set 열람/튜닝 없음.
- split manifest의 validation trajectory 전체와 case1–6 모두 필요. train/test 혼입·중복 manifest 거부.
- 전체 및 **각 case**에서 RUL MAE/RMSE 증가 없음, 4·2·1h AP/F1/Recall 감소 없음,
  FPR 증가 없음(수치 오차 허용1e-8). 결측·무한대·확률 범위 위반 거부.
- 동등 성능도 통과 가능하나 성능 개선을 주장하지 않는다. 평가 통과는 자동 승격이 아니다.
- 위 정책은 보수적인 프로젝트 기본값이며, 운영 Drift 데이터에 대한 일반화 보증이 아니다.
  향후 기준 변경은 새 정책 version/문서/별도 승인으로 처리한다.

```powershell
python -m src.lifecycle.evaluate --candidate models/candidates/vNEW --baseline models/production/v1.0.0 --validation data/processed/temporal/validation.parquet --output reports/model-evaluation.json
python -m src.lifecycle.main promote --candidate models/candidates/vNEW --report reports/model-evaluation.json --approve-report-sha256 <직접 검토한 보고서 SHA256>
python -m src.lifecycle.main rollback --expected-generation <현재 pointer generation>
```

운영 중 active 모델이 v1.0.0이 아니면 `--baseline`은 실제 active 디렉터리를 지정한다.
승격은 현재 active bundle fingerprint가 평가 baseline과 다르면 거부한다.
수동 CLI는 기존 SSH로 인증된 운영자만 실행한다. 쓰기 HTTP endpoint를 만들지 않는다.

## 원자성·실패·관찰

1. exact report SHA 승인·validation pass·후보 파일 hashes를 다시 검사한다.
2. exclusive lock으로 승격/rollback을 직렬화한다. 기존 version 폴더를 덮어쓰지 않는다.
3. 임시 디렉터리에9파일 복사·hash 재검사 후 immutable version 디렉터리로 rename한다.
4. `logs/model-changes/<generation>.json`을 먼저 기록하고 `logs/model-active.json`을 원자 교체한다.
5. API 동기 추론/Inference는 예측 경계에서 최대1초마다 pointer를 확인한다.
6. 경로 탈출 방지·hash·feature order·4모델 load·Prediction/SHAP smoke 후에만 메모리 reference 교체.
   적용 실패 시 직전 메모리 모델 유지. 재시작 때도 검증된 service acknowledgement의 직전 bundle을 우선 복구한다.
7. `logs/model-status-api.json`, `model-status-inference.json`에서 loaded/applied/rejected 확인.
   **pointer/audit 작성만으로 적용 완료가 아니다. 실제 Prediction.model_version도 확인한다.**
8. rollback은 expected generation이 일치하고 previous bundle hash 검사가 통과할 때만
   새 generation으로 previous를 선택한다. 다음 예측부터 각 서비스가 안전하게 적용한다.

모든 raw 센서/Feature 버퍼는 모델 교체에도 유지한다(동일 feature 계약이 필수).
API Kafka snapshot은 실제 수신된 Prediction의 model_version을 표시하므로 새 pointer version으로
과거 예측을 덮어쓰지 않는다. Monitor의 model_version은 현재 legacy 설정값이며 적용 acknowledgement가 아니다.

운영 설정: `MODEL_ACTIVE_POINTER=logs/model-active.json`, `PRODUCTION_MODEL_DIR=models/production`.
models는 컨테이너 read-only mount, CLI는 집컴 host에서 새 bundle을 추가한다. logs는 영구 mount.
pointer/ack/audit는 Git에 넣지 않고 Jenkins 재배포에도 host 파일을 보존한다.
lock 파일은 프로세스 강제 종료 시 남을 수 있다. 실제 승격 프로세스가 없는지 확인한 후 운영자가
해당 단일 lock만 제거한다. 임의 timeout 자동 해제/production 디렉터리 삭제는 하지 않는다.

## 완료 판정

같은 실제 모델의 별도 control 버전은 전달·적용·rollback의 양성 대조이며 새로운 개선 모델이 아니다.
실제 candidate 학습/승격은 운영 Drift 데이터나 별도 승인된 후보가 확보된 후 수행한다.
소스/test 통과와 실제 validation 전체 평가·live 모델 version 전환 증거를 구분해 기록한다.
