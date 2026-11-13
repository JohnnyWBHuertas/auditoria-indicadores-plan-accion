"""Registro de reproducibilidad de las auditorias (E11, V-M6) y de rendimiento (E10).

Cada ejecucion guarda la version del prototipo, del modelo y de las reglas,
los umbrales, el entorno y una huella SHA-256 de los indicadores de entrada.
Con ello dos corridas se pueden comparar: si la huella y la configuracion
coinciden, los senalamientos deben coincidir (ver comparar_ejecuciones).
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
import time
from pathlib import Path

from django.conf import settings

VERSION_APLICACION = "1.2.0"
# Historial de las reglas:
#   R-1.0  la divergencia operativa comparaba tambien la formula (texto libre).
#   R-1.1  la divergencia compara solo unidad de medida y periodicidad.
#   R-1.2  la divergencia exige ambos valores presentes; si falta uno se registra «valor faltante».
VERSION_REGLAS = "R-1.2"

CAMPOS_HUELLA = [
    "nombre", "objetivo", "formula", "unidad_medida", "linea_base", "meta", "periodicidad",
    "fuente", "responsable", "programa", "bien_servicio", "producto_actividad_proyecto", "vigencia",
]


def huella_datos(vigencia: str) -> str:
    """SHA-256 del contenido de los indicadores de la vigencia (independiente de los ID)."""
    from apps.ingesta.models import Indicador

    filas = sorted(
        json.dumps([getattr(i, c) for c in CAMPOS_HUELLA] + [i.dependencia.nombre], ensure_ascii=False)
        for i in Indicador.objects.filter(vigencia=vigencia).select_related("dependencia")
    )
    return hashlib.sha256("\n".join(filas).encode("utf-8")).hexdigest()


def revision_modelo() -> str:
    """Revision (hash de commit) del modelo en el almacen local de Hugging Face; '' si no se encuentra."""
    try:
        from huggingface_hub import constants

        nombre = settings.NLP_ENGINE["EMBEDDING_MODEL"]
        if "/" not in nombre:
            nombre = "sentence-transformers/" + nombre
        ref = Path(constants.HF_HUB_CACHE) / ("models--" + nombre.replace("/", "--")) / "refs" / "main"
        return ref.read_text().strip() if ref.exists() else ""
    except Exception:
        return ""


def versiones_entorno() -> dict:
    def version(modulo):
        try:
            return __import__(modulo).__version__
        except Exception:
            return ""

    return {
        "python": platform.python_version(),
        "sistema": platform.system() + " " + platform.release(),
        "django": version("django"),
        "sentence_transformers": version("sentence_transformers"),
        "torch": version("torch"),
        "numpy": version("numpy"),
    }


def parametros_de_ejecucion() -> dict:
    return {
        "umbral_duplicidad": settings.NLP_ENGINE["UMBRAL_DUPLICIDAD"],
        "umbral_clonacion_textual": settings.NLP_ENGINE["UMBRAL_CLONACION_TEXTUAL"],
        "entorno": versiones_entorno(),
    }


def memoria_pico_mb() -> float | None:
    """Memoria maxima residente del proceso, en MB (sin dependencias externas)."""
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            class Contadores(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            c = Contadores()
            c.cb = ctypes.sizeof(c)
            proceso = ctypes.windll.kernel32.GetCurrentProcess()
            ctypes.windll.psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Contadores), wintypes.DWORD]
            if ctypes.windll.psapi.GetProcessMemoryInfo(proceso, ctypes.byref(c), c.cb):
                return round(c.PeakWorkingSetSize / 1024 / 1024, 1)
            return None
        import resource

        pico = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return round((pico / 1024 / 1024) if sys.platform == "darwin" else (pico / 1024), 1)
    except Exception:
        return None


class Cronometro:
    """Mide el tiempo (s) de cada etapa de una corrida."""

    def __init__(self):
        self.t0 = time.perf_counter()
        self.etapas: dict[str, float] = {}

    def etapa(self, nombre):
        cron = self

        class _Ctx:
            def __enter__(self):
                self.t = time.perf_counter()

            def __exit__(self, *exc):
                cron.etapas[nombre] = round(time.perf_counter() - self.t, 3)

        return _Ctx()

    def resultado(self) -> dict:
        r = dict(self.etapas)
        r["total_s"] = round(time.perf_counter() - self.t0, 3)
        r["memoria_pico_mb"] = memoria_pico_mb()
        return r
