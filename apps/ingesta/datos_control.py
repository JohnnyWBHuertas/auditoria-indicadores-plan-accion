"""Conjunto de control del prototipo: nueve indicadores sinteticos (no son el
dataset real del Ministerio) construidos para producir exactamente un caso de
cada tipo de hallazgo y un indicador sin inconsistencia esperada. Se usa en la
validacion funcional (apps.auditoria.validacion) y en la carga de demostracion.
"""

VIGENCIA_DEMO = "2026"

# Datos sinteticos (no son el dataset real del Ministerio) construidos para
# ejercitar cada uno de los 5 tipos de hallazgo del prototipo, siguiendo los
# patrones documentados en el Informe de Duplicidad de Indicadores PAA 2026.
INDICADORES_DEMO = [
    # --- Caso: CLONACION (mismo nombre+formula+meta, distinto producto/actividad) ---
    dict(
        nombre="Proyectos culturales apoyados mediante el Programa Nacional de Concertación Cultural",
        objetivo="Fortalecer procesos culturales de las comunidades del país.",
        formula="Sumatoria de proyectos culturales apoyados en la vigencia",
        unidad_medida="Número", linea_base="0", meta="150", periodicidad="anual",
        fuente="Sistema PA", responsable="Grupo de Convocatorias",
        dependencia_nombre="Grupo de Convocatorias y Estímulos a las Artes, los Saberes y las Culturas",
        programa="Programa Nacional de Concertación Cultural", bien_servicio="Apoyo a proyectos culturales",
        producto_actividad_proyecto="Modalidad Artes Visuales",
    ),
    dict(
        nombre="Proyectos culturales apoyados mediante el Programa Nacional de Concertación Cultural",
        objetivo="Fortalecer procesos culturales de las comunidades del país.",
        formula="Sumatoria de proyectos culturales apoyados en la vigencia",
        unidad_medida="Número", linea_base="0", meta="150", periodicidad="anual",
        fuente="Sistema PA", responsable="Grupo de Convocatorias",
        dependencia_nombre="Grupo de Convocatorias y Estímulos a las Artes, los Saberes y las Culturas",
        programa="Programa Nacional de Concertación Cultural", bien_servicio="Apoyo a proyectos culturales",
        producto_actividad_proyecto="Modalidad Música",
    ),
    # --- Caso: DUPLICIDAD semantica (mismo proposito, redaccion distinta) ---
    dict(
        nombre="Número de acciones de circulación artística y cultural realizadas",
        objetivo="Divulgar la producción artística nacional en espacios públicos.",
        formula="Conteo de acciones de circulación ejecutadas",
        unidad_medida="Número", linea_base="0", meta="40", periodicidad="anual",
        fuente="Sistema PA", responsable="Despacho Museo Nacional",
        dependencia_nombre="Despacho del Museo Nacional de Colombia",
        programa="Museos en diálogo con las memorias, los saberes y los territorios",
        bien_servicio="Circulación artística", producto_actividad_proyecto="Agenda expositiva",
    ),
    dict(
        nombre="Actividades de divulgación artística y cultural desarrolladas",
        objetivo="Promover la circulación de la producción artística nacional.",
        formula="Total de actividades de divulgación cultural desarrolladas",
        unidad_medida="Número", linea_base="0", meta="40", periodicidad="anual",
        fuente="Sistema PA", responsable="Despacho Museo Nacional",
        dependencia_nombre="Despacho del Museo Nacional de Colombia",
        programa="Museos en diálogo con las memorias, los saberes y los territorios",
        bien_servicio="Circulación artística", producto_actividad_proyecto="Agenda pedagógica",
    ),
    # --- Caso: DIVERGENCIA OPERATIVA (misma redaccion, distinta ficha tecnica) ---
    dict(
        nombre="Bibliotecas públicas asistidas técnicamente",
        objetivo="Fortalecer la Red Nacional de Bibliotecas Públicas.",
        formula="Número de bibliotecas que reciben asistencia técnica en el trimestre",
        unidad_medida="Número", linea_base="0", meta="120", periodicidad="trimestral",
        fuente="Sistema PA", responsable="Biblioteca Nacional",
        dependencia_nombre="Despacho de la Biblioteca Nacional de Colombia",
        programa="Fortalecimiento integral de la Red Nacional de Bibliotecas Públicas",
        bien_servicio="Asistencia técnica bibliotecas", producto_actividad_proyecto="Visitas territoriales",
    ),
    dict(
        nombre="Bibliotecas públicas asistidas técnicamente",
        objetivo="Fortalecer la Red Nacional de Bibliotecas Públicas.",
        formula="Porcentaje de bibliotecas asistidas frente al total de la Red en la vigencia",
        unidad_medida="Porcentaje", linea_base="0", meta="80", periodicidad="anual",
        fuente="Sistema PA", responsable="Biblioteca Nacional",
        dependencia_nombre="Despacho de la Biblioteca Nacional de Colombia",
        programa="Fortalecimiento integral de la Red Nacional de Bibliotecas Públicas",
        bien_servicio="Asistencia técnica bibliotecas", producto_actividad_proyecto="Convocatoria anual",
    ),
    # --- Caso: INCOMPLETITUD DE ATRIBUTOS ---
    dict(
        nombre="Entidades territoriales con asistencia técnica en gobernanza cultural",
        objetivo="", formula="", unidad_medida="", linea_base="", meta="30", periodicidad="no_especificada",
        fuente="", responsable="",
        dependencia_nombre="Despacho de la Dirección de Fomento Regional",
        programa="Estrategia territorial de Gobernanza Cultural para la Paz",
        bien_servicio="Asistencia territorial", producto_actividad_proyecto="Mesas técnicas",
    ),
    # --- Caso: PROBLEMA METODOLOGICO (redactado como actividad) ---
    dict(
        nombre="Cierre de procesos contractuales",
        objetivo="Formalizar el cierre administrativo de contratos de infraestructura.",
        formula="No aplica",
        unidad_medida="No aplica", linea_base="0", meta="20", periodicidad="anual",
        fuente="Sistema PA", responsable="Grupo de Infraestructura Cultural",
        dependencia_nombre="Grupo de Infraestructura Cultural",
        programa="Construcción, adecuación y mantenimiento de infraestructuras culturales a nivel Nacional",
        bien_servicio="Gestión contractual", producto_actividad_proyecto="Cierre de vigencia",
    ),
    # --- Caso limpio (sin hallazgos esperados) ---
    dict(
        nombre="Porcentaje de trámites de expedición de CDP tramitados dentro del término",
        objetivo="Garantizar la oportunidad en la gestión presupuestal.",
        formula="Trámites resueltos en término / Total de trámites recibidos",
        unidad_medida="Porcentaje", linea_base="85", meta="95", periodicidad="mensual",
        fuente="Sistema PA", responsable="Grupo de Gestión Financiera",
        dependencia_nombre="Grupo de Gestión Financiera",
        programa="Gestión presupuestal", bien_servicio="Gestión de CDP",
        producto_actividad_proyecto="Trámites presupuestales",
    ),
]
