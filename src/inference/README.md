# TEP 실시간 추론 서비스

Kafka의 `tep-sensor-data` 메시지를 받아 trajectory별 최근 60분을 메모리에
보관하고, 학습 당시와 같은 728개 Temporal Feature를 만든 뒤 Production
XGBoost 모델 4개로 추론한다. 결과는 `tep-predictions`로 발행한다.

## 처리 순서

1. Sensor 메시지 수신
2. trajectory별 21행(현재 포함 60분) 버퍼링
3. 최초 20행은 준비 구간으로 사용
4. 21번째 메시지부터 728개 Feature 생성
5. RUL·4시간·2시간·1시간 위험도 추론
6. `NORMAL`, `CAUTION`, `WARNING`, `CRITICAL` 판정
7. 위험도를 증가시키는 SHAP 상위 5개 생성
8. Prediction 메시지 발행

Producer의 실제 전송 간격이 `0.1초`여도 시간 계산은 메시지의
`timestamp_hours`를 사용한다. 원본 데이터는 0.05시간, 즉 3분 간격이다.

## 필요한 환경변수

```env
KAFKA_BOOTSTRAP_SERVERS=100.127.7.26:9092
KAFKA_SENSOR_TOPIC=tep-sensor-data
KAFKA_PREDICTION_TOPIC=tep-predictions
KAFKA_CONSUMER_GROUP=inference-service
MODEL_DIR=C:/TEP-DigitalTwin/models/production/v1.0.0
```

`MODEL_DIR`은 생략할 수 있으며 기본값은
`models/production/v1.0.0`이다.

## 1. Temporal Feature 일치 검증

프로젝트 루트에서 실행한다.

```powershell
python -m inference.validate_temporal --case case1 --id 1 --row 20
```

정상 결과:

```text
비교 Feature: 728개
최대 절대 오차: 0에 가까운 값
최종 결과: 정상
```

## 2. Prediction 토픽 생성

Docker 컴퓨터에서 한 번 실행한다.

```cmd
docker exec tep-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:19092 --create --if-not-exists --topic tep-predictions --partitions 1 --replication-factor 1
```

## 3. 실시간 추론 실행

첫 번째 PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m src.inference.main
```

다음 문구가 나온 상태로 창을 유지한다.

```text
[수신 대기] Producer를 실행하세요. 첫 20개 메시지는 60분 준비 구간입니다.
```

두 번째 PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python .\kafka\producer.py --case case1 --id 1 --send
```

`case1::1`은 2,929개 Sensor 메시지 중 첫 20개가 준비 구간이므로 정상이라면
Prediction 메시지 2,909개가 생성된다.

종료할 때는 추론 서비스 창에서 `Ctrl+C`를 누른다.

## 파일 역할

| 파일                   | 역할                                       |
| ---------------------- | ------------------------------------------ |
| `temporal_features.py` | 최근 21행으로 728개 Feature 생성           |
| `model_loader.py`      | 모델·임계값 로딩, 상태 판정, SHAP 계산     |
| `prediction_schema.py` | Prediction 메시지 기본 검증                |
| `service.py`           | Kafka 수신·추론·발행                       |
| `validate_temporal.py` | 오프라인 계산 결과와 실시간 계산 결과 비교 |
