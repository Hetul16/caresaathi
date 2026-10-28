"""A public (https) deployment must not start with development secrets or default database passwords."""
from app.config import Settings, production_problems


def _s(**kw):
    base = dict(public_base_url="https://care.example.org", jwt_secret="j" * 40, token_pepper="p" * 40,
                database_url_app="postgresql+psycopg://a:strong@db/x", database_url_auth="postgresql+psycopg://b:strong@db/x",
                database_url_worker="postgresql+psycopg://c:strong@db/x", allow_demo_seed=False)
    base.update(kw)
    return Settings(**base)


def test_local_development_is_never_blocked():
    assert production_problems(Settings(public_base_url="http://localhost:3000")) == []


def test_a_proper_public_configuration_passes():
    assert production_problems(_s()) == []


def test_default_secrets_and_passwords_are_refused_on_a_public_address():
    problems = production_problems(_s(jwt_secret="dev-only-change-me", token_pepper="short",
                                      database_url_app="postgresql+psycopg://caresaathi_app:change-me-app@db/x"))
    assert any("JWT_SECRET" in p for p in problems) and any("TOKEN_PEPPER" in p for p in problems) and any("DATABASE_URL_APP" in p for p in problems)
