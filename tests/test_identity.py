"""Identidad OBO: cabeceras del proxy de Databricks Apps y cliente con el token del usuario."""
from databricks.sdk import config as sdk_config

import identity


def _offline(host, **_):
    raise ValueError("sin red en los tests")


def test_user_client_uses_user_token_even_with_app_sp_credentials(monkeypatch):
    # El SDK consulta /.well-known/databricks-config al crear el cliente; aquí no hay workspace.
    monkeypatch.setattr(sdk_config, "get_host_metadata", _offline)
    # En la App conviven el token del usuario y las credenciales OAuth del SP en el entorno.
    monkeypatch.setenv("DATABRICKS_HOST", "https://adb-123.1.azuredatabricks.net")
    monkeypatch.setenv("DATABRICKS_CLIENT_ID", "sp-client-id")
    monkeypatch.setenv("DATABRICKS_CLIENT_SECRET", "sp-secret")
    w = identity.user_client("tok-usuario")
    assert w.config.auth_type == "pat"
    assert w.config.authenticate() == {"Authorization": "Bearer tok-usuario"}


def test_from_headers_normalizes_and_ignores_blank_values():
    who = identity.from_headers({"x-forwarded-email": "  Ana.Perez@GrupoBimbo.com ", "x-forwarded-user": " ",
                                 "x-forwarded-access-token": ""})
    assert who == identity.Identity(email="ana.perez@grupobimbo.com")
    assert identity.from_headers({}) == identity.Identity()


def test_columns():
    who = identity.Identity(email="a@grupobimbo.com", user="1@2", username="a", verified=True)
    assert who.columns() == {"sso_email": "a@grupobimbo.com", "sso_user": "1@2", "sso_username": "a",
                             "sso_verified": True}
