# B 운영 검증 — 2026-09-30

독립 `feat/ops-verification`은 origin/dev `0380467`에서 시작했다.
17번 미병합 변경을 포함하지 않는다. 자동 재학습·모델 교체·API 구현은 범위 밖이다.

| 작업 | 이번 확인/구현 | 남은 범위 |
|---|---|---|
| 08 저장·복구 | 별도 Kafka 재생성 후 topic·메시지·commit offset 유지, 집컴 dev 서비스 복구 | 집컴 재부팅·로그인 복구 |
| 09 배포 | ValidateOnly, 단계별 보고서, 집컴 Python/Web 검증 | API 포함 전체 배포 acceptance |
| 10 Jenkins | workspace 배포 스크립트·보고서 archive 저장, 자동 시작 작업 Running | PR 병합 후 실제 dev Poll SCM build |
| 16/22 품질 | 읽기 전용 runtime 감사·6개 신규 테스트 | API→Web/Unity 전체 live chain |
| 20 모델 적용 | Production 모델 유지 | 19 평가·승격/rollback 계약 필요 |
| 21 | 번호만 있고 요구사항 문서 없음 | 요구사항 확정 필요 |

## 영구 저장 실증

UUID container/volume과 별도 loopback port의 Kafka에 synthetic sequence 0을 commit.
테스트 broker를 정상 종료·삭제 후 같은 테스트 볼륨으로 새 컨테이너를 만들었다.
topic·메시지 유지 및 sequence 1,2부터 재개 확인.
원본: `kafka-persistence-drill-2026-09-30.json`. 테스트 container/volume만 삭제했다.
새 볼륨 uid 1000 소유권이 필요해 첫 준비 실패 후 이를 보완하고 재검증했다.
운영 tep-kafka/tep-kafka-data는 이 drill에서 중지·삭제·설정 변경하지 않았다.
이 결과는 집컴 재부팅 실증이 아니다.

## 배포·실행 상태

격리 dev export + 새 배포 코드에서 ValidateOnly 실제 실행:
Python 39 passed, compileall/pip check 및 npm ci/lint/build 통과.
공통 33개 + 새 운영 테스트 6개이며 17번 브랜치 테스트와 합산하지 않는다.
Validation 보고서 commit은 격리 export의 임시 Git revision이며 운영 배포 revision이 아니다.

집컴 깨끗한 dev `0380467`에서 기존 Inference/Monitor 이미지를 빌드·복구.
Kafka healthy, 구현된 서비스 Running/restart 0, Monitor 재학습 false 확인.
원본: `runtime-audit-restored-2026-09-30.json`. API 미구현으로 full_runtime_ready=false.
17번 후보는 운영에 적용하지 않았으므로 컨테이너 준비와 통계 기준 승인을 구분한다.

## Jenkins

서비스 및 TEP-Jenkins-Agent Running, 로그인 trigger / Interactive / Limited 확인.
사용자 승인 후 Inline Script에 workspace 도구 경로와 보고서 archive를 저장했다.
dev/H/2/Groovy Sandbox/DisableRemotePoll 및 기존 접근권한은 유지했다.
저장 Script와 새 Jenkinsfile SHA 일치:
`aaea1ca3aa525cef4e177c9f1346cc83343b373598af065373acbda48daf50e0`.
최근 build #23 UNSTABLE. 저장 후 새 dev 변경으로 실제 자동 배포된 증적은 아직 없다.
비밀번호·secret은 산출물에 포함하지 않았다.

## 완료 경계

코드·사전검증과 운영 컨테이너 준비를 구분한다. dev 강제 push/PR 강제 병합,
자동 재학습, 무단 모델 교체, 인증 우회, 집컴 재부팅은 수행하지 않았다.
