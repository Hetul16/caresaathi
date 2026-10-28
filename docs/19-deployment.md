# 19. Deployment: getting a public link for the judges

Judges need a link they can open. Three ways, from fastest to most solid. Everything uses synthetic data only (CLAUDE.md, rule 8).

| Way | Time | Good for | Weakness |
| --- | --- | --- | --- |
| A. Tunnel from your own laptop | 15 minutes | Trying it on a phone today, a backup demo | Dies when the laptop sleeps or the tunnel stops |
| B. One cheap server with Docker | 1 to 2 hours | The real submission | Costs a few dollars; needs a domain or the server's address |
| C. Managed platform (Render, Fly, Railway) | 2 to 3 hours | No server to look after | Three services plus a database to set up |

Recommendation: **B** for the submission link, **A** as a backup during judging.

## What is deployed

`api` (FastAPI, runs the database migrations on start), `web` (Next.js, forwards `/api/*` to `api`), `db` (Postgres 16 with the baseline schema and roles) and `caddy` (one public address, automatic HTTPS). Files are kept on a Docker volume. There is no MinIO, no worker and no hosted backend service.

## B. One server with Docker

1. Get a small Linux server (2 GB memory is enough) and a name pointing to it (an `A` record). Install Docker and the Compose plugin. Open ports 80 and 443.
2. Copy the repository to the server (`git clone https://github.com/Hetul16/caresaathi.git`).
3. `cp .env.production.example .env.production` and fill it in. Make secrets with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` for `JWT_SECRET` and `TOKEN_PEPPER`. Set `PUBLIC_BASE_URL=https://your.domain` and `SITE_ADDRESS=your.domain`. Put the Meta key in `META_API_KEY`. Keep `SPEND_LIMIT_USD` at your budget. The server refuses to start on an `https` address while a development secret or a default `change-me` password is still set.
4. Also create a file named `.env` next to it with `POSTGRES_PASSWORD`, `S3_ACCESS_KEY` and `S3_SECRET_KEY` (compose reads these for the database and validates the MinIO names). Use the same `POSTGRES_PASSWORD` inside `DATABASE_URL_ADMIN`.
5. Start the database alone first and set the role passwords. The roles are created with placeholder passwords, so change them before anything else uses them:
   ```
   docker compose up -d db
   docker compose exec db psql -U postgres -d caresaathi -c "ALTER ROLE caresaathi_app PASSWORD '<app password>'" -c "ALTER ROLE caresaathi_auth PASSWORD '<auth password>'" -c "ALTER ROLE caresaathi_worker PASSWORD '<worker password>'" -c "ALTER ROLE caresaathi_readonly PASSWORD '<readonly password>'"
   ```
   Use the same passwords in the three `DATABASE_URL_*` lines of `.env.production`.
6. `docker compose --profile app up -d --build`. The first start builds both images and applies migrations 0002 to 0010.
7. Open `https://your.domain`. Sign up, press "Load the demo family", and walk through the demo path in `docs/06-testing-demo.md`.
8. Check: `https://your.domain/trust` loads without signing in; a doctor link and an Emergency Card link open in a private window; the model name on `/trust` is the live one.

Update later with `git pull && docker compose --profile app up -d --build`. Back up with `docker compose exec db pg_dump -U postgres caresaathi > backup.sql`.

## A. Tunnel from your laptop

1. Install `cloudflared` (no account needed for a quick tunnel). Start the backend and `npm run dev` or `npm run build && npm start` as usual.
2. `cloudflared tunnel --url http://localhost:3000` prints an `https://something.trycloudflare.com` address.
3. For doctor links and Emergency Card links to carry that address, restart the backend with `PUBLIC_BASE_URL` set to it. Because that is an `https` address, set real values for `JWT_SECRET` and `TOKEN_PEPPER` first, or the backend will refuse to start (this is intended).
4. The address changes each time the tunnel restarts, so do not put it in the submission.

## Before you submit the link

- Signing up works from a phone on mobile data, and the microphone prompt appears (this needs HTTPS).
- A second browser cannot open another family's patient (try the patient address while signed in as a different user).
- `SPEND_LIMIT_USD` is set, and `python scripts/spend.py` (in `backend/`) shows what has been used.
- The repository is public and contains no `.env` or `.env.production` (check with `git ls-files | grep env`).
- Say plainly on the page that all data is fictional (the "Synthetic patient" marker is already shown).

## Limits to know about

- The spend ledger is a file on the server's storage volume; two API copies would each count separately. Run one.
- Uploaded files and the ledger live on the `storage` volume; `docker compose down -v` deletes it.
- Browser text-to-speech depends on the voices installed on the viewer's device, so Hindi and Marathi read-aloud may fall back to a default voice on some phones.
