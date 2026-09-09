# TEP 예지보전 개인 프로젝트 작업 체크리스트

> 일정 없이 **선후관계 기준**으로 진행하는 개인 프로젝트 작업 문서  
> 각 항목은 완료 시 `- [ ]` → `- [x]` 로 체크

---

## 1. 프로젝트 기획 확정

- [x] 프로젝트 목적 정의
- [x] TEP 기반 예지보전 시스템의 핵심 기능 정의
  - [x] 공정 상태 실시간 모니터링
  - [x] 고장 위험 예측
  - [x] 잔여수명(RUL) 예측
  - [x] 데이터 드리프트 감지
  - [x] 자동 재학습
  - [x] 후보 모델 평가 및 모델 교체
- [x] 주요 설비 범위 확정
  - [x] 반응기
  - [x] 분리기
  - [x] 정제기
- [x] 전체 사용자 흐름 정의
- [x] 기술 스택 1차 확정
- [x] 프로젝트 한 문장 설명 작성

**완료 기준**
- [x] 프로젝트가 무엇을 만들고 왜 만드는지 한 문장으로 설명 가능

---

## 2. TEP 데이터 구조 및 고장 시나리오 분석

- [x] TEP 데이터셋 공식 문서 정리
- [x] 8개 CSV 파일의 역할 확인
- [x] 각 `Id`가 하나의 독립 Run-to-Failure trajectory임을 문서화
- [x] `Time` 단위 및 3분 샘플링 간격 확인
- [x] 전체 변수 목록 정리
- [x] 변수 역할 분류
  - [x] 측정 센서
  - [x] 조작 변수
  - [x] 설정값/제어값 구분
  - [x] 조성/공정 보조 변수
- [x] 설비별 변수 매핑
  - [x] 반응기 관련 변수
  - [x] 분리기 관련 변수
  - [x] 정제기 관련 변수
- [x] 운전 모드 의미 확인
- [x] 열화 시나리오 의미 확인
- [x] case 파일과 열화/운전조건의 관계 확인
- [x] 데이터 누수 가능성이 있는 변수 후보 정리
- [x] EOL 정의 확정
- [x] RUL 계산식 확정

**완료 기준**
- [x] 각 주요 컬럼이 무엇을 의미하는지 설명 가능
- [x] 모델에 넣어도 되는 변수와 제외할 변수가 구분됨

---

## 3. 모델 검증용 데이터셋 구축

- [x] trajectory 단위 데이터 분리 방식 확정
- [x] Train / Validation / Test 분리
- [x] 동일 trajectory의 train/test 중복 방지
- [x] Leave-One-Case-Out 평가 구조 유지
- [x] RUL target 생성
- [x] 고장 위험 target 생성
  - [x] 4시간 이내
  - [x] 2시간 이내
  - [x] 1시간 이내
- [x] 결측치 검사
- [x] 중복 timestamp 검사
- [x] sampling interval 검사
- [x] 이상값 검사
- [x] 학습 feature schema 확정

**완료 기준**
- [x] 데이터 누수 없이 재현 가능한 학습/평가 데이터 생성 가능

---

## 4. AI Baseline 모델 개발

- [x] NVIDIA CUDA / XGBoost GPU 환경 확인
- [x] RUL 회귀 Baseline 구현
- [x] 고장 위험 분류 Baseline 구현
  - [x] 4시간 모델
  - [x] 2시간 모델
  - [x] 1시간 모델
- [x] Validation 기반 threshold 결정 방식 구현
- [x] 모델 평가 지표 계산
  - [x] MAE
  - [x] R²
  - [x] Average Precision
  - [x] ROC-AUC
  - [x] Recall
  - [x] False Positive Rate
- [x] Event 단위 탐지율 계산
- [x] 최초 경고 lead time 계산
- [x] case별 성능 비교

**완료 기준**
- [x] unseen trajectory에서 모델 성능 확인
- [x] unseen case에서도 모델 일반화 성능 확인

---

## 5. 시계열 Feature 모델 개발

- [x] 단일 시점 Baseline 결과 저장
- [x] 과거 시계열 feature 설계
  - [x] 이동평균
  - [x] 표준편차
  - [x] 변화량
  - [x] 변화속도
  - [x] 기울기
  - [x] 최대값
  - [x] 최소값
- [x] 과거 5분 feature
- [x] 과거 15분 feature
- [x] 과거 30분 feature
- [x] 과거 60분 feature
- [x] 미래 데이터가 feature에 섞이지 않는지 검사
- [x] 시계열 feature 모델 학습
- [x] Baseline과 성능 비교
- [x] 복잡도 대비 성능 향상 판단

**완료 기준**
- [x] 시계열 feature 사용 여부를 성능 근거로 결정

---

## 6. 최종 모델 선정 및 설명 기능

- [x] 최종 RUL 모델 선정
- [x] 최종 고장 위험 모델 선정
- [x] 최종 threshold 확정
- [x] 모델 저장 형식 확정
- [x] 모델 버전 정보 저장
- [x] feature 목록 저장
- [x] SHAP 또는 feature importance 구현
- [x] 주요 위험 요인 출력 형식 정의
- [x] 예측 결과 schema 정의

**완료 기준**
- [x] 한 입력에 대해 RUL, 위험도, 상태, 주요 원인을 함께 출력 가능

---

## 7. 프로젝트 기본 구조 생성

- [x] 새 GitHub 저장소 생성
- [x] 기본 branch 전략 결정
- [x] 프로젝트 디렉터리 구조 생성
- [x] `.gitignore` 작성
- [x] `.env` 구조 정의
- [x] Python requirements 정리
- [x] 공통 config 구조 작성
- [x] 로그 저장 구조 정의
- [x] README 기본 골격 작성

**완료 기준**
- [x] 새 저장소를 clone한 뒤 기본 개발환경을 재현 가능

---

## 8. Docker 개발환경 구축

- [x] FastAPI Dockerfile 작성
- [x] Kafka Docker 구성
- [x] inference Dockerfile 작성
- [x] monitor Dockerfile 작성
- [x] Docker Compose 작성
- [x] 서비스 간 네트워크 설정
- [x] 환경변수 관리
- [x] 볼륨 구조 설정
- [x] 모델 파일 공유 방식 결정
- [x] 컨테이너 로그 확인 방식 결정

**완료 기준**
- [ ] `docker compose up -d`로 최소 시스템 실행 가능

---

## 9. 개발서버 수동 배포

- [ ] Oracle 개발서버 준비
- [ ] 저장소 clone
- [ ] 서버 `.env` 설정
- [ ] Docker/Compose 설치 확인
- [ ] Docker image build
- [ ] Compose 실행
- [ ] FastAPI 접근 확인
- [ ] Kafka 접근 확인
- [ ] 서버 재부팅 후 서비스 동작 확인

**완료 기준**
- [ ] 사람이 직접 배포하면 개발서버가 정상적으로 올라옴

---

## 10. Jenkins 기본 CI/CD 구축

- [ ] Jenkins 설치 및 실행
- [ ] GitHub 저장소 연동
- [ ] GitHub Webhook 설정
- [ ] Jenkinsfile 작성
- [ ] `dev` push 감지
- [ ] 최신 코드 반영
- [ ] Docker build 자동화
- [ ] Docker Compose 재배포 자동화
- [ ] 배포 로그 확인
- [ ] 빌드 실패 처리
- [ ] 필요 시 pytest 선행 실행

**완료 기준**
- [ ] Git push만으로 개발서버 코드가 자동 반영됨

---

## 11. Kafka 실시간 데이터 재생 구현

- [ ] Kafka topic 설계
- [ ] 메시지 schema 정의
- [ ] TEP trajectory 선택 기능
- [ ] case 선택 기능
- [ ] timestamp 처리
- [ ] CSV 순차 재생 Producer 구현
- [ ] 재생 속도 설정
- [ ] 시작/중지 기능
- [ ] 실제 3분 간격을 데모 시간으로 압축
- [ ] Kafka 메시지 수신 확인

**완료 기준**
- [ ] 선택한 trajectory가 시간순으로 Kafka에 정상 재생됨

---

## 12. 실시간 추론 서비스 구현

- [ ] Kafka Consumer 구현
- [ ] 실시간 feature 전처리
- [ ] 최종 모델 로딩
- [ ] 실시간 RUL 추론
- [ ] 실시간 고장 위험 추론
- [ ] threshold 적용
- [ ] 상태 단계 정의
  - [ ] NORMAL
  - [ ] CAUTION
  - [ ] WARNING
  - [ ] CRITICAL
- [ ] 주요 위험 요인 계산
- [ ] 최신 추론 결과 저장

**완료 기준**
- [ ] Kafka 센서 입력이 들어오면 자동으로 AI 결과 생성

---

## 13. FastAPI 구축

- [ ] API 기본 구조 생성
- [ ] 현재 공정 상태 API
- [ ] 현재 센서값 API
- [ ] RUL API
- [ ] 고장 위험도 API
- [ ] 반응기 상태 API
- [ ] 분리기 상태 API
- [ ] 정제기 상태 API
- [ ] 주요 영향 변수 API
- [ ] trajectory 정보 API
- [ ] 오류 응답 형식 통일

**완료 기준**
- [ ] 외부 화면에서 필요한 실시간 정보를 API로 모두 조회 가능

---

## 14. 기본 Web 모니터링 화면

- [ ] 현재 RUL 표시
- [ ] 현재 고장 위험도 표시
- [ ] 전체 공정 상태 표시
- [ ] 주요 센서 그래프
- [ ] 반응기 상태 표시
- [ ] 분리기 상태 표시
- [ ] 정제기 상태 표시
- [ ] 주요 위험 요인 표시
- [ ] FastAPI 실시간 연결

**완료 기준**
- [ ] Unity 없이도 전체 데이터 흐름을 웹에서 확인 가능

---

## 15. Unity 디지털트윈 개발

- [ ] 전체 화학공정 레이아웃 설계
- [ ] 반응기 3D 모델 구성
- [ ] 분리기 3D 모델 구성
- [ ] 정제기 3D 모델 구성
- [ ] 배관 연결
- [ ] 설비별 상태 색상 정의
- [ ] NORMAL 표현
- [ ] CAUTION 표현
- [ ] WARNING 표현
- [ ] CRITICAL 표현
- [ ] 설비 클릭 기능
- [ ] 상세 센서 UI
- [ ] RUL 표시
- [ ] 고장 위험도 표시
- [ ] API 연결
- [ ] 실시간 상태 갱신

**완료 기준**
- [ ] AI 결과에 따라 공정 3D 상태가 실시간으로 변화

---

## 16. 전체 실시간 시스템 1차 통합

- [ ] TEP CSV → Kafka 연결
- [ ] Kafka → inference 연결
- [ ] inference → AI model 연결
- [ ] AI 결과 → FastAPI 연결
- [ ] FastAPI → Web 연결
- [ ] FastAPI → Unity 연결
- [ ] timestamp 순서 확인
- [ ] 센서 mapping 확인
- [ ] 모델 입력 schema 확인
- [ ] Kafka 재연결 처리
- [ ] 서비스 재시작 처리

**완료 기준**
- [ ] 데이터 입력부터 Unity/Web 출력까지 전체 체인이 연속 동작

---

## 17. 데이터 드리프트 감지 구현

- [ ] 기준 정상 데이터 정의
- [ ] 드리프트 대상 sensor 선정
- [ ] KS Test 구현
- [ ] PSI 또는 추가 지표 검토
- [ ] 센서별 drift 판단
- [ ] 여러 센서 종합 drift 기준 정의
- [ ] 지속시간 조건 정의
- [ ] 고장 위험과 drift 분리 로직 구현
- [ ] Drift event 로그 저장

핵심 정책:

```text
고장 위험 높음
→ 열화/고장 후보
→ 재학습 금지

고장 위험 낮음
+
정상 상태 분포가 지속적으로 변화
→ Drift 후보
```

**완료 기준**
- [ ] 정상적인 분포 변화와 고장 위험을 구분하여 drift 판단 가능

---

## 18. Python 자동 재학습 구현

- [ ] `monitor.py`와 재학습 연결
- [ ] 재학습 trigger 조건 정의
- [ ] 재학습 데이터 생성
- [ ] XGBoost GPU 학습
- [ ] candidate model 저장
- [ ] 재학습 로그 저장
- [ ] 재학습 실패 처리
- [ ] 중복 재학습 방지

**완료 기준**
- [ ] Drift 조건 충족 시 사람 개입 없이 후보 모델 생성

---

## 19. 후보 모델 평가 및 자동 교체

- [ ] 기존 production 모델 평가
- [ ] candidate 모델 평가
- [ ] 동일 test set 비교
- [ ] drift 데이터 성능 비교
- [ ] RUL 성능 비교
- [ ] AP 비교
- [ ] False Alarm 비교
- [ ] 승격 기준 정의
- [ ] candidate PASS 처리
- [ ] candidate FAIL 처리
- [ ] 모델 버전 백업
- [ ] production 모델 교체

**완료 기준**
- [ ] 새 모델이 더 좋은 경우에만 자동 교체됨

---

## 20. 새 모델 적용

- [ ] 모델 hot reload 방식 검토
- [ ] inference container 재시작 방식 검토
- [ ] 최종 적용 방식 선정
- [ ] 모델 변경 감지
- [ ] 새 모델 로딩
- [ ] 적용 실패 시 이전 모델 복구
- [ ] 모델 버전 API/로그 표시

**완료 기준**
- [ ] production model 변경 후 실시간 추론에 자동 반영

---

## 21. 전체 MLOps 통합

### 코드 배포 자동화

- [ ] Git push
- [ ] Jenkins 실행
- [ ] Docker build
- [ ] 개발서버 재배포
- [ ] 배포 성공/실패 확인

### 모델 자동화

- [ ] 실시간 데이터 수집
- [ ] Drift 감지
- [ ] 자동 재학습
- [ ] candidate 평가
- [ ] production 승격
- [ ] inference 적용

**완료 기준**
- [ ] 코드 자동배포와 모델 생명주기 자동화가 독립적으로 정상 동작

---

## 22. 테스트 및 장애 대응

- [ ] 단위 테스트 작성
- [ ] API 테스트
- [ ] Kafka Producer 테스트
- [ ] Kafka Consumer 테스트
- [ ] feature 생성 테스트
- [ ] inference 테스트
- [ ] drift detector 테스트
- [ ] retraining 테스트
- [ ] model promotion 테스트
- [ ] Kafka 중단 테스트
- [ ] API 중단 테스트
- [ ] inference 중단 테스트
- [ ] 잘못된 데이터 입력 테스트
- [ ] 모델 파일 누락 테스트
- [ ] 재학습 실패 테스트
- [ ] candidate 성능 부족 테스트
- [ ] Jenkins 배포 실패 테스트

**완료 기준**
- [ ] 대표적인 장애 상황에서 시스템이 예상된 방식으로 실패/복구

---

## 23. 최종 시스템 통합 및 기능 동결

- [ ] `docker compose up` 전체 서비스 실행 확인
- [ ] Kafka replay 정상
- [ ] 실시간 센서 변화 정상
- [ ] RUL 예측 정상
- [ ] 고장 위험 예측 정상
- [ ] Web 상태 반영 정상
- [ ] Unity 상태 반영 정상
- [ ] Drift 감지 정상
- [ ] 자동 재학습 정상
- [ ] 후보 모델 평가 정상
- [ ] 모델 교체 정상
- [ ] Git push → Jenkins 재배포 정상
- [ ] 최종 버그 수정
- [ ] 기능 추가 중단

**완료 기준**
- [ ] 처음부터 끝까지 전체 데모를 한 번에 실행 가능

---

## 24. 포트폴리오 및 문서화

- [ ] README 완성
- [ ] 프로젝트 목적 설명
- [ ] TEP 데이터 설명
- [ ] 시스템 아키텍처 그림
- [ ] 데이터 흐름 그림
- [ ] 모델 구조 설명
- [ ] 모델 평가 결과 정리
- [ ] LOCO 검증 결과 정리
- [ ] Kafka 구조 설명
- [ ] Docker 구조 설명
- [ ] Jenkins CI/CD 설명
- [ ] Drift 감지 설명
- [ ] 자동 재학습 설명
- [ ] 모델 교체 구조 설명
- [ ] Unity 디지털트윈 설명
- [ ] 실행 방법 작성
- [ ] 데모 이미지/GIF 첨부
- [ ] 기술적 한계 정리
- [ ] 향후 개선사항 정리

**완료 기준**
- [ ] 저장소 README만 읽어도 프로젝트 구조와 기술적 의도를 이해 가능

---

# 전체 진행 현황

- [ ] 01. 프로젝트 기획 확정
- [ ] 02. TEP 데이터 구조 및 고장 시나리오 분석
- [ ] 03. 모델 검증용 데이터셋 구축
- [ ] 04. AI Baseline 모델 개발
- [ ] 05. 시계열 Feature 모델 개발
- [ ] 06. 최종 모델 선정 및 설명 기능
- [ ] 07. 프로젝트 기본 구조 생성
- [ ] 08. Docker 개발환경 구축
- [ ] 09. 개발서버 수동 배포
- [ ] 10. Jenkins 기본 CI/CD 구축
- [ ] 11. Kafka 실시간 데이터 재생
- [ ] 12. 실시간 추론 서비스
- [ ] 13. FastAPI
- [ ] 14. 기본 Web 모니터링
- [ ] 15. Unity 디지털트윈
- [ ] 16. 전체 실시간 시스템 1차 통합
- [ ] 17. 데이터 드리프트 감지
- [ ] 18. Python 자동 재학습
- [ ] 19. 후보 모델 평가 및 자동 교체
- [ ] 20. 새 모델 적용
- [ ] 21. 전체 MLOps 통합
- [ ] 22. 테스트 및 장애 대응
- [ ] 23. 최종 시스템 통합 및 기능 동결
- [ ] 24. 포트폴리오 및 문서화
