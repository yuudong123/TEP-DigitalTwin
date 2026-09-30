# 13 · Live API / Web 계약

Unity는 사용자 집 PC 작업 범위로 남긴다. 아래는 실제 CSV→Kafka→Inference→API→Web 경로다.
기본 mock fallback은 없다. 개발용 mock만 `VITE_PREDICTION_SOURCE=mock`으로 명시한다.

## 실행

`.venv/Scripts/python -m src.api.main` (모델, Kafka, `data/metadata` 필요).
배포 gate가 Web을 검사·빌드한 후 Docker API 이미지에 포함해 같은 주소
`http://100.127.7.26:8000/`에서 제공한다. 단독 Docker build 전에는 `web`에서
`npm ci && npm run build`를 먼저 실행해야 한다.
노트북 Web 개발 서버는 localhost:8000으로 `/api`, `/v1`, `/health`를 proxy한다.
집컴 CSV는 API에 읽기 전용 mount, SQLite는 `logs/api-snapshots.sqlite3`에 영구 저장한다.

| 경로 | 계약 |
|---|---|
| GET `/health/live` | HTTP 프로세스 응답; 통합 정상의 증거 아님 |
| GET `/health/ready` | 모델 초기 로드 + Kafka partition 할당; reader 실패 시 503 |
| GET `/api/predictions/latest` · `/v1/predictions/latest` | 기존 Prediction v1.0 그대로, 선택 `trajectory_key`; 없으면 404 |
| GET `/v1/predictions` | trajectory별 마지막 Prediction 및 실제 수신 시각 |
| POST `/v1/predict` | `{"history": [Sensor v1.0 21개]}`; 같은 key, 연속 sequence·3분 시간; 위반 422 |
| GET `/v1/trajectories` | metadata 목록 + host 원본 사용 가능 여부 |
| GET `/v1/replay` | run_id, 상태, ACK 받은 sent/total |
| POST `/v1/replay/start` | `{"trajectory_key":"case1::1","interval_seconds":0.1}`; 간격 .01–10초 |
| POST `/v1/replay/pause` · `resume` · `stop` | 한 번에 한 run. 충돌/불가 상태 409 |
| GET `/v1/monitoring/latest` | Event + received_at; 없으면 404. **운전상태·열화 변화** 의미 |

`/v1/predict`는 동기 추론이며 Kafka/cache를 바꾸지 않는다. 온라인 Kafka 추론 결과가 Web의
source of truth다. 원본을 서버에 임의 업로드하거나 파일 경로를 요청으로 지정할 수 없다.
Replay 중지는 이미 전송/처리 중인 최대 한 행까지 허용하며, 전송 취소/rollback이 아니다.
순서는 단일 partition과 trajectory key에 의존한다. API run은 외부 CLI producer를 잠그지 않으므로
같은 trajectory의 외부 병렬 replay를 금지한다.

## 전달·복구·상태 표시

- Inference/Replay는 `flush()==0`만으로 성공 처리하지 않고 delivery callback 성공 ACK를 요구한다.
- Inference는 ACK 이후 Sensor offset을 commit. 실패 종료 시 해당 offset 미commit.
- Sensor 누락·중복·순서 역전 시 해당 key 버퍼를 비워 21개의 연속 행으로 다시 준비한다.
  재시작에도 메모리 버퍼는 다시 준비해야 한다. exactly-once prediction 보장은 아니다.
- API는 validation/key 검사 후 SQLite transaction을 완료하고 Kafka offset commit.
  topic/partition/offset 중복은 snapshot/수신 시각을 갱신하지 않는다.
- 시뮬레이션 시간은 새 replay에서 작아질 수 있어 “더 큰 timestamp만 최신” 규칙은 쓰지 않는다.
- HTTP 수신 반복은 새로운 Prediction이 아니다. `X-Prediction-Received-At`을 그대로 사용하고
  Web 기본 15초 동안 새 예측이 없으면 DATA STALE. 404/503/timeout은 오류로 표시, mock 대체 없음.
- 센서 전송 종료와 추론 완료는 구분한다. `/v1/replay`의 `inference_caught_up` 및
  `prediction_timestamp_hours`로 처리 backlog를 표시하고 이전 replay 처리 중 새 시작을 거부한다.
- Monitor는 실제 Event만 표시. Data Drift 정답·오탐률·재학습 근거로 해석하지 않는다.

## 접근 범위

현재는 기존 Tailscale 사설 개발 환경 전용이다. API 자체 계정 인증은 미구현이므로 인터넷 공개 금지.
브라우저 쓰기 요청의 다른 Origin은 기본 거부. 필요한 개발 Origin만 `API_ALLOWED_ORIGINS`에 명시.
Origin 검사/CORS는 인증 대체가 아니며 허용 네트워크의 CLI는 접근 가능하다.
동일 origin Web만 기본 사용하고 `.env`, 비밀번호, SSH key를 Web/보고서에 포함하지 않는다.

## 검증 상태

로컬 API 계약/저장/발행 ACK 테스트 및 Web 계약 테스트 추가. 전체 native 모델 테스트와
집컴 실제 Kafka·API·Web 통합은 별도 실제 결과를 `reports/16-integration`에 기록한다.
준비/실행 중인 상태를 완료로 간주하지 않는다.
