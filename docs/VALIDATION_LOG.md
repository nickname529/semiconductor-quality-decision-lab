# 실행·검증 기록

작업 시작: 2026-10-01. 최종 문서 정리: 2026-10-02 (Asia/Seoul).
상태: 로컬 분석·검증 완료 / 문서 해석 Draft / 사용자 검토 대기.

## 실행 환경과 검증 결과

Python 3.12.13, 프로젝트 내부 `.venv`. 패키지 버전은 `requirements-lock.txt`,
실제 분석 환경·코드 해시는 `results/baseline/run_metadata.json`에 기록했다.

| 검증 | 결과 |
|---|---|
| 공식 ZIP 및 추출 파일 SHA-256 | 일치 |
| 원본 크기·라벨·날짜 파싱 | 통과 |
| 시간순 분석 전체 실행 | 완료 |
| 별도 출력 폴더에서 오프라인 재실행 | 완료 |
| 6개 CSV·요약·출처·코드 해시·패키지 버전 비교 | 통과 |
| pytest | 18 passed |
| Ruff lint / format | 통과 |
| Python compileall | 통과 |
| pip check | 의존성 충돌 없음 |
| git diff --check | 통과 |
| 초기 README와 보존본 바이트 비교 | 동일 |
| PNG 4개 육안 확인 | 제목·축·범례·막대 확인 |
| 로컬 Markdown 링크 | 최종 확인 통과 |
| 원격 main | 초기 커밋 e89777f 유지 |

TypeScript typecheck와 애플리케이션 build는 해당하지 않는다. Python 분석 저장소로
별도 정적 타입 검사기·패키지 빌드 작업은 구성하지 않았다. `compileall`은 구문 확인이며
정적 타입 검사나 패키지 빌드를 대신했다는 뜻이 아니다.
GitHub Actions 설정은 추가했지만 원격 실행은 하지 않았다. Linux에서의 실행은 아직 미검증이다.

## 수행 명령

아래 분석·검증 명령은 저장소 루트 기준이다. 조회에는 `rg`, `cat`, `git ls-tree`,
`git show`, `git log`, `git status`, `gh repo list`를 사용했다.
초기 원본은 공개 HTTPS clone으로 확보했다.

```bash
gh repo list nickname529 --limit 100 --json name,url,description,isPrivate,defaultBranchRef
git clone https://github.com/nickname529/semiconductor-quality-decision-lab.git outputs/semiconductor-quality-decision-lab
git status --short --branch
git log -12 --format='%h %ad %s' --date=iso-strict
git ls-tree -r --name-only HEAD
git show --stat HEAD
git switch -c codex/solo-quality-decision-lab
cp README.md docs/archive/README.initial.md
python3 -m venv .venv
uv pip compile requirements-dev.txt -o requirements-lock.txt --python .venv/bin/python
uv pip sync requirements-lock.txt --python .venv/bin/python
.venv/bin/ruff check src scripts --fix
.venv/bin/ruff check src scripts tests --fix
.venv/bin/ruff format src scripts tests
.venv/bin/python scripts/run_analysis.py --download --output results/baseline
mv results/baseline ../../work/initial-analysis-run
.venv/bin/python scripts/run_analysis.py --output results/baseline
.venv/bin/python scripts/run_analysis.py --output ../../work/reproduction
.venv/bin/python scripts/verify_reproduction.py --actual ../../work/reproduction
.venv/bin/python -m pytest -q
.venv/bin/ruff check src scripts tests
.venv/bin/ruff format --check src scripts tests
.venv/bin/python -m compileall -q src scripts tests
.venv/bin/python -m pip check
git diff --check
git diff --stat
git ls-remote origin refs/heads/main
```

추가 인라인 Python 점검으로 README 보존본을 `git show HEAD:README.md`와 바이트 비교했고,
로컬 Markdown 링크가 가리키는 파일의 존재 여부를 검사했다.
최초 분석 결과를 work로 옮긴 이유는 재현 비교 스크립트를 완성한 뒤 그 코드 해시까지
최종 실행 메타데이터에 포함하기 위해서다. 모델·분할·임계값 규칙은 바꾸지 않았다.
사용자 원본을 삭제하지 않았으며, 편집은 요청한 README와 빈 문서 채우기 및 신규 파일 추가다.

## 실패·수정·경고

1. 최초 현재 디렉터리의 Git 조회는 저장소가 아니어서 실패했다. 공개 저장소를 별도 clone했다.
2. 최초 원본 로더가 라벨 파일을 3열로 가정해 `Unexpected source dimensions`로 중단했다.
   실제 날짜·시간이 따옴표로 감싼 하나의 열이므로 2열로 파싱하도록 수정했다.
   해시와 원본 1,567 × 590 검증은 유지했다.
3. 그 상태에서 시행한 첫 테스트는 결과 파일이 없어 3 failed / 15 passed였다.
   로더 수정 및 전체 분석 완료 후 18 passed로 해소했다.
4. 문서 연결의 첫 점검은 아직 작성 중이던 `docs/VALIDATION_LOG.md` 1개가 없어 실패했다.
   본 문서 작성 후 다시 확인했다.
5. 최초 Matplotlib 실행은 폰트 캐시를 생성했다. 분석 오류는 아니었다.
6. 성능은 약하다. 20% 용량에서 FAIL 3/17 포착, 14/17 미포착이며,
   동일 용량의 무작위 기대값 3.36건보다 낮았다. 좋은 수치를 얻기 위한 재튜닝은 하지 않았다.

## 남은 작업·승인 상태

- 사용자 코드 이해·수치 해석·포트폴리오 문구 검토.
- 사용자가 명시적으로 승인한 뒤에만 GitHub push 또는 PR 진행.
- 로컬 브랜치의 변경은 아직 커밋하지 않았다. 원격 변경·PR·merge·배포 없음.
- 외부 현장 데이터, 실제 용량·비용, lot/batch, 검사 정확도는 제공되지 않았다.
  해당 자료가 필요한 후속 검증이나 운영 단계는 자동 진행하지 않는다.

## 정확한 변경 파일 목록

아래 목록은 초기 커밋 대비이며, 원본 데이터와 가상환경은 Git 제외다.

### 수정 (9개)

- `README.md`
- `data/README.md`
- `docs/AI_USAGE.md`
- `docs/CONTRIBUTIONS.md`
- `docs/HUMAN_DECISION_LOG.md`
- `docs/PROBLEM_DEFINITION.md`
- `reports/CUSTOMER_RISK_MEMO.md`
- `reports/JOINT_FINAL_REPORT.md`
- `reports/QUALITY_ENGINEERING_REPORT.md`

### 추가 (34개)

- `.github/workflows/analysis.yml`
- `.gitignore`
- `.python-version`
- `data/raw/.gitkeep`
- `docs/ANALYSIS_PROTOCOL.md`
- `docs/REPOSITORY_AUDIT.md`
- `docs/VALIDATION_LOG.md`
- `docs/archive/README.initial.md`
- `pyproject.toml`
- `requirements-dev.txt`
- `requirements-lock.txt`
- `requirements.txt`
- `results/baseline/01_label_distribution.png`
- `results/baseline/02_missingness.png`
- `results/baseline/03_capacity_capture.png`
- `results/baseline/04_review_workload.png`
- `results/baseline/REPORT.md`
- `results/baseline/artifact_hashes.json`
- `results/baseline/decision_metrics.csv`
- `results/baseline/feature_eda.csv`
- `results/baseline/monthly_eda.csv`
- `results/baseline/predictions.csv`
- `results/baseline/ranking_metrics.csv`
- `results/baseline/run_metadata.json`
- `results/baseline/source_manifest.json`
- `results/baseline/split_assignments.csv`
- `results/baseline/summary.json`
- `scripts/run_analysis.py`
- `scripts/verify_reproduction.py`
- `src/quality_lab/__init__.py`
- `src/quality_lab/data.py`
- `src/quality_lab/decision.py`
- `src/quality_lab/pipeline.py`
- `tests/test_analysis.py`
