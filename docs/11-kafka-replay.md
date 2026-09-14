# Kafka 실시간 데이터 재생

> 업데이트 기준: 2026-09-14  
> 현재 상태: Producer·Consumer 구현 및 로컬 실행 진입 확인 완료, 실제 Kafka 송수신 미검증

## 1. 목적

TEP Run-to-Failure CSV에서 사용자가 선택한 `case`와 `Id`의 trajectory를
시간순으로 읽어 Kafka sensor topic에 실시간 데이터처럼 재생한다.

이 작업의 출력 메시지는 이후 12번 실시간 추론 서비스의 입력으로 사용한다.

## 2. 작업 범위

11번 작업에서는 다음 기능을 구현한다.

- `case1`~`case6` 중 재생할 case 선택
- 선택한 case 안에서 trajectory `Id` 선택
- 원본 데이터를 `Time` 오름차순으로 전송
- 재생 간격 설정
- Kafka 메시지 생성 및 발행
- 확인용 Consumer를 통한 메시지 수신 검증
- 전송 성공·실패 로그 기록

AI 추론, RUL 계산 및 고장 위험 판단은 12번 작업에서 구현한다.

## 3. 데이터 기준

기본 재생 데이터는 다음 파일을 사용한다.

```text
data/raw/case1.csv
data/raw/case2.csv
data/raw/case3.csv
data/raw/case4.csv
data/raw/case5.csv
data/raw/case6.csv
```

`case5_1.csv`와 `case7.csv`는 공식 6개 시나리오에 포함되지 않는 추가 실험
데이터이므로 기본 재생 대상에서 제외하고 별도 검증용으로 보관한다.

각 CSV는 다음 구조를 갖는다.

- `Id`: case 내부의 독립 Run-to-Failure trajectory 번호
- `Time`: trajectory 시작 후 경과시간. 단위는 hour
- 나머지 56개 컬럼: 공정 측정값, 조작 변수 및 추가 공정 상태 변수
- 기본 sampling interval: `0.05 hour`, 즉 3분

고유 trajectory 식별자는 다음 형식을 사용한다.

```text
case명::Id
```

예:

```text
case1::17
```

## 4. 구현 위치

Kafka 재생 관련 파일은 프로젝트 루트의 `kafka/`에 둔다.

```text
kafka/
├─ producer.py
├─ message_schema.py      # 구현 및 1차 검증 완료
├─ consumer.py
└─ README.md
```

- `producer.py`: CSV 선택, trajectory 필터링 및 Kafka 발행
- `message_schema.py`: Kafka sensor 메시지 생성 및 검증
- `consumer.py`: 수신 메시지의 구조, key, 개수와 순서 확인
- `README.md`: 실행 방법과 메시지 예시

## 5. Kafka 설정

기존 공통 환경변수를 사용한다.

```text
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_SENSOR_TOPIC=tep-sensor-data
TEP_REPLAY_INTERVAL_SECONDS=0.1
```

Kafka message key는 `trajectory_key`를 사용한다. 동일 trajectory의 메시지가
같은 partition에 배치되어 순서를 유지할 수 있도록 하기 위한 규칙이다.

루트 `.env`의 기존 `KAFKA_CONSUMER_GROUP=inference-service`는 향후 AI 추론
서비스에서 사용한다. 확인용 `consumer.py`는 별도의 환경변수를 추가하지 않고
코드 내부 기본값 `tep-replay-check`를 사용한다. 이를 통해 추론 서비스와
확인용 Consumer가 메시지를 나눠 갖지 않도록 group을 분리한다.

확인용 Consumer는 실행할 때마다 고유 시각을 group id 뒤에 붙이며, Consumer
실행 이후 들어오는 새 메시지를 받도록 `latest`에서 시작한다. 따라서 기존
`.env`와 `.env.example`에 `KAFKA_CHECK_CONSUMER_GROUP`을 추가하지 않아도 된다.

Python Kafka client는 다음 버전을 로컬 가상환경에 설치해 확인했다.

```text
confluent-kafka==2.15.0
```

재현 가능한 설치를 위해 이 의존성은 프로젝트 `requirements.txt`에도 추가해야
한다.

개발 PC에서는 Kafka 코드를 작성하고, Docker Compose와 Kafka의 실제
실행은 별도의 컴퓨터에서 진행한다. 따라서 실제 송수신 검증은
Producer와 Consumer 구현 후 Docker 실행 컴퓨터에서 수행한다.

## 6. Sensor 메시지 Schema v1.0

11번 작업의 최초 메시지 schema는 다음과 같이 확정한다.

```json
{
  "schema_version": "1.0",
  "event_type": "tep_sensor_reading",
  "trajectory_key": "case1::1",
  "case": "case1",
  "trajectory_id": 1,
  "sequence": 0,
  "timestamp_hours": 0.0,
  "replayed_at": "2026-09-14T12:00:00+09:00",
  "values": {
    "D feed": 0.0,
    "Reactor Pressure": 0.0,
    "Reactor Level": 0.0,
    "Reactor Temperature": 0.0
  }
}
```

실제 메시지의 `values`에는 `Id`와 `Time`을 제외한 56개 공정 변수를 모두
포함한다. 컬럼 이름은 원본 CSV의 이름을 변경하지 않고 그대로 사용한다.

`sequence`는 trajectory의 첫 행에서 `0`으로 시작하고 메시지를 한 개
발행할 때마다 1씩 증가한다.

## 7. 필드 정의

| 필드              | 형식    | 설명                                             |
| ----------------- | ------- | ------------------------------------------------ |
| `schema_version`  | string  | Kafka sensor 메시지 구조의 버전                  |
| `event_type`      | string  | 메시지 종류. v1.0에서는 `tep_sensor_reading`     |
| `trajectory_key`  | string  | case와 Id를 결합한 고유 trajectory 식별자        |
| `case`            | string  | 원본 TEP 열화 시나리오 이름                      |
| `trajectory_id`   | integer | 해당 case 안의 독립 시뮬레이션 번호              |
| `sequence`        | integer | trajectory 내부의 메시지 전송 순번               |
| `timestamp_hours` | number  | 원본 CSV의 `Time`. 단위는 hour                   |
| `replayed_at`     | string  | Kafka에 메시지를 발행한 실제 시각. ISO 8601 형식 |
| `values`          | object  | 해당 시점의 공정 변수 56개와 값                  |

`timestamp_hours`는 시뮬레이션 시간이고 `replayed_at`은 실제 전송 시각이므로
서로 다른 목적으로 사용한다.

## 8. Schema 변경 규칙

- 기존 필드를 유지하면서 선택 필드를 추가하면 minor version을 올린다.
- 기존 필드를 삭제하거나 이름·구조를 변경하면 major version을 올린다.
- 변경 전 12번 Inference, 17번 Drift, Web 및 Unity 담당자와 공유한다.
- 변경된 필드와 호환성 영향을 이 문서에 기록한다.

예:

```text
선택 필드 추가: 1.0 → 1.1
기존 구조 변경: 1.x → 2.0
```

## 9. 처리 흐름

### 9.1 Producer

```text
case와 Id 입력
→ 대상 CSV 확인
→ 선택한 Id 필터링
→ Time 오름차순 정렬
→ 한 행을 Schema v1.0 메시지로 변환
→ trajectory_key를 Kafka key로 지정
→ tep-sensor-data topic에 발행
→ 설정한 interval만큼 대기
→ trajectory 마지막 행까지 반복
```

`producer.py`는 `case1.csv` 전용 파일이 아니다. 하나의 공통 Producer가
`--case case1`부터 `--case case6`까지 지원하며, 한 번 실행할 때 선택한 case의
trajectory Id 한 개를 재생한다. 모든 trajectory를 동시에 섞어 발행하지 않는다.

`--send`가 없으면 Kafka에 연결하지 않고 일부 메시지만 출력하는 미리보기
모드로 동작한다. 실제 발행은 `--send`를 명시한 경우에만 수행한다.

### 9.2 Consumer

```text
tep-sensor-data topic 구독
→ JSON 역직렬화
→ 대상 trajectory_key 필터링
→ Sensor Schema v1.0 검증
→ Kafka message key 일치 확인
→ sequence 연속성 확인
→ 수신 개수 집계
→ expected-count 도달 또는 idle-timeout 시 종료
```

Consumer는 `latest`에서 시작하므로 실제 검증 시 반드시 Consumer를 먼저
실행하고 수신 대기 문구가 나온 뒤 Producer를 실행한다.

## 10. 검증 항목과 현재 결과

| 검증 항목                           | 상태      | 결과                                                  |
| ----------------------------------- | --------- | ----------------------------------------------------- |
| 기본 case 파일 존재                 | 완료      | `case1.csv`~`case6.csv` 확인                          |
| CSV 컬럼 구조                       | 완료      | 전체 58개, `Id`·`Time` 제외 공정 변수 56개            |
| `message_schema.py` Python 문법     | 완료      | `python -m py_compile` 통과                           |
| 실제 CSV 1행 메시지 변환            | 완료      | `case1::1`, `sequence=0`, `timestamp_hours=0.0`       |
| `values` 공정 변수 개수             | 완료      | 56개 확인                                             |
| `confluent-kafka` 설치              | 완료      | 가상환경에서 `2.15.0` import 확인                     |
| Producer Python 문법                | 완료      | `python -m py_compile` 통과                           |
| 선택한 Id 전체 필터링·정렬          | 완료      | `case1::1` 2,929행, Time `0`~`146.4`                  |
| Producer 미리보기                   | 완료      | sequence `0, 1, 2`, Time `0, 0.05, 0.1`, values 56개  |
| Producer 실제 발행 경로 진입        | 완료      | `--send` 실행 및 `localhost:9092` 연결 시도 확인      |
| Consumer 실행 진입                  | 완료      | topic 구독 및 `localhost:9092` 연결 시도 확인         |
| `sequence` 연속 증가                | 부분 완료 | 생성은 확인, 실제 수신 순서는 Kafka 송수신 후 확인    |
| CSV 행 수와 Consumer 수신 개수 일치 | 미검증    | Kafka 송수신 후 확인                                  |
| Kafka 연결 실패 로그                | 완료      | 브로커 미실행 상태에서 connection failure 확인        |
| Kafka 실제 송수신                   | 미검증    | Docker 실행 컴퓨터에서 확인 필요                      |
| Producer 성공·실패 최종 집계        | 보완 필요 | delivery callback 실패 건수를 최종 결과에 반영해야 함 |

## 11. 현재 상태

설계 확정:

- 구현 위치: 루트 `kafka/`
- 기본 데이터: `case1`~`case6`
- Sensor topic: `tep-sensor-data`
- Kafka message key: `trajectory_key`
- Sensor 메시지 schema: `v1.0`
- 메시지 필드와 변경 규칙

구현 및 검증 완료:

- 루트 `kafka/` 폴더 생성
- `kafka/message_schema.py` 구현
- CSV 값의 유한한 실수 변환 및 NaN·무한대 검증
- Sensor Schema v1.0 필수 필드 검증
- `trajectory_key`, case, sequence, 시각, 공정 변수 개수 검증
- `python -m py_compile .\kafka\message_schema.py` 문법 검사 통과
- `case1.csv` 첫 행으로 메시지 생성 통과
- `kafka/producer.py` 구현
- `case1`~`case6` 공통 선택, trajectory Id 필터링 및 Time 정렬 구현
- Kafka 미전송 미리보기와 `--send` 실제 발행 모드 분리
- `trajectory_key`를 Kafka key로 사용하는 JSON 발행 구현
- 환경변수 기반 bootstrap server, sensor topic, interval 적용
- `acks=all`, idempotence, delivery callback, poll 및 flush 적용
- `case1::1` 전체 2,929행 필터링 확인
- Time 범위 `0`~`146.4`, 기본 간격 `0.05 hour` 확인
- 미리보기 sequence `0, 1, 2` 및 values 56개 확인
- `kafka/consumer.py` 구현
- Sensor Schema v1.0, Kafka key, sequence, 수신 개수 검증 구현
- 예상 개수 도달 및 idle timeout 종료 조건 구현
- 확인용 Consumer group을 추론 서비스 group과 분리
- 확인용 group은 별도 환경변수 없이 코드 기본값 `tep-replay-check` 사용
- 기존 `.env`의 `KAFKA_CONSUMER_GROUP=inference-service` 유지
- 가상환경에 `confluent-kafka==2.15.0` 설치 및 import 확인
- Producer와 Consumer 모두 실제 실행 경로 진입 확인

실제 실행 결과:

- 개발 PC의 `.env` 기본값에 따라 `localhost:9092`로 연결을 시도함
- 해당 PC에서 Kafka broker가 실행되지 않아 connection failure 발생
- Producer 메시지는 broker에 전달되지 않고 `_MSG_TIMED_OUT` 처리됨
- Consumer도 broker에 연결되지 않아 실제 메시지를 수신하지 못함
- 이는 CSV 처리, Schema 또는 Python 문법 오류가 아니라 Kafka 미실행 상태에
  따른 결과임

남은 작업:

- `confluent-kafka==2.15.0`을 `requirements.txt`에 추가
- Producer delivery callback의 성공·실패 건수를 집계하여 최종 결과에 반영
- 2026-09-15 Docker 실행 컴퓨터에서 Kafka broker 기동 상태 확인
- 실제 Kafka 송수신 검증
- Producer 발행 2,929개와 Consumer 수신 2,929개 일치 확인
- Consumer sequence `0`~`2928` 연속성 확인
- 장애 및 재시도 검증
- `kafka/README.md` 작성

현재 11번 작업은 **Sensor 메시지 Schema, Producer, 확인용 Consumer 구현과
로컬 데이터 검증까지 완료**된 상태다. Kafka broker가 없는 개발 PC에서 연결
실패 동작까지 확인했지만, 실제 송수신은 완료되지 않았으므로 11번 전체를
완료로 표시하지 않는다. Docker 기반 실제 송수신 검증은 2026-09-15에
진행한다.

## 12. 실행 명령

### 12.1 로컬 미리보기

```powershell
.\.venv\Scripts\Activate.ps1
python .\kafka\producer.py --case case1 --id 1 --limit 3
```

### 12.2 Docker 실행 컴퓨터에서 실제 송수신

첫 번째 PowerShell에서 Consumer를 먼저 실행한다.

```powershell
.\.venv\Scripts\Activate.ps1
python .\kafka\consumer.py --case case1 --id 1 --expected-count 2929
```

Consumer가 수신 대기 상태가 된 뒤 두 번째 PowerShell에서 Producer를 실행한다.

```powershell
.\.venv\Scripts\Activate.ps1
python .\kafka\producer.py --case case1 --id 1 --interval 0.1 --send
```

두 PowerShell 모두 각각 가상환경을 활성화해야 한다. Kafka가 같은 컴퓨터의
Docker에서 호스트 포트 `9092`로 노출되면 `localhost:9092`를 사용한다.
