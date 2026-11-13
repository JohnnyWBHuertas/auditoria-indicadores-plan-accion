"""Filtro por tipo de hallazgo con el subresultado «valor faltante».

«Valor faltante» no es un sexto tipo: es un subresultado de la regla de divergencia
operativa (clasificacion = valor_faltante). Para el auditor se consulta como una
categoria aparte, de modo que no se sume a las divergencias demostradas.
"""

VALOR_FALTANTE = "valor_faltante"
ETIQUETA_VALOR_FALTANTE = "Valor faltante (regla de divergencia)"


def filtrar_por_tipo(qs, tipo):
    if not tipo:
        return qs
    if tipo == VALOR_FALTANTE:
        return qs.filter(tipo="divergencia_operativa", atributos_comparados__clasificacion=VALOR_FALTANTE)
    if tipo == "divergencia_operativa":
        return qs.filter(tipo="divergencia_operativa").exclude(atributos_comparados__clasificacion=VALOR_FALTANTE)
    return qs.filter(tipo=tipo)


def etiqueta_tipo(h) -> str:
    if h.tipo == "divergencia_operativa" and (h.atributos_comparados or {}).get("clasificacion") == VALOR_FALTANTE:
        return ETIQUETA_VALOR_FALTANTE
    return h.get_tipo_display()


def opciones_de_tipo(choices):
    """Opciones del filtro: los cinco tipos mas el subresultado de valor faltante."""
    return list(choices) + [(VALOR_FALTANTE, ETIQUETA_VALOR_FALTANTE)]
