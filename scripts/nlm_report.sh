#!/usr/bin/env bash
set -euo pipefail

if [[ ${1:-} != "--confirm" || $# -lt 2 ]]; then
  echo "NotebookLM Studio 보고서 생성은 외부 생성 작업입니다." >&2
  echo "사용법: $0 --confirm \"원하는 보고서 설명\"" >&2
  exit 2
fi

shift
prompt="$*"
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output_dir="${project_root}/reports/notebooklm/reports"
timestamp="$(date '+%Y-%m-%d_%H-%M-%S')"
output_file="${output_dir}/${timestamp}_report.md"

mkdir -p "${output_dir}"

grounded_prompt="${prompt}

업로드된 소스만 사용하세요. 소스에 없는 통계, 인용문, 사례를 만들지 마세요. 확인된 사실, 가정, 미결정 사항을 구분하고 한국어로 작성하세요."

echo "NotebookLM 보고서 생성을 요청합니다."
nlm report create maximus \
  --format "Create Your Own" \
  --prompt "${grounded_prompt}" \
  --language ko \
  --confirm

echo
echo "생성이 완료된 뒤 아래 명령으로 상태를 확인하세요."
echo "  nlm studio status maximus"
echo "완료 후 아래 명령으로 내려받으세요."
echo "  nlm download report maximus --output \"${output_file}\""

