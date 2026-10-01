# Where Do We Go?

수도권 생활이동·카드소비·상권 데이터를 결합해, 이동 가능한 후보 중 어떤 상권이 왜 선택되는지 분석하고 후보 목적지를 랭킹하는 DAT 8기 캡스톤 프로젝트입니다.

## Team MAXIMUS

**막시무스(MAXIMUS)**는 라틴어로 ‘가장 큰’, ‘가장 위대한’이라는 뜻을 지닌 이름입니다. 우리는 이 이름에 단순히 가장 인기 있는 장소를 찾는 것을 넘어, 사용자가 실제로 갈 수 있는 범위 안에서 가장 가치 있는 목적지를 발견하겠다는 의미를 담았습니다. 생활이동·소비·상권 데이터를 통해 사람들이 어디로 이동하고, 왜 그곳을 선택하며, 그 선택이 실제 소비로 어떻게 이어지는지를 분석합니다. 이를 바탕으로 각자의 시간과 목적에 가장 잘 맞는 선택지를 제안하는 것이 막시무스가 지향하는 방향입니다.

> **갈 수 있는 범위 안에서, 가장 가치 있는 선택을.**

## 현재 단계

Phase 0 — Feasibility / schema audit

- 원본 프로젝트 컨텍스트 보존
- 데이터 출처와 접근 제약 정리
- 공통 분석 단위(grain) 초안 정의
- 공개 데이터 기반 파이프라인 및 1차 EDA 준비

모델과 UI는 데이터 구조 및 JOIN 가능성을 검증한 뒤 진행합니다.

## 핵심 질문

이동시간을 통제한 뒤에도 어떤 상권 특성이 실제 이동 유입과 외부 소비를 더 잘 설명하는가?

## 문서

- `PROJECT_CONTEXT.md`: 전달받은 프로젝트 원문
- `docs/PROJECT_SUMMARY.md`: 실행 관점 요약
- `docs/data_sources.md`: 데이터 출처·단위·제약
- `docs/model_dataset_grain.md`: 분석 데이터마트 단위와 키
- `docs/eda_plan.md`: 1차 EDA 계획
- `docs/analysis_roadmap.md`: 연구질문별 통계기법·진단·검증 로드맵
- `docs/archive_log.md`: 아카이빙 이력
- `docs/notebooklm_workflow.md`: NotebookLM CLI 질의·보고서 생성 방법

## NotebookLM 연동

프로젝트 전용 NotebookLM 노트북은 CLI 별칭 `maximus`로 연결되어 있습니다.

```bash
./scripts/nlm_query.sh "현재 프로젝트의 핵심 리스크를 요약해줘"
```

질의와 보고서 결과는 `reports/notebooklm/` 아래에 저장합니다. 정식 보고서 생성 방법과 승인 절차는 `docs/notebooklm_workflow.md`를 참고합니다.

## 데이터 디렉터리

- `data/raw/`: 원본(수정 금지, Git 미추적)
- `data/external/`: 외부 공개 원본(Git 미추적)
- `data/interim/`: 중간 산출물(Git 미추적)
- `data/processed/`: 분석용 산출물(Git 미추적)

각 데이터 폴더의 `.gitkeep`만 버전 관리합니다. 민감 데이터와 빅데이터캠퍼스 반출 제한 자료는 저장소에 커밋하지 않습니다.
