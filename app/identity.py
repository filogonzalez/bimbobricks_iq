"""Identidad de quien usa la App (autorización en nombre del usuario, OBO).

El proxy de Databricks Apps autentica cada petición y reenvía a la App:
  X-Forwarded-Email, X-Forwarded-User, X-Forwarded-Preferred-Username  identidad del IdP
  X-Forwarded-Access-Token  token OAuth del usuario, limitado a los `user_api_scopes` de la App
La identidad que se guarda sale siempre de estas cabeceras, nunca del cuerpo del formulario. Si llega
el token, se confirma llamando a /Me como el propio usuario (scope iam.current-user:read); si el
correo de la cabecera no coincide, manda el del token.
"""
import logging
import os
from dataclasses import dataclass, replace
from typing import Optional

from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config

log = logging.getLogger("bimbobricks.identity")


@dataclass(frozen=True)
class Identity:
    email: Optional[str] = None
    user: Optional[str] = None
    username: Optional[str] = None
    verified: bool = False

    def columns(self):
        return {"sso_email": self.email, "sso_user": self.user, "sso_username": self.username,
                "sso_verified": self.verified}


def user_client(token):
    """WorkspaceClient que actúa como el usuario.

    auth_type="pat" es obligatorio: la App también tiene en el entorno las credenciales OAuth de su
    service principal y, sin él, el SDK rechaza la mezcla de métodos de autenticación.
    """
    return WorkspaceClient(config=Config(host=os.getenv("DATABRICKS_HOST"), token=token, auth_type="pat",
                                         http_timeout_seconds=5, retry_timeout_seconds=10))


def verified_email(token):
    """userName (en minúsculas) del dueño del token, o None si no se pudo verificar."""
    try:
        return (user_client(token).current_user.me().user_name or "").strip().lower() or None
    except Exception as e:  # noqa: BLE001 - verificar no debe impedir guardar el formulario
        log.warning("No se pudo verificar la identidad con el token del usuario (%s)", type(e).__name__)
        return None


def _header(headers, name):
    return (headers.get(name) or "").strip() or None


def from_headers(headers):
    ident = Identity(email=(_header(headers, "x-forwarded-email") or "").lower() or None,
                     user=_header(headers, "x-forwarded-user"),
                     username=_header(headers, "x-forwarded-preferred-username"))
    token = _header(headers, "x-forwarded-access-token")
    confirmed = verified_email(token) if token else None
    if not confirmed:
        return ident
    if ident.email and ident.email != confirmed:
        log.warning("X-Forwarded-Email no coincide con el token del usuario; se guarda el del token")
    return replace(ident, email=confirmed, verified=True)
