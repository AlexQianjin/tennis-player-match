# Runbook (stub)

This is the M0 outline from `docs/DESIGN.md` §4.14. Fill in real environment IDs when the WeChat Cloud Hosting test environment exists. Do not put passwords in this file.

## 1. Open the test environment

1. Create one Cloud Hosting environment in Shanghai. Leave MySQL auto-pause on.
2. Create MySQL 8.0. Set `character_set_server=utf8mb4` before creating `tennis` with `utf8mb4_0900_ai_ci`. Collation cannot be changed later.
3. As root, run `apps/api/sql/users.sql` after replacing the password placeholders. That creates `tennis_migrator` and `tennis_app`.
4. Object storage rule: all users can read, only the creator can write. Avatar objects live under `avatars/`.

## 2. Service

- Name: `tennis-api`.
- Port: **8080** (must match the container).
- Public network: **off**. The API trusts `X-WX-OPENID` only because the gateway is the sole caller.
- Replicas: min 0 / max 2 for the test environment.
- Pipeline: this repo, branch `main`, target directory `apps/api`, Dockerfile `apps/api/Dockerfile`.
- Minimum base library for the mini program: 2.23.0.

## 3. Runtime configuration

Copy the test-environment JSON in `docs/DESIGN.md` §12.3 into the service settings. `MYSQL_ADDRESS` is the private address from the MySQL page. `CBR_ENV_ID` is injected by the platform.

`AUTH_MODE` on the cloud service stays `wxcloud`. `dev` is only for a local uvicorn process.

## 4. Release and migrate

The container runs `tennis-match-migrate --if-enabled` before uvicorn. That waits for a paused database, takes `GET_LOCK('tennis:migrate', 60)`, then `alembic upgrade head`.

MySQL DDL commits implicitly. Take a console backup before a destructive migration. Rollback is "deploy the previous image", plus `alembic downgrade` only when that downgrade is known to be safe.

## 5. Logs

Stdout JSON. Look for `event=startup`, `db_connect_retry`, and 5xx responses. `SERVICE_NOT_READY` or `ECONNREFUSED` means the container is cold. `CynosDB serverless instance is resuming` means the database is waking up; the client retries, and the mini program retries `50301`.

## 6. Local equivalents

```sh
pnpm db:up
pnpm db:migrate
pnpm --filter @tennis/api seed
```

`docker-compose.yml` is for laptops only. Cloud Hosting does not use it.

## 7. Production

Do not create the production environment in this milestone. The checklist is `docs/DESIGN.md` §15.1.

## 8. 本地联调（微信开发者工具）

一条命令拉起 MySQL、迁移、导入武汉球场、用开发模式编出小程序，并在 8000 端口启动 API（`AUTH_MODE=dev`，定时任务打开）：

```sh
pnpm dev:integration
```

脚本是 `scripts/dev-integration.sh`。它要求本机有 Docker、pnpm，以及 Node 24.22.2（`.nvmrc`）。Node 22 编微信包会在 `RegExp.escape` 上报错。若还没有 `apps/api/.env`，脚本会从 `.env.example` 复制一份；进程环境变量会把本次启动固定成 `AUTH_MODE=dev` 和 `SCHEDULER_ENABLED=true`，不会改写文件。小程序请求地址来自 `apps/miniapp/.env.development` 的 `TARO_APP_API_BASE_URL=http://127.0.0.1:8000/api/v1`。云托管镜像仍用容器端口 8080，那是 `.env.example` 里的 `PORT`，本地这条链路不读它。

想自己分步时：

```sh
pnpm install
pnpm --filter @tennis/api setup
cp apps/api/.env.example apps/api/.env   # 已有则跳过
pnpm db:up
pnpm db:migrate
pnpm seed:courts
pnpm --filter @tennis/miniapp exec vite build --mode development
cd apps/api && AUTH_MODE=dev SCHEDULER_ENABLED=true uv run uvicorn tennis_match_api.main:create_app --factory --host 0.0.0.0 --port 8000
```

热更新小程序用另一个终端跑 `pnpm dev:weapp`（同样是 development 模式）。只改页面时不必重启 API。

在微信开发者工具中：

1. 导入项目目录 `apps/miniapp/dist/wx`，或导入仓库根目录（`project.config.json` 的 `miniprogramRoot` 已指向 `dist/wx/`）。
2. 打开「详情 → 本地设置」，勾选「不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书」。工程配置里的 `urlCheck: false` 不会代替这一项；不勾选时，开发者工具会拦截 `http://127.0.0.1:8000`。
3. 基础库建议不低于 2.23.0。编译模式保持普通小程序，不要切到 Skyline。
4. 多用户：底部「个人中心 → 设置」，修改「本地测试账号（X-Dev-Openid）」后点「保存并重新登录」。每个不同的值都是一个新用户（默认 `dev_user_1`，可再开 `dev_user_2`、`dev_user_3`）。换号后要各自走一遍「完善资料」，否则不能发布和申请。清除本地缓存会保留当前这个测试账号，避免把身份清回默认值。
5. 推荐列表在模型未配置或调用失败时仍返回规则排序，并提示「当前按信用分和等级排序（模型未参与）」。要启用模型，在 `apps/api/.env` 写上 `LLM_ENABLED=true` 和 `AI_MODEL_*`，再重启 API。
6. 24 小时自动取消由进程内定时任务扫描，默认间隔 300 秒，不会在到点的同一秒立刻变状态。到场窗口是约定开始时间起的 24 小时；信用分在提交评分后 +1，只点到场不加分。

没有微信开发者工具或真机时，接口本身用 `cd apps/api && uv run pytest tests/integration/test_mvp_flow_dev.py` 覆盖同一条 dev 身份链路。
