# Backend image. Build from the REPOSITORY ROOT so the synthetic data (the demo family) can be copied in:
#   docker build -f backend/Dockerfile -t caresaathi-api .
# The code sits at /srv/backend so that app/config.py finds data/synthetic at /srv/data/synthetic.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv/backend

COPY backend/pyproject.toml ./
# Install the dependencies first so this layer is cached when only the code changes.
RUN python - <<'EOF'
import tomllib, subprocess, sys
deps = tomllib.load(open("pyproject.toml", "rb"))["project"]["dependencies"]
subprocess.check_call([sys.executable, "-m", "pip", "install", *deps])
EOF

COPY backend/ /srv/backend/
COPY data/synthetic/ /srv/data/synthetic/
RUN rm -rf /srv/backend/tests /srv/backend/.venv

# Migrations run as the database owner (DATABASE_URL_ADMIN), then the API starts as an unprivileged user.
RUN useradd --system --home /srv --shell /usr/sbin/nologin caresaathi && mkdir -p /srv/.storage && chown -R caresaathi /srv/.storage
USER caresaathi
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
