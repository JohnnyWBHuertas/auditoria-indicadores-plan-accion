"""Agrupacion de indicadores repetidos (mejora 1 del jurado V; E07, tratamiento de transversales).

Un mismo indicador registrado con el mismo nombre por varias dependencias
genera un par senalado por cada combinacion (por ejemplo, 115 registros de
«Recursos de gestion y apoyo» producen miles de pares). Esta agrupacion no
elimina ni modifica ningun registro, par ni hallazgo: solo los presenta
agrupados por nombre normalizado para que el auditor revise una vez cada grupo.

Cada grupo se rotula:
- ``transversal``: el nombre se repite en dos o mas dependencias.
- ``repeticion_en_dependencia``: el nombre se repite dentro de una sola
  dependencia (posible clonacion); no se oculta como si fuera transversal.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict

from apps.ingesta.models import Indicador

from .models import Hallazgo

TIPOS_DE_PAR = ("duplicidad", "clonacion", "divergencia_operativa")
CLASES = {
    "transversal": "Transversal (dos o más dependencias)",
    "repeticion_en_dependencia": "Repetición dentro de una dependencia",
}


def normalizar_nombre(nombre: str) -> str:
    """Minusculas, sin tildes ni signos y con espacios colapsados: «Recursos de gestión y apoyo» y
    «Recursos de Gestion y Apoyo» son el mismo nombre."""
    sin_tildes = unicodedata.normalize("NFKD", (nombre or "").lower())
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", sin_tildes)).strip()


def clase_de_grupo(dependencias: set) -> str:
    return "transversal" if len(dependencias) >= 2 else "repeticion_en_dependencia"


def resumen_agrupacion(ejecucion) -> dict:
    """Cuenta los pares senalados antes y despues de agruparlos. Los pares originales se conservan."""
    indicadores_por_nombre = defaultdict(list)
    for i in Indicador.objects.filter(vigencia=ejecucion.vigencia).select_related("dependencia"):
        indicadores_por_nombre[normalizar_nombre(i.nombre)].append(i)

    pares = Hallazgo.objects.filter(
        ejecucion=ejecucion, tipo__in=TIPOS_DE_PAR, indicador_relacionado__isnull=False
    ).select_related("indicador_principal", "indicador_relacionado")

    por_grupo = defaultdict(lambda: {"pares": 0, "tipos": Counter()})
    sueltos = 0
    total = 0
    for h in pares:
        total += 1
        clave = normalizar_nombre(h.indicador_principal.nombre)
        if clave == normalizar_nombre(h.indicador_relacionado.nombre):
            por_grupo[clave]["pares"] += 1
            por_grupo[clave]["tipos"][h.tipo] += 1
        else:
            sueltos += 1

    grupos = []
    for clave, datos in por_grupo.items():
        miembros = indicadores_por_nombre[clave]
        dependencias = {m.dependencia_id for m in miembros}
        grupos.append({
            "clave": clave,
            "nombre": miembros[0].nombre,
            "indicadores": len(miembros),
            "dependencias": sorted({m.dependencia.nombre for m in miembros}),
            "clase": clase_de_grupo(dependencias),
            "pares": datos["pares"],
            "tipos": dict(datos["tipos"]),
        })
    grupos.sort(key=lambda g: (-g["pares"], g["nombre"]))

    return {
        "pares_individuales": total,
        "pares_en_grupos": total - sueltos,
        "pares_sueltos": sueltos,
        "grupos": grupos,
        "grupos_transversales": sum(1 for g in grupos if g["clase"] == "transversal"),
        "grupos_en_dependencia": sum(1 for g in grupos if g["clase"] == "repeticion_en_dependencia"),
        "unidades_de_revision": len(grupos) + sueltos,
    }
