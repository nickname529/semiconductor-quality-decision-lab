# 데이터 출처와 가용성

- 공식 출처: [UCI SECOM](https://archive.ics.uci.edu/dataset/179/secom)
- McCann, M. & Johnston, A. (2008). SECOM [Dataset].
  [DOI:10.24432/C54305](https://doi.org/10.24432/C54305)
- 라이선스: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- 다운로드: https://archive.ics.uci.edu/static/public/179/secom.zip
- 출처·라이선스 확인일: 2026-10-01.

공식 설명은 591 features라고 하지만 실제 `secom.data`는 1,567 × 590이다.
입력은 `feature_000`부터 `feature_589`로 명명한다. 원본 라벨 `-1=PASS`, `1=FAIL`을
내부 `0=PASS`, `1=FAIL`로 변환한다. 따옴표로 감싼 timestamp는 `%d/%m/%Y %H:%M:%S`로 해석한다.
시간대는 원본에 명시되어 있지 않으므로 임의의 시간대를 부여하지 않는다.

## 있는 것 / 없는 것

있는 것: 익명 수치 측정값, 결측값, 테스트 PASS/FAIL, 테스트 시점.
없는 것: 웨이퍼맵, 공정 변수의 실제 이름·단위, lot/batch/장비/recipe ID,
고객·불량 비용·검사 용량·추가 검사의 정확도·현장 후속 결과.
현재 기업·고객사 데이터가 아니며 SK하이닉스 제공 자료도 아니다.

## 확보 및 보존

`python scripts/run_analysis.py --download --output results/reproduced`가 공식 원본을 받는다.
다운로드는 UCI에만 요청하며 API 키가 필요 없다. ZIP과 3개 추출 파일의 SHA-256을
코드에 고정한다. 불일치 파일은 덮어쓰지 않고 중단한다. 기존 원본이 검증되면 재사용한다.
임의 ZIP 경로를 일괄 추출하지 않고 지정한 파일만 읽는다.

원본은 `data/raw/`에 저장하고 Git에서는 제외한다. 이 분석 세션에서 원본을 확보했으며,
새 clone에서 재현하려면 최초 인터넷 연결이 필요하다. 원본 확보 후 `--download` 없이
오프라인 재실행할 수 있다. 변환·파생 결과는 `results/baseline/`에 저장한다.
출처와 고정 해시는 `results/baseline/source_manifest.json`에도 포함되어 있다.
