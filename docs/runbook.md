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
pnpm --filter @tennis/api seed -- --allow-placeholder
```

`docker-compose.yml` is for laptops only. Cloud Hosting does not use it.

## 7. Production

Do not create the production environment in this milestone. The checklist is `docs/DESIGN.md` §15.1.
