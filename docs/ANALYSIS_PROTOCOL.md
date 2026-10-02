# 분석 사전 규칙 — Draft / 사용자 검토 대기

작성: 2026-10-01. 본 저장소의 분석 실행 전에 기록한 구현 규칙이다.
사용자가 승인한 운영 규격이나 통계적 사전등록은 아니다. 기존 SECOM 프로젝트의
분석 결과는 이미 알려져 있으므로 이 실험을 완전히 새로운 blind holdout 검증이라고 부르지 않는다.

- 질문: 익명 공정 측정값의 위험 순위가 제한된 추가 검토 용량에서 FAIL을 포착하는가?
- 원본: UCI SECOM 공식 ZIP, SHA-256 고정. 1,567행 × 590개 측정값.
- 시간순 약 60/20/20 train/validation/test. 경계의 동일 timestamp는 앞 분할에 모두 배정.
- timestamp는 분할 전용; row ID는 추적·동점 정렬 전용. 모델 입력에 포함하지 않는다.
- 모델: median imputation → variance-zero removal → RandomForestClassifier.
  n_estimators=200, min_samples_leaf=3, class_weight=balanced, random_state=42,
  n_jobs=1. 전처리와 학습 모두 train에서만 fit. 모델 탐색·튜닝·재학습 없음.
- 기준: train FAIL 비율의 상수 점수(dummy AP), 무검토, 전수검토,
  무작위 k개 검토의 FAIL 포착 기대값(k × FAIL/N).
- 가정 용량: 각 평가 구간 전체의 10%, 20%, 30%를 floor하여 top-k 추가 검토.
  운영 요구사항이 아닌 예시. 동점은 원본 row ID 오름차순. k=0이면 검토 0건.
- 별도 정책: validation 점수의 80% quantile(linear)을 고정 threshold로 test에 적용.
  >= threshold는 검토 후보. 동점/분포 변화 때문에 이 정책은 20% 용량을 보장하지 않는다.
- top-k는 평가 구간의 전체 점수가 알려진 후 정렬하는 retrospective batch 정책이다.
  실시간 정책·일별 용량으로 해석하지 않는다. 비교 후 최적 정책을 선택하지 않는다.
- 보고: AP/ROC-AUC, 검토 건수, FAIL 포착/미포착, PASS 추가 검토,
  precision/recall, recall Wilson 95% 구간(독립 표본 가정의 기술적 구간).
- 전체 EDA는 결측·상수·라벨·기간 분포만 기술. feature selection에는 사용하지 않는다.
- 금액, 손익 최적화, 고객 피해, 공정 원인, 수율 개선, 검사 후 개선율은 계산하지 않는다.
- 예측점수는 보정 확률이 아니다. 검토 후보는 불량 확정이나 출하 차단 판정이 아니다.
