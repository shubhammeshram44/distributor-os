"""
Regression test for AUTH-3: SECRET_KEY (the JWT signing secret for every
session/refresh token in the app) had a hardcoded default with no
production safety check -- a deployment started with ENVIRONMENT=production
but no SECRET_KEY override would run indefinitely with a forgeable,
publicly-known signing secret, a complete authentication bypass.

app.config now raises RuntimeError at import time when
ENVIRONMENT=production and SECRET_KEY still equals the known insecure
default. Since this check runs at module import time (the earliest,
safest point -- before any request can be served), it must be exercised
in a subprocess: app.config (and the app.main import chain that pulls it
in) is already cached in sys.modules for every other test in this suite,
so re-importing it in-process wouldn't re-run the module-level check.
"""
import subprocess
import sys
import textwrap


def _run_import_check(env_overrides: dict) -> subprocess.CompletedProcess:
    script = textwrap.dedent("""
        import app.config
        print("IMPORT_SUCCEEDED")
    """)
    import os
    env = dict(os.environ)
    env.pop("ENVIRONMENT", None)
    env.pop("SECRET_KEY", None)
    env.update(env_overrides)
    return subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=".",
        env=env,
        timeout=30,
    )


def test_production_with_default_secret_key_refuses_to_start():
    result = _run_import_check({
        "ENVIRONMENT": "production",
        "SECRET_KEY": "super-secret-key-distributor-os-2026",
    })
    assert result.returncode != 0, (
        "App must refuse to start when ENVIRONMENT=production and SECRET_KEY "
        "is still the hardcoded insecure default (see AUTH-3)."
    )
    assert "RuntimeError" in result.stderr
    assert "SECRET_KEY" in result.stderr
    assert "IMPORT_SUCCEEDED" not in result.stdout


def test_production_with_overridden_secret_key_starts_normally():
    result = _run_import_check({
        "ENVIRONMENT": "production",
        "SECRET_KEY": "a-real-unique-production-secret-from-a-vault",
    })
    assert result.returncode == 0, result.stderr
    assert "IMPORT_SUCCEEDED" in result.stdout


def test_development_with_default_secret_key_starts_normally():
    """The default SECRET_KEY must remain safe to use for local dev/tests --
    this check must only ever fire when ENVIRONMENT is explicitly production."""
    result = _run_import_check({
        "SECRET_KEY": "super-secret-key-distributor-os-2026",
    })
    assert result.returncode == 0, result.stderr
    assert "IMPORT_SUCCEEDED" in result.stdout
