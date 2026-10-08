# Runtime credential configuration

The application requires explicit credentials. Development, staging, and production
reject default or weak JWT secrets and PostgreSQL passwords. Test-only fixtures are
permitted only with `ENVIRONMENT=test`; do not deploy with that environment.

## First-time Docker setup

Copy `backend/.env.example` to `backend/.env` for provider settings. On a fresh clone
with no existing `.env` or application database, initialize private credentials:

```powershell
docker run --rm -v "${PWD}:/workspace" -w /workspace python:3.12-slim python backend/scripts/bootstrap_local_secrets.py
docker compose up -d --build db backend frontend
```

The helper writes the ignored root `.env`, generates independent credentials, prints
no secret values, and refuses to overwrite an existing file. Keep it private and
restrict its filesystem access. Container environment variables override provider
file entries for the security settings below. Never run database tests against the
application database.

| Setting | Purpose |
| --- | --- |
| `SECRET_KEY` | JWT signing key; independently generated, at least 32 characters |
| `POSTGRES_PASSWORD` | PostgreSQL role password; independently generated, at least 32 characters |
| `DATABASE_URL` | asyncpg URL containing the matching role password; container hostname `db` |
| `INTEGRATION_TOKEN` | Optional independent Finance bridge credential, at least 32 characters |
| `INTEGRATION_USER_ID` | UUID of the explicitly selected, existing PortfolioMind user |
| `PORTFOLIOMIND_API_TOKEN` | Outbound Finance client credential; Compose supplies `INTEGRATION_TOKEN` |

## Finance bridge authorization

The bridge is disabled until a token and an existing user UUID are configured. Select
that user's UUID from the authenticated `GET /api/auth/me` response. Generate a new
random credential using a cryptographically secure generator and store it directly
in the ignored environment file or a deployment secret manager. Do not paste secrets
into source, tickets, command histories, or logs. Never reuse the JWT key.

Set `INTEGRATION_TOKEN` and `INTEGRATION_USER_ID` in the root `.env`, then recreate the
backend. The outbound Finance client continues sending a Bearer credential through
`PORTFOLIOMIND_API_TOKEN`. A separately deployed Finance client must receive the same
new credential in its private environment. It can also use the existing user-login
JWT flow. `PORTFOLIOMIND_API_TOKEN` is no longer an inbound authentication alias.

Only instrument catalog GETs and the intelligence/review/technical-plan routes opt
into bridge authentication. Personal finance, authentication, instrument creation,
and research execution routes require an expiring user JWT. The credential never
selects the first user or another fallback account. A removed user immediately loses
bridge access. Compare credentials in constant time.

## Existing database and credential rotation

Changing `POSTGRES_PASSWORD` in Compose does **not** change the password on an
initialized PostgreSQL volume. Keep `postgres_data`; never delete volumes or reset
the database to rotate credentials.

1. Arrange a short maintenance window and preserve a private rollback copy of the
   existing environment files. Do not commit or publish that copy.
2. Generate three independent random credentials for JWT, the database, and the bridge.
3. Using an already authenticated administrative connection, change only the existing
   PostgreSQL role password with `ALTER ROLE`; preserve role name, database, and data.
4. Update `POSTGRES_PASSWORD`, the password inside `DATABASE_URL`, `SECRET_KEY`, and
   the bridge settings in private configuration. Confirm the new database connection.
5. Recreate the backend and update any external Finance client. JWT rotation invalidates
   existing access and refresh tokens; users sign in again with their unchanged passwords.
6. Check backend health, authentication boundaries, bridge connectivity, and unchanged
   application data. Securely remove temporary rollback copies after verification.

Never retain the old JWT signing key as a fallback when rotating a compromised key.
Source changes alone do not revoke previously disclosed credentials. Git history
cleanup and the remaining publication findings are separate work.
