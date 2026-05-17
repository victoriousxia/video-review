#!/usr/bin/env bash
set -Eeuo pipefail

OPERATIONS_DIR="${OPERATIONS_DIR:-/nas/docker/video-review/data/operations}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXECUTOR="$SCRIPT_DIR/hermes_operation_executor.py"

run_executor() {
  python3 "$EXECUTOR" --operations-dir "$OPERATIONS_DIR" "$@"
}

print_header() {
  printf '\n==== %s ====\n' "$1"
}

choose_operation() {
  local ops_json count
  ops_json="$(run_executor list)"
  count="$(printf '%s' "$ops_json" | jq 'length')"
  if [ "$count" -eq 0 ]; then
    echo "当前没有待审批的 video-review 删除请求。"
    return 1
  fi

  print_header "待审批请求"
  printf '%s' "$ops_json" | jq -r 'to_entries[] | "\(.key + 1). \(.value.operation_id) | \(.value.job_name) | 文件数=\(.value.item_count) | 大小=\(.value.total_size_bytes) bytes"'
  printf '\n请选择 operation 序号，或输入 operation_id：'
  read -r choice

  if [[ "$choice" =~ ^[0-9]+$ ]]; then
    local idx=$((choice - 1))
    if [ "$idx" -lt 0 ] || [ "$idx" -ge "$count" ]; then
      echo "序号无效。" >&2
      return 1
    fi
    printf '%s' "$ops_json" | jq -r ".[$idx].operation_id"
  else
    printf '%s' "$choice"
  fi
}

main() {
  print_header "video-review Hermes 审批执行器"
  echo "operations dir: $OPERATIONS_DIR"
  local op_id
  op_id="$(choose_operation)" || exit 0

  print_header "执行计划"
  run_executor plan "$op_id"

  printf '\n操作选项：\n'
  printf '1. 扔垃圾桶\n'
  printf '2. 立刻删除\n'
  printf '3. 取消\n'
  printf '请选择：'
  read -r action

  case "$action" in
    1)
      print_header "扔垃圾桶结果"
      run_executor execute "$op_id" --confirm "$op_id"
      ;;
    2)
      printf '\n危险：立刻删除会永久 unlink 文件，不进入 .video-review-trash。\n'
      printf '如确认永久删除，请输入 DELETE_PERMANENTLY %s：' "$op_id"
      read -r confirm
      print_header "立刻删除结果"
      run_executor delete-permanently "$op_id" --confirm "$confirm"
      ;;
    3)
      print_header "取消结果"
      run_executor reject "$op_id" --reason "cancelled by user"
      ;;
    *)
      echo "选项无效，未执行任何文件操作。"
      ;;
  esac
}

main "$@"
