"""First-time credential initialization must never overwrite existing files."""
import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts/bootstrap_local_secrets.py"
_SPEC = importlib.util.spec_from_file_location("bootstrap_local_secrets", _SCRIPT)
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


def test_bootstrap_generates_independent_credentials_without_disclosure(tmp_path, capsys):
    (tmp_path / ".env.example").write_text("SECRET_KEY=\nPOSTGRES_PASSWORD=\nDATABASE_URL=\nINTEGRATION_TOKEN=\n")
    _MODULE.initialize(tmp_path)
    data = dict(line.split("=", 1) for line in (tmp_path / ".env").read_text().splitlines())
    assert len(data["SECRET_KEY"]) >= 32
    assert len(data["POSTGRES_PASSWORD"]) >= 32
    assert data["SECRET_KEY"] != data["POSTGRES_PASSWORD"]
    assert data["POSTGRES_PASSWORD"] in data["DATABASE_URL"]
    assert data["INTEGRATION_TOKEN"] == ""
    output = capsys.readouterr().out
    assert data["SECRET_KEY"] not in output
    assert data["POSTGRES_PASSWORD"] not in output
    import os
    if os.name != "nt":
        assert (tmp_path / ".env").stat().st_mode & 0o077 == 0


def test_bootstrap_preserves_existing_configuration(tmp_path):
    (tmp_path / ".env.example").write_text("SECRET_KEY=\nPOSTGRES_PASSWORD=\nDATABASE_URL=\n")
    (tmp_path / ".env").write_text("existing-private-configuration")
    with pytest.raises(FileExistsError):
        _MODULE.initialize(tmp_path)
    assert (tmp_path / ".env").read_text() == "existing-private-configuration"
