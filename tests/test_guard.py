"""Checagens do guard_secrets.py. Roda com pytest ou `python tests/test_guard.py`."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("g", Path(__file__).resolve().parents[1] / "src/sddkit/templates/hooks/guard_secrets.py")
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)


def test_url_password_templates_are_not_secrets():  # regressão: 16 de 18 achados num projeto real eram templates
    for line in ("mongodb://${user}:${password}@${host}:${port}", "mongodb://${U}:${encodeURIComponent(env.PASS)}@mongo",
                 "postgres://app:$DB_PASSWORD@db/x", "https://user:<token>@github.com", "amqp://u:{{ rabbit_pass }}@mq"):
        assert not g.scan(line), line


def test_literal_url_passwords_are_secrets():
    for line in ("mongodb://${U}:${ME_PASS:-hunter2secret}@mongo", "postgres://app:s3cretP4ss@db/x", "redis://u:$uper1234@r"):
        assert g.scan(line), line


if __name__ == "__main__":
    test_url_password_templates_are_not_secrets()
    test_literal_url_passwords_are_secrets()
    print("ok")
