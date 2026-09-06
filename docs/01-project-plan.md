# TEP Digital Twin 프로젝트 기획서

## 1. 프로젝트 개요

TEP Run-to-Failure 화학공정 데이터를 Kafka로 실시간 스트리밍하고,
AI를 이용해 공정의 고장 위험과 잔여수명을 예측하며,
데이터 드리프트에 따른 자동 재학습과 Unity 디지털트윈 모니터링까지 구현하는
예지보전 개인 프로젝트.

---

## 2. 프로젝트 목표

- 공정 센서 데이터 실시간 재생
- 고장 위험 예측
- 잔여수명(RUL) 예측
- 주요 위험 요인 설명
- 데이터 드리프트 감지
- 자동 재학습
- 후보 모델 평가 및 자동 교체
- Unity 기반 공정 시각화
- Git push 기반 개발서버 자동배포

---

## 3. 대상 공정

TEP 화학공정 전체를 하나의 공정으로 표현한다.

주요 상태 표현 대상:
- 반응기
- 분리기
- 정제기

공정 흐름:

원료 투입
→ 반응기
→ 응축/냉각
→ 분리기
→ 정제기
→ 제품 생산

일부 물질은 압축 후 반응기로 재순환된다.

---

## 4. 사용자 흐름

1. 사용할 TEP trajectory 선택
2. 시뮬레이션 시작
3. Kafka로 센서값 순차 전송
4. AI 모델 실시간 추론
5. 고장 위험도와 RUL 계산
6. FastAPI를 통해 결과 제공
7. Web과 Unity에서 상태 확인

---

## 5. 시스템 구조

TEP CSV
→ Kafka Producer
→ Kafka
→ Inference Service
→ AI Model
→ FastAPI
→ Web / Unity

별도 MLOps 흐름:

실시간 데이터
→ Drift Monitor
→ Drift 감지
→ 재학습
→ Candidate Model
→ 기존 모델 비교
→ Production Model 교체

---

## 6. CI/CD 구조

Git push
→ GitHub
→ Jenkins
→ Docker Build
→ 개발서버 재배포

Jenkins는 코드 배포 자동화를 담당한다.

모델 재학습과 모델 교체는 Jenkins가 아니라
Python 기반 자체 MLOps 로직에서 처리한다.

---

## 7. 기술 스택

- Python
- XGBoost
- CUDA
- Pandas
- NumPy
- SHAP
- Apache Kafka
- FastAPI
- pytest
- Docker
- Docker Compose
- Jenkins
- Unity
- Git / GitHub
- Oracle Cloud

---

## 8. 제외 범위

현재 프로젝트에서는 다음 기술을 사용하지 않는다.

- Airflow
- MLflow

기능상 필요하지 않기 때문에 자체 Python 기반 구조로 구현한다.

---

## 9. 프로젝트 한 문장 설명

TEP 기반 실시간 AI 예지보전 및 화학공정 디지털트윈 시스템