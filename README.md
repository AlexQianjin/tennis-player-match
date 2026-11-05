# tennis-player-match

WeChat mini program for matching tennis partners (网球约球). This repository follows `docs/DESIGN.md`. M1 covers login, profile completion (including an avatar fileID), the personal center, and the court list. Publish / recommend / apply behavior beyond the profile gate is still later work.

## Toolchain

The mini program uses the community plugin [`vite-plugin-taro`](https://github.com/sep2/vite-plugin-taro) (npm `vite-plugin-taro@0.8.5`, `pnpm create vite-taro`), not `@tarojs/vite-runner`.

Verified on 2026-11-04:

| Piece | Version | Result |
| --- | --- | --- |
| Node.js | 24.22.2 | Required. Node 22.23.4 fails the weapp build with `RegExp.escape is not a function`. The package `engines` field allows `^22.18.0`, but that range does not actually build. `.nvmrc` is `24.22.2`. |
| pnpm | 10.33.4 | Workspace install, strict layout. |
| Vite | 8.3.5 | `vite build` writes `apps/miniapp/dist/wx`. |
| vite-plugin-taro | 0.8.5 | WeChat target `wx`. React 19.3.1. TypeScript 5.9. |
| Tailwind CSS | 4.3.3 | Pulled in by the plugin, together with `@weapp-tailwindcss/postcss@3.4.3`. Utilities land in `dist/wx/assets/global.wxss`. Spacing is emitted as `rpx` (`--spacing: 8rpx`). Class names that are illegal in WXSS are rewritten (`w-1/2` style escapes). |
| Zustand | 5 | Sample auth store on the profile tab. |

`TARO_APP_*` is not injected by Taro's compiler here. `vite.config.ts` sets `envPrefix` to `VITE_` and `TARO_APP_`, so the same variable names from the design are available as `import.meta.env.TARO_APP_*`. The plugin itself still uses `VITE_VPT_WECHAT_APP_ID` and `VITE_VPT_TARGET` is unnecessary because this app hard-codes the WeChat target.

### Caveats versus DESIGN.md §3.8 and §10.2

- **Page subpackages are not available.** vpt deletes hand-written `subPackages` and puts every `pages` entry in the main package. Its automatic subpackages are JavaScript chunks reached by `import()`. The detail panel is loaded that way and shows up as `dist/wx/sub/p_<hash>` with `"pages": []`. The screen files still live under `src/subpackages/` so the routes match the design, but they count toward the main package until the plugin can place pages in native subpackages.
- **Native tabBar is used** (`custom` is omitted). Icons are flat PNGs in `public/assets/tabbar/` and are copied into `dist/wx/assets/tabbar/`.
- **Open `apps/miniapp/dist/wx` in WeChat DevTools** after a build. The source `project.config.json` only points `miniprogramRoot` at that directory.
- The plugin is young (repository created 2026-06, low star count). The official `@tarojs/vite-runner` path in the design remains the fallback if a later weapp bug cannot be avoided. Do not switch silently.

## Layout

```text
apps/miniapp     @tennis/miniapp   Vite 8 + vite-plugin-taro + React 19 + Zustand
apps/api         @tennis/api       FastAPI, uv, Alembic, asyncmy
packages/shared  @tennis/shared    OpenAPI types, enums, error codes
docs/DESIGN.md   technical design (source of truth)
docs/specs/      the eight original product specs
```

Python dependencies stay inside `apps/api` (`uv sync`). `pnpm install` does not touch them.

## Prerequisites

- Node.js 24.11 or newer (`nvm use` reads `.nvmrc`)
- Corepack, so the pnpm version comes from the root `packageManager` field
- uv 0.13.x (CI pins 0.13.7)
- Docker, for `pnpm db:up` (MySQL 8.0, utf8mb4)
- WeChat DevTools, when you want to open the mini program

## Setup

```sh
pnpm install
pnpm --filter @tennis/api setup
cp apps/api/.env.example apps/api/.env
pnpm db:up
pnpm db:migrate
pnpm --filter @tennis/api seed -- --allow-placeholder
```

The court CSV is still placeholder text (`TODO-球场名称-01` and two more rows). Real Wuhan court names are **not** in this repo and must not be invented here — that list is a product-owner task. The importer upserts by `(city, name)`, so a verified CSV can replace `apps/api/seed/courts_wuhan.csv` later without API changes. The placeholder file is refused unless you pass `--allow-placeholder`, and it is refused entirely when `APP_ENV=prod`.

Local API auth is `AUTH_MODE=dev`. The mini program sends `X-Dev-Openid` (storage key `devOpenid`, default `dev_user_1`) only on the http transport. That header is ignored when `AUTH_MODE=wxcloud`.

## Commands

```sh
pnpm dev            # API on :8000 and the weapp dev server
pnpm dev:api
pnpm dev:weapp      # Vite dev, .env.development, http transport
pnpm --filter @tennis/miniapp dev:weapp:cloud   # .env.test, callContainer
pnpm --filter @tennis/miniapp build:weapp:test
pnpm lint && pnpm typecheck && pnpm test
pnpm gen:api        # refresh packages/shared/openapi.json and generated types
```

Root `lint` / `typecheck` / `test` / `build` run the workspace packages and skip the root package, so they do not call themselves.

The mini program dev server writes `apps/miniapp/dist/wx`. Import that directory in DevTools and, for the http transport, disable URL checks. `Taro.cloud.callContainer` is used only when `TARO_APP_TRANSPORT=cloud`.

## What is implemented

- FastAPI envelope `{code, message, data}`, the error codes from the design, and `X-WX-*` / dev-header checks (`AUTH_MODE=dev` is rejected when `APP_ENV=prod`)
- `GET /healthz`, `GET /api/v1/health`, `GET /api/v1/health/db`
- `POST /api/v1/auth/login` (upsert, `isNewUser`, disabled users return 403)
- `GET/POST/PATCH /api/v1/user/profile` and `GET /api/v1/user/{userId}/public`
- Rules-only matching: publish, recommend (`llmApplied=false`), detail, apply, withdraw, and agree/reject. Arrive, rate, cancel, and LLM ranking are later milestones.
- Profile completion, NTRP monthly cooldown (`40301` + `nextEditableAt`), and avatar `fileID` checks (`40004`)
- `GET /api/v1/courts?city=` (active courts only). Wuhan rows in the seed CSV are still `TODO` placeholders
- Mini program launch login, onboarding (`mode=onboarding`), personal center, and a court picker on the publish tab
- Alembic `0001_init` executes `apps/api/migrations/sql/0001_init.sql` (the validated DDL without `CREATE DATABASE`)
- asyncmy connections set `time_zone='+00:00'`, `CLIENT.FOUND_ROWS`, and retry transient errors including a resuming CynosDB

`alembic check` ignores tables and columns that the ORM does not map yet. The SQL file remains the schema source; the ORM maps `app_user` (including `ntrp_update_time`) and `court`.

Try the mini program locally with `AUTH_MODE=dev`:

```sh
pnpm dev:api
pnpm dev:weapp
```

Open `apps/miniapp/dist/wx` in WeChat DevTools (`pnpm --filter @tennis/miniapp dev:weapp` writes that directory) and leave URL checking off. The http transport sends `X-Dev-Openid`. Choose-avatar upload is a fileID stub on that transport (`cloud://dev.local/avatars/...`) because cloud storage is not configured locally.

## Next milestone

My matches, arrival, ratings, credit, and the scheduler (M3), then LLM re-ranking (M4). A verified Wuhan court CSV is still a product-owner task. Cloud Hosting wiring stays environment-driven. The image job in CI builds `apps/api` only.
