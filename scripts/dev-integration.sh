#!/usr/bin/env bash
# One-command local 联调: MySQL, migrate, Wuhan courts, dev-mode weapp, API on :8000.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "需要 Docker 才能启动 MySQL。请先安装并启动 Docker。" >&2
  exit 1
fi
if ! command -v pnpm >/dev/null 2>&1; then
  echo "需要 pnpm。Node 请使用 .nvmrc 里的 24.22.2（Node 22 编不出微信小程序）。" >&2
  exit 1
fi

if [[ ! -d node_modules ]]; then
  pnpm install
fi
if [[ ! -f apps/api/.env ]]; then
  cp apps/api/.env.example apps/api/.env
  echo "已从 apps/api/.env.example 复制 apps/api/.env"
fi

pnpm --filter @tennis/api setup
pnpm db:up
pnpm db:migrate
pnpm seed:courts

echo "构建开发模式小程序，请求 http://127.0.0.1:8000/api/v1"
pnpm --filter @tennis/miniapp exec vite build --mode development

cat <<'EOF'

小程序目录：apps/miniapp/dist/wx
用微信开发者工具导入该目录（或导入仓库根目录，miniprogramRoot 已指向 dist/wx）。
详情 → 本地设置 → 勾选「不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书」。
设置页可切换 X-Dev-Openid（默认 dev_user_1），每个值是一个独立用户。

API：AUTH_MODE=dev，SCHEDULER_ENABLED=true，http://127.0.0.1:8000
模型未配置时推荐走规则排序（llmApplied=false）。Ctrl-C 停止 API。
EOF

cd apps/api
exec env AUTH_MODE=dev APP_ENV=dev SCHEDULER_ENABLED=true \
  uv run uvicorn tennis_match_api.main:create_app --factory --host 0.0.0.0 --port 8000
