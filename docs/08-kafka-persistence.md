# Kafka 영구 저장 (2026-09-23)

Kafka 데이터 디렉터리 `/tmp/kraft-combined-logs`를 외부 Docker 볼륨
`tep-kafka-data`에 연결한다. 이름에 tmp가 있어도 실제 데이터는 볼륨에 보존된다.
토픽, 메시지, consumer offset, KRaft 메타데이터가 컨테이너 재생성 후 유지된다.
Compose 프로젝트가 바뀌어도 같은 볼륨을 사용하며 `compose down -v`의 삭제 대상에서 제외된다.
Docker 볼륨 자체 삭제·Docker 데이터 초기화는 보호하지 않으며 메시지 retention 정책은 별도다.

## 기존 브로커 이전

배포 전에 Docker 호스트에서 `deploy/migrate-kafka-storage.ps1`을 실행한다.
기존 브로커를 정상 종료하고 logs/kafka-backup-시각 폴더에 전체 데이터를 복사한 후
새 볼륨에 이전한다. 기존 대상 볼륨이 있으면 덮어쓰지 않고 중단한다.
성공 후 기존 브로커는 중지 상태이므로 새 compose로 Kafka를 즉시 시작한다.
실패 시 기존 브로커를 다시 시작하며 백업과 생성된 볼륨은 조사용으로 보존한다.

새 설치처럼 기존 데이터가 전혀 없는 경우에만 `docker volume create tep-kafka-data`로
빈 볼륨을 준비하고 시작한다. 기존 데이터가 있을 때 이 절차를 사용하면 안 된다.

## 검증

토픽 목록, 메시지 offset, 검증 메시지를 기록하고 컨테이너를 강제 재생성한 뒤
같은 데이터가 조회되는지 확인한다. 백업은 검증 후에도 보존한다.

## 의존성·추론 통합

비어 있던 requirements.txt를 복원했다. 추론 이미지에 kafka 패키지를 포함하고,
Jenkins 배포 시 호스트 테스트 실행 전에 의존성을 설치한다.
추론 단위 테스트는 원본 CSV 대신 고정된 합성 입력을 사용한다.
실제 원본 데이터의 Feature 일치 검증은 별도로
`python -m src.inference.validate_temporal --case case1 --id 1 --row 20`을 실행한다.
