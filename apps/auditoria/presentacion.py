"""Presentacion legible de los atributos comparados de un hallazgo.

El hallazgo guarda sus atributos comparados como un diccionario (JSON) para
conservar la trazabilidad exacta. Para el auditor, que no tiene por que leer
JSON, este modulo los convierte en una explicacion corta y una tabla
comparativa con las diferencias resaltadas.
"""

from __future__ import annotations

from apps.gobernanza.models import Dependencia
from apps.ingesta.models import Indicador

ETIQUETAS = {
    "nombre": "Nombre del indicador",
    "objetivo": "Objetivo",
    "formula": "Fórmula de cálculo",
    "unidad_medida": "Unidad de medida",
    "linea_base": "Línea base",
    "meta": "Meta",
    "periodicidad": "Periodicidad",
    "fuente": "Fuente de verificación",
    "responsable": "Responsable",
    "dependencia_id": "Dependencia",
    "vigencia": "Vigencia",
    "producto_actividad_proyecto": "Producto o actividad asociado",
}

ORDEN_CLONACION = ["nombre", "formula", "meta", "dependencia_id", "vigencia", "producto_actividad_proyecto"]
SIN_DATO = "(sin dato)"
PERIODICIDADES = dict(Indicador.PERIODICIDAD_CHOICES)


def _valor(campo, valor, dependencias):
    if valor in (None, "", "no_especificada"):
        return SIN_DATO
    if campo == "dependencia_id":
        return dependencias.get(valor, f"Dependencia #{valor}")
    if campo == "periodicidad":
        return PERIODICIDADES.get(valor, valor)
    return str(valor)


def _porcentaje(valor):
    return None if valor is None else f"{round(float(valor) * 100)} %"


def _tabla(atributos, campos):
    a, b = atributos.get("indicador_a", {}), atributos.get("indicador_b", {})
    ids = {v for snap in (a, b) for k, v in snap.items() if k == "dependencia_id"}
    dependencias = dict(Dependencia.objects.filter(pk__in=ids).values_list("pk", "nombre"))
    filas = []
    for campo in campos:
        va, vb = _valor(campo, a.get(campo), dependencias), _valor(campo, b.get(campo), dependencias)
        filas.append({"etiqueta": ETIQUETAS.get(campo, campo), "a": va, "b": vb, "igual": va == vb})
    return filas


def presentar(hallazgo) -> dict:
    """Devuelve {'explicacion', 'indicadores': [(etiqueta, valor)], 'filas', 'faltantes', 'diligenciados'}."""
    at = hallazgo.atributos_comparados or {}
    r = {"explicacion": "", "medidas": [], "filas": [], "faltantes": [], "diligenciados": []}

    if hallazgo.tipo == "duplicidad":
        r["explicacion"] = (
            "Se compararon el nombre y el objetivo de los dos indicadores. El modelo de inteligencia artificial "
            "midió qué tan parecido es su significado; como no hay diferencias de unidad ni de periodicidad, "
            "se señala como posible duplicidad."
        )
        r["medidas"] = [("Similitud de significado", _porcentaje(at.get("similitud_semantica")))]
        r["filas"] = _tabla(at, ["nombre", "objetivo"])

    elif hallazgo.tipo == "clonacion":
        r["explicacion"] = (
            "Se compararon el nombre, la fórmula y la meta de los dos indicadores. El texto es casi idéntico, "
            "pero cambia la dependencia, la vigencia, la meta o el producto asociado: parece el mismo indicador "
            "copiado con una variación mínima."
        )
        r["medidas"] = [("Coincidencia del texto (nombre, fórmula y meta)", _porcentaje(at.get("ratio_textual_nombre_formula_meta")))]
        r["filas"] = _tabla(at, ORDEN_CLONACION)

    elif hallazgo.tipo == "divergencia_operativa":
        r["explicacion"] = (
            "Los dos indicadores significan lo mismo, pero se miden de forma distinta: difieren en la unidad de "
            "medida o en la periodicidad. Así no se pueden consolidar ni comparar directamente."
        )
        r["medidas"] = [("Similitud de significado", _porcentaje(at.get("similitud_semantica")))]
        r["filas"] = _tabla(at, ["unidad_medida", "periodicidad"])

    elif hallazgo.tipo == "incompletitud_atributos":
        exigidos = at.get("campos_exigidos", [])
        faltantes = set(at.get("campos_faltantes", []))
        r["explicacion"] = (
            "Se revisaron los atributos que debe tener la hoja de vida de un indicador. "
            f"Faltan {len(faltantes)} de {len(exigidos)}."
        )
        r["faltantes"] = [ETIQUETAS.get(c, c) for c in exigidos if c in faltantes]
        r["diligenciados"] = [ETIQUETAS.get(c, c) for c in exigidos if c not in faltantes]

    elif hallazgo.tipo == "problema_metodologico":
        r["explicacion"] = (
            "Un indicador debe nombrarse como una magnitud que se pueda medir y acumular (por ejemplo, "
            "«Número de…» o «Porcentaje de…»). Este nombre empieza con una acción puntual, es decir, "
            "describe una actividad y no una medida."
        )
        r["medidas"] = [("Nombre revisado", at.get("nombre", "")), ("Clasificación", "Redactado como actividad")]

    return r
