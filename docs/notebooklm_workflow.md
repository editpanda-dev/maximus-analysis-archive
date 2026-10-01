# NotebookLM CLI 연동 가이드

## 연결 상태

- NotebookLM 노트북: `MAXIMUS — Where Do We Go?`
- CLI 별칭: `maximus`
- 결과 저장 위치: `reports/notebooklm/`
- 노트북 URL: <https://notebooklm.google.com/notebook/65948a3a-fbbd-488d-98d7-ba9ce6eff46a>

현재 PRD, 프로젝트 요약, 1주차 주제 선정 보고서, 분석 로드맵, 데이터마트 grain, 데이터 출처, EDA 계획이 소스로 등록되어 있다.

## Codex 대화에서 사용하기

이 작업에서 자연어로 다음과 같이 요청하면 된다.

```text
NotebookLM으로 현재 프로젝트의 핵심 리스크를 분석해줘.
NotebookLM에 데이터마트 설계의 허점을 물어보고 결과를 저장해줘.
NotebookLM으로 중간발표용 보고서를 만들어줘.
```

단순 질문은 바로 실행할 수 있다. NotebookLM Studio에서 새 보고서를 생성하는 작업은 외부 생성 작업이므로 실행 전에 사용자 승인을 받는다.

## 터미널에서 질문하기

```bash
./scripts/nlm_query.sh "현재 PRD에서 가장 먼저 검증해야 할 가정 5개를 알려줘"
```

답변은 화면에 출력되고 `reports/notebooklm/queries/`에도 Markdown으로 저장된다.

## 터미널에서 정식 보고서 만들기

```bash
./scripts/nlm_report.sh --confirm "교수님 중간 검토용으로 프로젝트 진행 현황과 다음 단계 보고서를 작성해줘"
```

생성 상태 확인:

```bash
nlm studio status maximus
```

생성이 끝난 뒤 다운로드:

```bash
nlm download report maximus --output reports/notebooklm/reports/latest_report.md
```

## 소스 갱신

로컬 문서를 수정해도 NotebookLM의 기존 업로드본은 자동으로 바뀌지 않는다. 중요한 문서가 변경되면 새 버전을 다시 등록한다.

```bash
nlm source add maximus --file "/Users/woojin/Documents/막시무스/PRD-Where-Do-We-Go.md" --wait
```

업로드 전에는 같은 문서의 이전 버전이 있는지 확인한다.

```bash
nlm source list maximus
```

기존 소스 삭제는 복구할 수 없으므로 사용자 확인 없이 실행하지 않는다.

