"""Motor de reglas de auditoria (CU3 + CU4).

Cada funcion evaluar_* materializa un tipo de hallazgo de la Tabla de
definiciones de la monografia y deja constancia obligatoria de regla
aplicada + atributos comparados + evidencia (requisito de explicabilidad).
El juicio de equivalencia de proposito sigue siendo del auditor humano:
todo hallazgo nace en estado "pendiente".

La unica inteligencia artificial del sistema es el modelo de embeddings
(apps.nlp_engine), que propone pares candidatos; la clasificacion por tipo
y las demas verificaciones son reglas deterministas.
"""

from __future__ import annotations

import difflib
import re

from django.conf import settings
from django.utils import timezone

from apps.gobernanza.models import EjecucionAuditoria, ParametroGobernanza
from apps.ingesta.models import Indicador
from apps.nlp_engine import embeddings as nlp
from apps.nlp_engine.models import ParCandidato

from .models import CorrespondenciaManual, Hallazgo, ReglaAuditoria

CAMPOS_CLONACION = ["nombre", "formula", "meta"]
CAMPOS_CLONACION_VARIABLES = ["dependencia_id", "vigencia", "meta", "producto_actividad_proyecto"]

# Nota de diseno: 'formula' se redacta en texto libre y casi siempre difiere
# en la forma aunque describa el mismo calculo, por lo que NO se usa como
# disparador de divergencia por desigualdad exacta (produciria falsos
# positivos sistematicos). Solo unidad_medida y periodicidad son lo bastante
# categoricos para que una desigualdad textual sea evidencia de divergencia.
CAMPOS_DIVERGENCIA = ["unidad_medida", "periodicidad"]

# Heuristica lexica del Informe de Duplicidad de Indicadores PAA 2026: un
# nombre que inicia en verbo o sustantivo de accion puntual describe una
# actividad y no una magnitud medible acumulable.
PATRON_ACTIVIDAD = re.compile(
    r"^(entregar|realizar|crear|cerrar|cierre de|entrega de|creación de|"
    r"creacion de|implementar|adelantar|gestionar|elaborar)\b",
    re.IGNORECASE,
)


def _normalizar(texto: str) -> str:
    return re.sub(r"\s+", " ", (texto or "").strip().lower())


def _ratio_textual(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, _normalizar(a), _normalizar(b)).ratio()


def _snapshot(indicador: Indicador, campos: list[str]) -> dict:
    return {campo: getattr(indicador, campo, None) for campo in campos}


def _obtener_regla(tipo_hallazgo: str) -> ReglaAuditoria:
    regla = ReglaAuditoria.objects.filter(tipo_hallazgo=tipo_hallazgo, activa=True).first()
    if regla is None:
        raise RuntimeError(
            f"No hay una ReglaAuditoria activa para '{tipo_hallazgo}'. "
            "Ejecute 'manage.py seed_catalogo_gobernanza' primero."
        )
    return regla


def evaluar_pares_candidatos(ejecucion: EjecucionAuditoria, vigencia: str) -> dict:
    """Clasifica cada ParCandidato de la vigencia en clonacion, divergencia
    operativa o duplicidad (CU2 -> CU3/CU4). Cada ejecucion reevalua todos
    los pares vigentes, de modo que repetir la auditoria produce el mismo
    resultado."""
    conteo = {"clonacion": 0, "divergencia_operativa": 0, "duplicidad": 0}

    regla_clonacion = _obtener_regla("clonacion")
    regla_divergencia = _obtener_regla("divergencia_operativa")
    regla_duplicidad = _obtener_regla("duplicidad")

    umbral_clonacion = settings.NLP_ENGINE["UMBRAL_CLONACION_TEXTUAL"]

    pares = ParCandidato.objects.filter(
        indicador_a__vigencia=vigencia,
        modelo=settings.NLP_ENGINE["EMBEDDING_MODEL"],
        similitud_coseno__gte=settings.NLP_ENGINE["UMBRAL_DUPLICIDAD"],
    ).select_related("indicador_a", "indicador_b").order_by("pk")

    for par in pares:
        a, b = par.indicador_a, par.indicador_b

        ratio_clonacion = min(_ratio_textual(getattr(a, c), getattr(b, c)) for c in CAMPOS_CLONACION)
        difiere_variable = any(
            getattr(a, campo) != getattr(b, campo) for campo in CAMPOS_CLONACION_VARIABLES
        )

        if ratio_clonacion >= umbral_clonacion and difiere_variable:
            _crear_hallazgo(
                ejecucion=ejecucion,
                regla=regla_clonacion,
                indicador_principal=a,
                indicador_relacionado=b,
                score=par.similitud_coseno,
                atributos_comparados={
                    "ratio_textual_nombre_formula_meta": round(ratio_clonacion, 4),
                    "indicador_a": _snapshot(a, CAMPOS_CLONACION + CAMPOS_CLONACION_VARIABLES),
                    "indicador_b": _snapshot(b, CAMPOS_CLONACION + CAMPOS_CLONACION_VARIABLES),
                },
                evidencia=(
                    f"Coincidencia textual del {ratio_clonacion:.0%} en nombre, fórmula y meta "
                    f"entre los indicadores #{a.pk} y #{b.pk}, con variación en "
                    "dependencia, vigencia, meta o producto/actividad asociado. "
                    "Patrón equivalente al de clonación identificado en el Informe de "
                    "Duplicidad de Indicadores PAA 2026."
                ),
            )
            conteo["clonacion"] += 1
        elif any(getattr(a, c) != getattr(b, c) for c in CAMPOS_DIVERGENCIA):
            _crear_hallazgo(
                ejecucion=ejecucion,
                regla=regla_divergencia,
                indicador_principal=a,
                indicador_relacionado=b,
                score=par.similitud_coseno,
                atributos_comparados={
                    "similitud_semantica": round(par.similitud_coseno, 4),
                    "indicador_a": _snapshot(a, CAMPOS_DIVERGENCIA),
                    "indicador_b": _snapshot(b, CAMPOS_DIVERGENCIA),
                },
                evidencia=(
                    f"Los indicadores #{a.pk} y #{b.pk} son semánticamente equivalentes "
                    f"(similitud {par.similitud_coseno:.0%}) pero difieren en unidad de "
                    "medida o periodicidad: falla de la dimensión de consistencia."
                ),
            )
            conteo["divergencia_operativa"] += 1
        else:
            _crear_hallazgo(
                ejecucion=ejecucion,
                regla=regla_duplicidad,
                indicador_principal=a,
                indicador_relacionado=b,
                score=par.similitud_coseno,
                atributos_comparados={
                    "similitud_semantica": round(par.similitud_coseno, 4),
                    "indicador_a": _snapshot(a, ["nombre", "objetivo"]),
                    "indicador_b": _snapshot(b, ["nombre", "objetivo"]),
                },
                evidencia=(
                    f"Los indicadores #{a.pk} y #{b.pk} persiguen el mismo propósito "
                    f"medible con redacción distinta (similitud semántica {par.similitud_coseno:.0%})."
                ),
            )
            conteo["duplicidad"] += 1

    pares.update(procesado=True)
    return conteo


def evaluar_incompletitud(ejecucion: EjecucionAuditoria, vigencia: str) -> int:
    regla = _obtener_regla("incompletitud_atributos")
    creados = 0
    for indicador in Indicador.objects.filter(vigencia=vigencia).order_by("pk"):
        diligenciados = indicador.atributos_diligenciados()
        faltantes = [campo for campo, ok in diligenciados.items() if not ok]
        if not faltantes:
            continue
        _crear_hallazgo(
            ejecucion=ejecucion,
            regla=regla,
            indicador_principal=indicador,
            indicador_relacionado=None,
            score=None,
            atributos_comparados={"campos_faltantes": faltantes, "campos_exigidos": list(diligenciados)},
            evidencia=(
                f"La hoja de vida del indicador #{indicador.pk} no diligencia: "
                f"{', '.join(faltantes)}."
            ),
        )
        creados += 1
    return creados


def evaluar_problema_metodologico(ejecucion: EjecucionAuditoria, vigencia: str) -> int:
    """Marca los nombres redactados como actividad puntual en lugar de
    magnitud medible (regla lexica)."""
    regla = _obtener_regla("problema_metodologico")
    creados = 0
    for indicador in Indicador.objects.filter(vigencia=vigencia).order_by("pk"):
        nombre = (indicador.nombre or "").strip()
        if not PATRON_ACTIVIDAD.match(nombre):
            continue
        _crear_hallazgo(
            ejecucion=ejecucion,
            regla=regla,
            indicador_principal=indicador,
            indicador_relacionado=None,
            score=None,
            atributos_comparados={"nombre": nombre, "clasificacion": "actividad"},
            evidencia=(
                f"El nombre del indicador #{indicador.pk} está redactado como actividad, "
                "no como magnitud medible acumulable: inicia con un verbo o sustantivo de "
                "acción puntual (regla léxica)."
            ),
        )
        creados += 1
    return creados


def _crear_hallazgo(
    *, ejecucion, regla, indicador_principal, indicador_relacionado, score, atributos_comparados, evidencia
) -> Hallazgo:
    return Hallazgo.objects.create(
        tipo=regla.tipo_hallazgo,
        ejecucion=ejecucion,
        regla_aplicada=regla,
        indicador_principal=indicador_principal,
        indicador_relacionado=indicador_relacionado,
        atributos_comparados=atributos_comparados,
        score_similitud=score,
        evidencia=evidencia,
    )


def es_trazable(hallazgo: Hallazgo) -> bool:
    """Un hallazgo es trazable si informa la regla aplicada, los atributos
    comparados y la evidencia que lo sustenta."""
    return bool(hallazgo.regla_aplicada_id and hallazgo.atributos_comparados and (hallazgo.evidencia or "").strip())


def conteo_correspondencia(ejecucion: EjecucionAuditoria) -> dict:
    """Variable observable 3: hallazgos coincidentes, no coincidentes y
    adicionales frente a la caracterizacion manual (se registran con
    CorrespondenciaManual cuando se dispone del reporte real)."""
    base = CorrespondenciaManual.objects.filter(hallazgo__ejecucion=ejecucion)
    return {
        "coincidente": base.filter(tipo_correspondencia="coincidente").count(),
        "no_coincidente": base.filter(tipo_correspondencia="no_coincidente").count(),
        "adicional": base.filter(tipo_correspondencia="adicional").count(),
    }


def ejecutar_auditoria(vigencia: str, usuario=None) -> EjecucionAuditoria:
    """Orquesta CU2 -> CU3 -> CU4 sobre una vigencia y deja el resumen de
    las 6 variables observables listo para el tablero (CU5)."""
    ejecucion = EjecucionAuditoria.objects.create(
        vigencia=vigencia,
        ejecutado_por=usuario,
        ejecucion_100_por_ciento_local=settings.EJECUCION_100_POR_CIENTO_LOCAL,
    )

    try:
        nlp.generar_embeddings_pendientes()
        nlp.generar_pares_candidatos(vigencia)
    except Exception:
        ejecucion.delete()  # sin embeddings no hay auditoria: no dejar una ejecucion vacia
        raise

    conteo_pares = evaluar_pares_candidatos(ejecucion, vigencia)
    conteo_incompletitud = evaluar_incompletitud(ejecucion, vigencia)
    conteo_metodologico = evaluar_problema_metodologico(ejecucion, vigencia)

    indicadores = Indicador.objects.filter(vigencia=vigencia)
    total_campos_exigidos = 0
    campos_diligenciados = 0
    for indicador in indicadores:
        atributos = indicador.atributos_diligenciados()
        total_campos_exigidos += len(atributos)
        campos_diligenciados += sum(1 for ok in atributos.values() if ok)

    hallazgos = list(ejecucion.hallazgos.all())
    trazables = sum(1 for h in hallazgos if es_trazable(h))

    parametros = ParametroGobernanza.objects.all()
    aplicados = parametros.filter(operacionalizacion="si")
    ejecucion.parametros_aplicados.set(aplicados)

    ejecucion.resumen_metricas = {
        "parametros_operacionalizados": aplicados.count(),
        "parametros_parciales": parametros.filter(operacionalizacion="parcial").count(),
        "parametros_totales": parametros.count(),
        "hallazgos_por_tipo": {
            "duplicidad": conteo_pares["duplicidad"],
            "clonacion": conteo_pares["clonacion"],
            "divergencia_operativa": conteo_pares["divergencia_operativa"],
            "incompletitud_atributos": conteo_incompletitud,
            "problema_metodologico": conteo_metodologico,
        },
        "correspondencia_manual": conteo_correspondencia(ejecucion),
        "proporcion_evidencia_trazable": round(trazables / len(hallazgos), 4) if hallazgos else None,
        "completitud_hoja_de_vida": (
            round(campos_diligenciados / total_campos_exigidos, 4) if total_campos_exigidos else None
        ),
        "ejecucion_100_por_ciento_local": settings.EJECUCION_100_POR_CIENTO_LOCAL,
    }
    ejecucion.finalizada_en = timezone.now()
    ejecucion.save(update_fields=["resumen_metricas", "finalizada_en"])
    return ejecucion
