#!/usr/bin/env bash
set -euo pipefail

if [[ $# -eq 0 ]]; then
  echo "사용법: $0 \"NotebookLM에 물어볼 질문\"" >&2
  exit 2
fi

if ! command -v nlm >/dev/null 2>&1; then
  echo "nlm CLI를 찾을 수 없습니다." >&2
  exit 1
fi

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output_dir="${project_root}/reports/notebooklm/queries"
timestamp="$(date '+%Y-%m-%d_%H-%M-%S')"
output_file="${output_dir}/${timestamp}_query.md"
question="$*"

mkdir -p "${output_dir}"

response="$(nlm notebook query maximus "${question}" --json)"
answer="$(jq -r '.answer' <<<"${response}")"
conversation_id="$(jq -r '.conversation_id // "없음"' <<<"${response}")"
source_count="$(jq -r '(.sources_used // []) | length' <<<"${response}")"

{
  echo "# NotebookLM 질의 결과"
  echo
  echo "- 생성 시각: $(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "- 노트북: maximus"
  echo "- 질문: ${question}"
  echo "- 사용한 소스 수: ${source_count}"
  echo "- 대화 ID: ${conversation_id}"
  echo
  echo "## 답변"
  echo
  echo "${answer}"
} | tee "${output_file}"

echo
echo "저장됨: ${output_file}"
