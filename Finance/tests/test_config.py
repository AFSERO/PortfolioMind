import pytest
from investment_intelligence.database import database_url


def test_environment_config_preserves_special_characters():
    password = "test-only:@/% value"
    url = database_url({
        "II_DB_NAME": "ii_test", "II_DB_USER": "test_user", "II_DB_PASSWORD": password
    })
    assert url.drivername == "postgresql+psycopg"
    assert url.database == "ii_test"
    assert url.host == "127.0.0.1"
    assert url.port == 55432
    assert url.password == password
    assert password not in str(url)


@pytest.mark.parametrize("key", ["II_DB_NAME", "II_DB_USER", "II_DB_PASSWORD"])
def test_required_config_has_no_credential_fallback(key):
    env = {"II_DB_NAME": "test", "II_DB_USER": "test", "II_DB_PASSWORD": "test-only"}
    del env[key]
    with pytest.raises(ValueError, match=key):
        database_url(env)


@pytest.mark.parametrize("port", ["abc", "0", "65536"])
def test_invalid_port(port):
    with pytest.raises(ValueError, match="II_DB_PORT"):
        database_url({
            "II_DB_NAME": "test", "II_DB_USER": "test", "II_DB_PASSWORD": "test-only",
            "II_DB_PORT": port,
        })
