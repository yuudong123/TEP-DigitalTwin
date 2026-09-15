# TEP DigitalTwin Kafka 원격 연결 점검 보고

> 팀장 공유용 요약 문서  
> 점검일: 2026-09-15  
> 상태: Docker/Kafka 실행 정상, 네트워크 포트 연결 정상, 실제 메시지 송수신은 미완료

## 1. 한눈에 보는 현재 상황

Docker 컴퓨터에서 Kafka 컨테이너는 정상 실행 중이며, 개발 컴퓨터에서 Tailscale을 통한 `9092` 포트 연결도 성공했습니다.

하지만 Producer로 메시지를 전송하면 `_MSG_TIMED_OUT` 오류가 발생합니다. 현재 확인된 구성상 가장 유력한 원인은 Kafka가 클라이언트에게 알려주는 접속 주소인 `advertised.listeners`가 외부 접속용으로 설정되지 않은 것입니다.

따라서 Producer·Consumer 코드보다 **Docker 컴퓨터의 Kafka 리스너 설정을 먼저 확인하고 수정해야 합니다.**

## 2. 실행 환경

| 구분 | 내용 |
| --- | --- |
| Docker 컴퓨터 | `DESKTOP-VNS4A9P` |
| Docker 프로젝트 경로 | `D:\\TEP_DigitalTwin` |
| Kafka 이미지 | `apache/kafka:4.1.0` |
| Kafka 컨테이너 | `tep-kafka` |
| 외부 공개 포트 | `9092:9092` |
| Docker 컴퓨터 Tailscale IP | `100.127.7.26` |
| Kafka 토픽 | `tep-sensor-data` |
| 확인 대상 trajectory | `case1::1` |
| 예상 메시지 수 | 2,929개 |

## 3. 지금까지 확인한 내용

### 3.1 Docker와 Kafka 컨테이너 상태

Docker 컴퓨터에서 다음 명령으로 상태를 확인했습니다.

```console
docker ps
```

확인 결과:

- `tep-kafka` 컨테이너 실행 중
- 상태: `healthy`
- 포트: `0.0.0.0:9092->9092/tcp`

즉, Kafka 컨테이너 자체는 실행되고 있습니다.

### 3.2 개발 컴퓨터에서 포트 연결 확인

개발 컴퓨터에서 다음 명령을 실행했습니다.

```powershell
Test-NetConnection 100.127.7.26 -Port 9092
```

결과:

```text
TcpTestSucceeded : True
```

따라서 다음 항목은 정상입니다.

- 두 컴퓨터의 Tailscale 연결
- Docker 컴퓨터까지의 네트워크 경로
- Docker 컴퓨터의 `9092` 포트 접근

### 3.3 개발 컴퓨터의 Kafka 주소

개발 컴퓨터 `.env`는 다음 주소를 사용하도록 변경했습니다.

```env
KAFKA_BOOTSTRAP_SERVERS=100.127.7.26:9092
```

Consumer 실행 화면에서도 같은 주소를 읽은 것을 확인했습니다.

```text
Kafka 서버: 100.127.7.26:9092
Kafka 토픽: tep-sensor-data
확인 trajectory: case1::1
예상 수신 개수: 2929
```

### 3.4 실제 전송 결과

Producer로 실제 전송을 시도했지만 다음 오류가 반복됐습니다.

```text
_MSG_TIMED_OUT
```

따라서 현재까지 완료된 것은 포트 접속 확인이며, **2,929개 메시지의 Kafka 송수신 성공은 아직 검증되지 않았습니다.**

## 4. 확인된 현재 `compose.yaml` 구성

현재 Kafka 서비스에는 이미지, 포트, healthcheck 등이 있지만 Kafka 리스너 관련 환경변수는 없습니다.

```yaml
kafka:
  image: apache/kafka:4.1.0
  container_name: tep-kafka

  ports:
    - "9092:9092"

  healthcheck:
    test:
      [
        "CMD-SHELL",
        "/opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list > /dev/null 2>&1"
      ]
```

또한 컨테이너의 Kafka 환경변수를 조회했을 때 별도의 `KAFKA_*` 리스너 설정이 확인되지 않았습니다.

## 5. 전송 실패의 유력한 원인

Kafka 클라이언트의 연결 과정은 다음과 같습니다.

1. Producer가 `.env`의 `100.127.7.26:9092`로 최초 접속합니다.
2. Kafka 브로커가 실제 통신에 사용할 브로커 주소를 메타데이터로 반환합니다.
3. Producer가 반환받은 주소로 다시 접속하여 메시지를 전송합니다.

현재 `advertised.listeners` 외부 설정이 없기 때문에 Kafka가 `localhost:9092`처럼 원격 개발 컴퓨터에서 접근할 수 없는 주소를 반환하는 것으로 추정됩니다.

이 경우 최초 TCP 포트 검사는 성공하지만, 실제 메시지 전송 단계에서는 재접속에 실패하여 `_MSG_TIMED_OUT`이 발생할 수 있습니다.

> 아직 브로커 메타데이터를 직접 출력하여 주소를 확인한 것은 아니므로 최종 확정은 설정 적용 후 송수신 재검증이 필요합니다.

## 6. Docker 담당자가 적용할 권장 설정

Docker 내부 서비스와 Tailscale 외부 접속을 함께 사용하기 위해 리스너를 두 개로 분리합니다.

- Docker 내부용: `INTERNAL://kafka:19092`
- Tailscale 외부용: `EXTERNAL://100.127.7.26:9092`

Kafka 서비스 권장 예시는 다음과 같습니다.

코드 안에서 `#`으로 시작하는 줄은 실행되는 설정이 아니라 각 설정의 역할을 설명하는 주석입니다.

```yaml
kafka:
  # 사용할 Kafka 공식 Docker 이미지와 버전
  image: apache/kafka:4.1.0

  # docker ps에서 표시될 컨테이너 이름
  container_name: tep-kafka

  # Docker 네트워크 내부에서 kafka라는 이름으로 접근할 수 있게 설정
  hostname: kafka

  # Docker 컴퓨터의 9092 포트를 Kafka 컨테이너의 9092 포트와 연결
  # 개발 컴퓨터는 Tailscale IP인 100.127.7.26:9092로 이 포트에 접속
  ports:
    - "9092:9092"

  environment:
    # ----------------------------------------------------------
    # 1. KRaft 단일 Kafka 서버 기본 설정
    # ----------------------------------------------------------

    # 이 Kafka 서버의 고유 번호
    KAFKA_NODE_ID: 1

    # 한 컨테이너가 메시지 처리용 broker와 관리용 controller 역할을 함께 수행
    KAFKA_PROCESS_ROLES: broker,controller

    # controller 1번 노드가 kafka:29093 주소에서 동작한다고 지정
    KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka:29093

    # CONTROLLER라는 이름의 리스너를 Kafka 관리 통신에 사용
    KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER

    # ----------------------------------------------------------
    # 2. 접속 위치별 리스너 설정
    # ----------------------------------------------------------

    # Kafka가 실제로 연결을 기다릴 포트
    # INTERNAL: Docker 내부 서비스용 19092
    # EXTERNAL: Tailscale을 통한 외부 컴퓨터용 9092
    # CONTROLLER: Kafka 내부 관리 통신용 29093
    KAFKA_LISTENERS: INTERNAL://:19092,EXTERNAL://:9092,CONTROLLER://:29093

    # Kafka가 클라이언트에게 실제 접속 주소로 알려줄 값
    # Docker 내부에는 kafka:19092를 안내
    # 외부 개발 컴퓨터에는 Docker 컴퓨터의 Tailscale 주소를 안내
    KAFKA_ADVERTISED_LISTENERS: INTERNAL://kafka:19092,EXTERNAL://100.127.7.26:9092

    # 세 리스너 모두 암호화·인증 없는 PLAINTEXT 방식 사용
    # 개발·시연용 구성에 적합하며 외부 인터넷에 직접 공개하면 안 됨
    KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: INTERNAL:PLAINTEXT,EXTERNAL:PLAINTEXT,CONTROLLER:PLAINTEXT

    # Kafka 브로커 자체 통신에는 INTERNAL 리스너 사용
    KAFKA_INTER_BROKER_LISTENER_NAME: INTERNAL

    # ----------------------------------------------------------
    # 3. Kafka 서버가 한 대뿐인 환경을 위한 복제 설정
    # ----------------------------------------------------------

    # Consumer가 어디까지 읽었는지 저장하는 내부 토픽의 복제본 수
    KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1

    # Kafka 트랜잭션 상태 토픽의 복제본 수
    KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1

    # 트랜잭션 상태 기록에 필요한 최소 정상 복제본 수
    KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1

    # 최초 Consumer 그룹 연결 시 기다리지 않고 바로 리밸런싱
    KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS: 0

    # Kafka 공유 그룹 상태 토픽의 복제본 수
    KAFKA_SHARE_COORDINATOR_STATE_TOPIC_REPLICATION_FACTOR: 1

    # 공유 그룹 상태 기록에 필요한 최소 정상 복제본 수
    KAFKA_SHARE_COORDINATOR_STATE_TOPIC_MIN_ISR: 1

    # ----------------------------------------------------------
    # 4. KRaft 클러스터와 로그 저장 위치
    # ----------------------------------------------------------

    # Kafka 클러스터를 식별하는 고유 ID
    # 기존 Kafka 데이터를 유지해야 한다면 기존 클러스터 ID 확인 필요
    CLUSTER_ID: 4L6g3nShT-eMCtK--X86sw

    # Kafka 토픽과 메시지 로그가 컨테이너 내부에 저장되는 경로
    KAFKA_LOG_DIRS: /tmp/kraft-combined-logs

  healthcheck:
    # Docker가 Kafka 정상 여부를 확인하는 명령
    # Docker 내부용 19092 포트에서 토픽 목록 조회가 되는지 검사
    test:
      [
        "CMD-SHELL",
        "/opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:19092 --list > /dev/null 2>&1"
      ]

    # 10초마다 검사하고 한 번의 검사는 최대 5초 동안 대기
    interval: 10s
    timeout: 5s

    # 최대 10번까지 재시도
    retries: 10

    # 컨테이너 시작 후 Kafka가 준비될 수 있도록 최초 20초 대기
    start_period: 20s

  # 오류나 컴퓨터 재부팅으로 정지되면 컨테이너를 다시 시작
  restart: unless-stopped

  # api, inference, monitor와 같은 Docker 네트워크 사용
  networks:
    - tep-network
```

## 7. 다른 Docker 서비스에서 함께 바꿀 부분

`api`, `inference`, `monitor`는 Docker 네트워크 내부에서 Kafka에 접속하므로 각각 다음 주소를 사용해야 합니다.

```yaml
environment:
  KAFKA_BOOTSTRAP_SERVERS: kafka:19092
```

최종 주소 구분은 다음과 같습니다.

| 실행 위치 | 사용할 Kafka 주소 |
| --- | --- |
| Docker 내부 `api` | `kafka:19092` |
| Docker 내부 `inference` | `kafka:19092` |
| Docker 내부 `monitor` | `kafka:19092` |
| 개발 컴퓨터 Producer·Consumer | `100.127.7.26:9092` |
| Docker 컴퓨터에서 직접 실행하는 Producer·Consumer | `100.127.7.26:9092` |

Tailscale을 계속 사용할 예정이므로 개발 컴퓨터의 `.env`는 다음과 같이 유지합니다.

```env
KAFKA_BOOTSTRAP_SERVERS=100.127.7.26:9092
```

## 8. Producer·Consumer 코드 변경 여부

현재 전송 실패 원인을 해결하기 위해 Producer나 Consumer 로직을 변경할 필요는 없습니다.

| 파일 | 현재 판단 |
| --- | --- |
| `kafka/producer.py` | Kafka 연결 문제 때문에 수정할 필요 없음 |
| `kafka/consumer.py` | Kafka 연결 문제 때문에 수정할 필요 없음 |
| 개발 컴퓨터 `.env` | `100.127.7.26:9092` 유지 |
| Docker `compose.yaml` | 외부·내부 리스너 설정 필요 |

Producer가 콜백 전송 실패 횟수를 최종 결과에 집계하도록 개선하는 작업은 가능하지만, 이는 현재 Kafka 연결 문제와 별개의 후속 개선사항입니다.

## 9. 적용 시 주의사항

- 설정 적용 과정에서 Kafka 컨테이너가 재생성될 수 있습니다.
- 현재 Kafka에 영구 볼륨이 없다면 기존 토픽과 메시지가 사라질 수 있습니다.
- 적용 전에 보존해야 할 Kafka 데이터가 있는지 확인해야 합니다.
- `100.127.7.26`이 Docker 컴퓨터의 현재 Tailscale IP인지 다시 확인해야 합니다.
- 팀원 컴퓨터도 같은 Tailscale 네트워크에 접속돼 있어야 합니다.

## 10. 설정 적용 후 검증 순서

### 10.1 Docker 컴퓨터

1. Kafka 설정 적용
2. Kafka 컨테이너가 `healthy`인지 확인
3. 토픽 목록 또는 `tep-sensor-data` 토픽 존재 여부 확인

### 10.2 개발 컴퓨터

먼저 포트를 다시 확인합니다.

```powershell
Test-NetConnection 100.127.7.26 -Port 9092
```

그다음 Consumer를 먼저 실행하고 대기시킵니다.

```powershell
python .\kafka\consumer.py --case case1 --id 1 --expected-count 2929
```

별도의 PowerShell에서 Producer를 실행합니다.

```powershell
python .\kafka\producer.py --case case1 --id 1 --send
```

> 실제 명령 옵션은 현재 작성된 `producer.py`, `consumer.py`의 옵션 이름과 다시 대조해야 합니다.

### 10.3 최종 성공 조건

- Producer 전송 실패 `0건`
- Consumer 수신 `2,929건`
- `trajectory_key = case1::1`
- `sequence = 0 ~ 2928` 연속
- 각 메시지의 공정 변수 `56개`
- 메시지 스키마 검증 오류 `0건`

## 11. 팀장 확인 요청사항

1. Kafka에 외부 Tailscale 접속용 `advertised.listeners`를 적용해도 되는지
2. 내부 Docker 서비스 주소를 `kafka:19092`로 변경해도 되는지
3. Kafka 컨테이너 재생성 전에 보존해야 할 토픽이나 메시지가 있는지
4. 설정 적용 후 `case1::1`의 2,929개 전체 송수신 검증을 진행해도 되는지

## 12. 결론

현재 Docker 실행, Kafka healthcheck, Tailscale 연결, `9092` 포트 접근까지는 정상입니다. 그러나 실제 Kafka 메시지 전송은 `_MSG_TIMED_OUT`으로 실패하고 있습니다.

우선 Docker 담당자가 Kafka의 내부·외부 리스너와 `advertised.listeners`를 설정한 뒤, Consumer를 먼저 실행하고 Producer를 실행하여 2,929개 전체 송수신을 다시 검증해야 합니다.