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
pnpm --filter @tennis/api seed
```

`apps/api/seed/courts_wuhan.csv` is a first set of public Wuhan venues. The importer upserts by `(city, name)`. Latitude and longitude are blank except 汉江湾体育公园网球场 (GCJ-02 from Amap). Product should still spot-check the rows on a WeChat map before treating them as final. A future CSV that puts `TODO` in the name, district, or address is refused unless you pass `--allow-placeholder`, and it is refused entirely when `APP_ENV=prod`.

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
- Matching through recommend, apply, my-matches, cancel/leave, arrive, pairwise rating, credit, and the in-process scheduler
- LLM re-ranking on the server when `LLM_ENABLED=true` and `AI_MODEL_BASE_URL`, `AI_MODEL_API_KEY`, and `AI_MODEL_NAME` are all set. Otherwise recommend stays on the rule order (`llmApplied=false`). The mini program never sees the key. See [Enabling LLM locally](#enabling-llm-locally).
- Profile completion, NTRP monthly cooldown (`40301` + `nextEditableAt`), and avatar `fileID` checks (`40004`)
- `GET /api/v1/courts?city=` (active courts only). The Wuhan seed is a first public-venue set; most coordinates are still blank pending a GCJ-02 check on a WeChat map
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

## Enabling LLM locally

Copy `apps/api/.env.example` to `apps/api/.env` (gitignored) and set:

```sh
LLM_ENABLED=true
AI_MODEL_BASE_URL=https://your-openai-compatible-host/v1
AI_MODEL_API_KEY=your-key
AI_MODEL_NAME=your-model
```

Leave `LLM_DEBUG_API_ENABLED=false` unless you also set `INTERNAL_API_TOKEN` and want `POST /api/v1/llm/match/score` and `/batch-score`. Do not commit `.env`. CI keeps `LLM_ENABLED=false` and does not call a model. A missing key forces the rule-only path even if `LLM_ENABLED=true`.

## Next milestone

M5 stays out of this branch: Cloud Run production wiring, content safety, and mini program review submission. The Wuhan court seed is a first public-venue set and still needs a WeChat-map spot-check, especially the blank coordinates. Cloud Hosting stays environment-driven. The image job in CI builds `apps/api` only.
