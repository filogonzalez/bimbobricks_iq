"""Lectura de archivos del Volume `media` (vídeo y bloque de noticias).

MEDIA_VOLUME viene del recurso uc_securable de la App (`catalogo.esquema.volumen`) o puede ser
una ruta /Volumes/... o un directorio local (tests). Las Apps no montan /Volumes, así que en
la App se lee con la Files API del SDK usando el service principal de la App.
"""
import logging
import os
import threading
import time
from pathlib import Path

log = logging.getLogger("bimbobricks.volume")


def volume_root(value=None):
    v = (value if value is not None else os.getenv("MEDIA_VOLUME", "")).strip()
    if not v:
        return ""
    if v.startswith("/"):
        return v.rstrip("/")
    parts = v.split(".")
    if len(parts) != 3:
        raise ValueError("MEDIA_VOLUME inválido: %r (esperado catalogo.esquema.volumen o /Volumes/...)" % v)
    return "/Volumes/" + "/".join(parts)


class VolumeReader:
    def __init__(self, root=None):
        self.root = volume_root(root)
        self._local = bool(self.root) and Path(self.root).is_dir()
        self._ws = None

    def read(self, rel):
        """Devuelve los bytes de <root>/<rel> o None si no existe."""
        if not self.root:
            return None
        path = "%s/%s" % (self.root, rel.lstrip("/"))
        if self._local:
            p = Path(path)
            return p.read_bytes() if p.is_file() else None
        from databricks.sdk.errors import NotFound

        if self._ws is None:
            from databricks.sdk import WorkspaceClient

            self._ws = WorkspaceClient()
        try:
            return self._ws.files.download(path).contents.read()
        except NotFound:
            return None


class CachedFile:
    """Cachea un archivo del Volume y lo relee cada `ttl` segundos (los errores no tumban la página)."""

    def __init__(self, reader, rel, ttl):
        self.reader, self.rel, self.ttl = reader, rel, ttl
        self._value, self._at = None, float("-inf")
        self._lock = threading.Lock()

    def get(self):
        if time.monotonic() - self._at < self.ttl:
            return self._value
        with self._lock:
            if time.monotonic() - self._at >= self.ttl:
                try:
                    self._value = self.reader.read(self.rel)
                except Exception:  # noqa: BLE001 - se sirve la última versión buena
                    log.exception("No se pudo leer %s del Volume", self.rel)
                self._at = time.monotonic()
        return self._value
