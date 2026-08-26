#!/bin/zsh

set -u

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$HOME/Library/pnpm:$PATH"
cd "$SCRIPT_DIR" || exit 1

if ! command -v node >/dev/null 2>&1; then
  echo "启动失败：没有找到 Node.js。请先安装 Node.js 22 或更高版本。"
  echo "按任意键关闭窗口。"
  read -k 1
  exit 1
fi

node scripts/dev.mjs
status=$?

if [ "$status" -ne 0 ]; then
  echo
  echo "启动没有完成，请保留上方报错信息。按任意键关闭窗口。"
  read -k 1
fi

exit "$status"
