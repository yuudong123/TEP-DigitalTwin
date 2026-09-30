# 16 · 비 Unity 실제 통합 검증

2026-09-30 집컴 Windows Docker / 실제 Kafka. PR #27·#28은 dev 병합 완료.

## 확인된 실제 결과

- 검증 revision `887ce2cc22d5c8cbb3c85df6d73db7a3f387a57c`.
- 운영 서비스와 별도 `live-bb71ec7052-*` 토픽·group·API/Inference/Monitor 컨테이너.
  운영 Kafka broker/볼륨은 그대로 사용, 기존 topic/offset은 변경하지 않았다.
- 실제 `case1.csv`, `case1::1` 센서 **2,929건**, ACK 받은 전송과 metadata 개수 일치.
- 준비 20행 제외 **2,909 Prediction**, timestamp 1.0→146.4h 순서/개수/schema/key 일치.
- `/v1/predict` 실제 첫 21행의 동기 결과와 Kafka 첫 Prediction 전체 JSON 동일.
- API replay pause/resume, active run 충돌 409 확인.
- `/api/predictions/latest`, `/v1/monitoring/latest`, Web HTML 동일 API 주소 제공 확인.
- 전체 검증 **201.578초**. Monitor는 검증용 1초 주기/기존 통계 기준 사용.
  운영 60초 판정이나 새 보정 기준 적용을 증명하는 테스트는 아니다.
- 자동 재학습 요청 false. 변화 Event를 운영 Data Drift label로 해석하지 않는다.
- 브라우저에서 case1::1, v1.0.0, 마지막146.40h, CRITICAL, RUL0.35h,
  3개 risk/SHAP 표시. 새 데이터 종료 후 DATA STALE 전환 확인.

원본 산출물: `full-chain-2026-09-30.json`, `web-live-2026-09-30.png`.

## 추가 보강

관찰 중 센서 전송은 이미 끝났지만 추론 backlog가 남아 있었다. 이에 전달 완료와
추론 완료를 분리 표시하고 backlog 처리 중 새 replay 시작을 막았다. Replay/Monitor 카드의
줄바꿈·비활성 버튼 표시도 보완했다. 이 후속 변경은 별도 테스트/운영 배포에서 확인한다.

노트북·집컴 Python 전체 테스트 78개 통과(추가 backlog/저장 장애 테스트는 별도 후속 실행).
Web 계약 테스트3개, lint/build 통과. Starlette TestClient의 httpx deprecation 경고1개는
있지만 실패가 아니다. 기존 노트북 native DLL 차단이 이번 실행에서는 재현되지 않았다.

## 완료로 주장하지 않는 범위

Unity WebGL은 현재 build required placeholder이며 사용자 집 PC 마무리 대상이다.
이 검증은 실제 replay acceptance이지 장시간 부하·집컴 재부팅 실증이 아니다.
운영 Jenkins 배포 성공, 영구 snapshot 재시작 복구 결과는 후속 증거에 별도 기록한다.

## 후속 실증

- 격리 API 컨테이너 실제 restart 후 Prediction 마지막146.4h 및 수신 시각
  `2026-09-30T08:24:13.692794+00:00` 유지. `api-restart-2026-09-30.json`.
- PR #29 dev 병합(`bea3e4f`) 후 기존 H/2 Poll SCM이 자동 감지.
  Jenkins **#25 SUCCESS**, Kafka/API/Inference/Monitor 전체 배포 exit0 및 보고서 보관 확인.
  `jenkins-deployment-2026-09-30.json`. 재부팅 실증은 아니다.
- 배포 후 화면 검토에서 host `.env`의 `DATA_RAW_DIR=data/raw`와 TEP 하위 mount 차이를 발견.
  direct/nested CSV 탐색 호환 및 컨테이너 경로 override를 보완하고 regression test를 추가했다.
  단순 기동 성공만으로 raw replay 성공을 판단하지 않았다. 운영 replay 검증은 해당 수정 배포 후 수행한다.
