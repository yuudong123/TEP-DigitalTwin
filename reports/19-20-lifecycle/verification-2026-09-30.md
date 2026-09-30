# 19·20 · 실제 validation 및 live model application

기준 revision `6110e811bfc7ec4912598342394c20e6220330e5`.
집컴 실제 v1.0.0 4모델을 별도 **control version**으로 복사했다.
새 학습/성능 개선이 아니라 평가·전달·적용 경로의 양성 대조다. 운영 모델은 바꾸지 않았다.

## 19 validation 평가

- 실제 `validation.parquet` **238,872행 / 90 trajectories / case1–6 전체**.
- 728 ordered features 및 기존 thresholds 고정, 학습/threshold search/test tuning 없음.
- 전체와 각 case의 RUL MAE/RMSE, 3 horizon AP/F1/Recall/FPR 비악화 정책 통과.
- 동일 실제 모델이므로 baseline/candidate metrics 동일. improved_model=false.
- 평가 보고서 SHA256 `bc713d56bb78fafe58cf4b4a636ea23cefdfaa3c2e68dd7221aa461cfce82986`.
- 보고서/후보/Production fingerprint 불일치, 성능 악화, generation 충돌 거부는 단위 테스트로 확인.

## 20 실제 Kafka·API

- 별도 `model-proof-56af1f1a00-*` topic/group/API/Inference 및 logs/registry 사용.
- 실제 case1 CSV 처음30행 → 준비20행 제외10개 Kafka Prediction.
- 원래 v1.0.0 → control version → 손상 pointer 거부·control 유지 → v1.0.0 rollback.
- API `/v1/predict`도 동일한 순서로 실제 model_version 확인.
- API/Inference acknowledgement 둘 다 `rejected_retaining_previous` 확인.
- 실행 결과 `application-proof-2026-09-30.json`, 전체 평가 `validation-control-2026-09-30.json`.

원자 pointer는 명령 처리 증거이고 실제 Kafka Prediction.model_version이 적용 증거다.
운영 재학습 label/새 후보를 확보하지 않았으므로 실제 개선 모델의 운영 승격 완료로 표시하지 않는다.
노트북·집컴 전체 Python88개 통과(후속 raw-dir regression은 별도 재검증).
