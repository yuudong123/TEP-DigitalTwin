# TEP Kafka 재생 도구

TEP Run-to-Failure CSV에서 선택한 case와 trajectory를 읽어 Kafka로 순차
전송하고, 확인용 Consumer로 메시지 구조·개수·순서를 검증한다.

AI 추론은 이 폴더의 확인용 Consumer가 아니라 12번 Inference Service에서
처리한다.

## 파일 역할

```text
kafka/
├─ message_schema.py   # Sensor 메시지 생성 및 Schema v1.0 검증
├─ producer.py         # CSV trajectory 선택 및 Kafka 전송
├─ consumer.py         # Kafka 송수신 검증
└─ README.md           # 실행 방법
```

## 환경변수

개발 PC의 프로젝트 루트 `.env`에서 다음 값을 사용한다.

```env
KAFKA_BOOTSTRAP_SERVERS=100.127.7.26:9092
KAFKA_SENSOR_TOPIC=tep-sensor-data
KAFKA_CONSUMER_GROUP=inference-service
TEP_REPLAY_INTERVAL_SECONDS=0.1
```

- `100.127.7.26:9092`: Docker 컴퓨터의 Tailscale Kafka 주소
- `tep-sensor-data`: Sensor 메시지 topic
- `inference-service`: 12번 AI 추론 서비스용 group
- `0.1`: 메시지 사이의 실제 전송 대기시간(초)

확인용 `consumer.py`는 추론 서비스와 메시지를 나눠 갖지 않도록
`tep-replay-check-*`라는 별도 group을 자동으로 사용한다.

## 설치

프로젝트 루트에서 가상환경을 활성화하고 의존성을 설치한다.

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r .\requirements.txt
```

`requirements.txt`에는 다음 패키지가 필요하다.

```text
confluent-kafka==2.15.0
```

## Kafka 없이 미리보기

CSV를 읽고 메시지를 생성하지만 Kafka에는 전송하지 않는다.

```powershell
python .\kafka\producer.py --case case1 --id 1 --limit 3
```

정상 결과에서 다음을 확인한다.

```text
trajectory_key: case1::1
sequence: 0부터 증가
timestamp_hours: Time 오름차순
values: 56개
```

`producer.py` 하나로 `case1`부터 `case6`까지 선택할 수 있다. 한 번 실행할
때는 선택한 case의 trajectory Id 한 개를 전송한다.

## 실제 Kafka 송수신

Consumer를 먼저 실행한 후 Producer를 실행해야 한다. 두 PowerShell 모두
프로젝트 루트에서 각각 가상환경을 활성화한다.

### 1. 첫 번째 PowerShell: Consumer

```powershell
.\.venv\Scripts\Activate.ps1
python .\kafka\consumer.py --case case1 --id 1 --expected-count 2929
```

다음 문구가 나오면 창을 닫지 않고 그대로 둔다.

```text
[수신 대기] 이제 다른 PowerShell에서 Producer를 실행하세요.
```

### 2. 두 번째 PowerShell: Producer

```powershell
.\.venv\Scripts\Activate.ps1
python .\kafka\producer.py --case case1 --id 1 --send
```

`--send`를 넣어야 실제 Kafka 전송이 실행된다. `--interval`을 생략하면
`.env`의 `TEP_REPLAY_INTERVAL_SECONDS` 값을 사용한다.

## 정상 결과

Producer는 delivery callback 기준으로 실제 전송 결과를 출력한다.

```text
========== Producer 전송 결과 ==========
전송 요청: 2929
전송 성공: 2929
전송 실패: 0
최종 결과: 정상
```

Consumer 정상 결과는 다음과 같다.

```text
========== Consumer 검증 결과 ==========
trajectory: case1::1
수신 메시지: 2929
스키마 정상: 2929
메시지 오류: 0
sequence 오류: 0
최종 결과: 정상
```

## 시간의 의미

```text
TEP_REPLAY_INTERVAL_SECONDS
→ 프로그램이 다음 메시지를 보내기 전 기다리는 실제 시간

timestamp_hours
→ CSV의 Time이며 AI Temporal Feature가 사용하는 시뮬레이션 시간
```

기본 TEP sampling interval은 `0.05 hour`, 즉 3분이다. Producer를 `0.1초`
간격으로 빠르게 실행해도 AI 추론은 `timestamp_hours` 기준으로 5·15·30·60분
Feature를 계산해야 한다.

## Topic이 없을 때

다음 오류는 `tep-sensor-data` topic이 없다는 뜻이다.

```text
UNKNOWN_TOPIC_OR_PART
```

Docker 컴퓨터에서 topic 목록을 확인한다.

```cmd
docker exec tep-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:19092 --list
```

topic이 없다면 생성한다.

```cmd
docker exec tep-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:19092 --create --topic tep-sensor-data --partitions 1 --replication-factor 1
```

Kafka는 원본 CSV의 장기 저장소가 아니라 실시간 전달 통로로 사용한다.
컨테이너 재생성 후 topic이 사라지면 topic을 다시 만들고 Producer를 재실행한다.

## 연결 실패 확인

개발 PC에서 Tailscale Kafka 포트를 확인한다.

```powershell
Test-NetConnection 100.127.7.26 -Port 9092
```

정상 결과:

```text
TcpTestSucceeded : True
```

포트는 열려 있는데 `_MSG_TIMED_OUT`이 발생하면 Kafka의 외부
`advertised.listeners`가 다음 주소인지 Docker 담당자에게 확인한다.

```text
EXTERNAL://100.127.7.26:9092
```

## 지원 범위

- 기본 case: `case1`~`case6`
- Sensor 메시지 Schema: `v1.0`
- Kafka message key: `trajectory_key`
- 공정 변수: `Id`·`Time` 제외 56개
- 확인 완료 trajectory: `case1::1`
- 확인 완료 메시지: 2,929개

