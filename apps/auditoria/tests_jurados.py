"""Pruebas de la version 1.2: reproducibilidad, rendimiento, agrupacion de transversales,
tablero de calidad, evaluacion de umbrales y controles basicos de seguridad."""

import io
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.auditoria import evaluacion, reproducibilidad, validacion
from apps.auditoria.agrupacion import resumen_agrupacion
from apps.auditoria.comparacion import comparar
from apps.auditoria.models import Hallazgo, ReglaAuditoria
from apps.auditoria.reglas import ejecutar_auditoria
from apps.dashboard.calidad import datos_calidad
from apps.dashboard.tests import usuario_con_rol
from apps.gobernanza.models import Dependencia, EjecucionAuditoria
from apps.ingesta.forms import CargaArchivoForm
from apps.ingesta.models import Indicador, PlantillaMapeoColumnas
from apps.nlp_engine import embeddings as nlp


def auditar_demo(usuario=None):
    with mock.patch.object(nlp, "generar_embeddings_pendientes", lambda: 0), \
            mock.patch.object(nlp, "generar_pares_candidatos", validacion._pares_simulados):
        return ejecutar_auditoria("2026", usuario=usuario)


def preparar_demo():
    call_command("seed_catalogo_gobernanza", stdout=io.StringIO())
    call_command("seed_datos_demo", stdout=io.StringIO())


class ReproducibilidadTest(TestCase):
    def setUp(self):
        preparar_demo()

    def test_la_ejecucion_registra_version_reglas_parametros_y_datos(self):
        e = auditar_demo()
        self.assertEqual(e.version_aplicacion, reproducibilidad.VERSION_APLICACION)
        self.assertEqual(e.version_reglas, reproducibilidad.VERSION_REGLAS)
        self.assertEqual(e.modelo_embeddings, "paraphrase-multilingual-mpnet-base-v2")
        self.assertEqual(e.indicadores_procesados, 9)
        self.assertEqual(len(e.huella_datos), 64)
        self.assertEqual(e.parametros_ejecucion["umbral_duplicidad"], 0.85)
        self.assertIn("django", e.parametros_ejecucion["entorno"])

    def test_dos_corridas_con_los_mismos_datos_son_equivalentes(self):
        a, b = auditar_demo(), auditar_demo()
        self.assertEqual(a.huella_datos, b.huella_datos)
        r = comparar(a, b)
        self.assertTrue(r["equivalentes"], r)
        self.assertEqual((r["hallazgos_a"], r["hallazgos_b"]), (5, 5))

    def test_un_cambio_de_umbral_o_de_datos_se_ve_en_el_registro(self):
        a = auditar_demo()
        with override_settings(NLP_ENGINE={**__import__("django.conf").conf.settings.NLP_ENGINE, "UMBRAL_DUPLICIDAD": 0.9}):
            b = auditar_demo()
        self.assertFalse(comparar(a, b)["configuracion_igual"])
        ind = Indicador.objects.filter(vigencia="2026").first()
        ind.objetivo += " (modificado)"
        ind.save()
        c = auditar_demo()
        self.assertNotEqual(a.huella_datos, c.huella_datos)

    def test_comando_comparar_ejecuciones(self):
        a, b = auditar_demo(), auditar_demo()
        salida = io.StringIO()
        call_command("comparar_ejecuciones", a.pk, b.pk, stdout=salida)
        self.assertIn("EQUIVALENTES", salida.getvalue())


class RendimientoTest(TestCase):
    def test_la_ejecucion_guarda_tiempos_por_etapa_y_memoria(self):
        preparar_demo()
        r = auditar_demo().rendimiento
        for clave in ("embeddings_s", "pares_candidatos_s", "reglas_pares_s", "reglas_indicador_s", "total_s"):
            self.assertIn(clave, r)
        self.assertGreaterEqual(r["total_s"], 0)
        self.assertTrue(r["memoria_pico_mb"] is None or r["memoria_pico_mb"] > 0)


class AgrupacionTest(TestCase):
    """Los pares con el mismo nombre se agrupan; ningun par se elimina."""

    def setUp(self):
        call_command("seed_catalogo_gobernanza", stdout=io.StringIO())
        self.d = [Dependencia.objects.create(nombre=f"Dependencia {i}") for i in range(3)]

        def ind(nombre, dep, producto=""):
            return Indicador.objects.create(nombre=nombre, dependencia=dep, vigencia="2026", producto_actividad_proyecto=producto)

        # transversal: tres dependencias; repeticion: una dependencia con dos productos; un par de nombres distintos
        self.t = [ind("Recursos de gestión y apoyo", d) for d in self.d]
        self.r = [ind("Entregar certificados", self.d[0], "A"), ind("entregar  certificados", self.d[0], "B")]
        self.x = [ind("Visitas guiadas realizadas", self.d[1]), ind("Visitas guiadas ejecutadas", self.d[2])]
        self.e = EjecucionAuditoria.objects.create(vigencia="2026")
        regla = ReglaAuditoria.objects.get(tipo_hallazgo="duplicidad")
        pares = [(self.t[0], self.t[1]), (self.t[0], self.t[2]), (self.t[1], self.t[2]), (self.r[0], self.r[1]), (self.x[0], self.x[1])]
        for a, b in pares:
            Hallazgo.objects.create(tipo="duplicidad", ejecucion=self.e, regla_aplicada=regla, indicador_principal=a,
                                    indicador_relacionado=b, atributos_comparados={"k": 1}, evidencia="x")

    def test_conteos_antes_y_despues(self):
        r = resumen_agrupacion(self.e)
        self.assertEqual(r["pares_individuales"], 5)
        self.assertEqual((r["pares_en_grupos"], r["pares_sueltos"]), (4, 1))
        self.assertEqual(len(r["grupos"]), 2)
        self.assertEqual(r["unidades_de_revision"], 3)
        self.assertEqual(Hallazgo.objects.filter(ejecucion=self.e).count(), 5, "no se elimina ningun hallazgo")

    def test_clases_transversal_y_repeticion_en_dependencia(self):
        clases = {g["nombre"]: g["clase"] for g in resumen_agrupacion(self.e)["grupos"]}
        self.assertEqual(clases["Recursos de gestión y apoyo"], "transversal")
        self.assertEqual(clases["Entregar certificados"], "repeticion_en_dependencia")

    def test_vista_de_agrupados_exige_permiso_y_muestra_los_grupos(self):
        self.assertEqual(self.client.get(reverse("dashboard:agrupados", args=[self.e.pk])).status_code, 302)
        self.client.force_login(usuario_con_rol("consulta1", "Consulta"))
        r = self.client.get(reverse("dashboard:agrupados", args=[self.e.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Recursos de gestión y apoyo")
        self.assertEqual(r.context["resumen"]["unidades_de_revision"], 3)


class TableroDeCalidadTest(TestCase):
    def setUp(self):
        preparar_demo()
        self.usuario = usuario_con_rol("auditor2")
        self.e = auditar_demo(self.usuario)

    def test_cifras_coinciden_con_el_conteo_directo(self):
        d = datos_calidad(self.e)
        self.assertEqual(d["total"], Hallazgo.objects.filter(ejecucion=self.e).count())
        for tipo, n in d["por_tipo"].items():
            self.assertEqual(n, Hallazgo.objects.filter(ejecucion=self.e, tipo=tipo).count())
        self.assertEqual(sum(d["por_estado"].values()), d["total"])
        self.assertEqual(sum(x["total"] for x in d["dependencias"]) <= d["total"], True)
        objetivo = Indicador.objects.filter(vigencia="2026", fuente="").count()
        fuente = next(c for c in d["completitud"] if c["campo"] == "fuente")
        self.assertEqual(fuente["total"] - fuente["diligenciados"], objetivo)

    def test_el_tablero_muestra_los_graficos_y_el_registro(self):
        self.client.force_login(self.usuario)
        r = self.client.get(reverse("dashboard:inicio"))
        self.assertContains(r, "g-completitud")
        self.assertContains(r, "Registro de reproducibilidad")
        self.assertEqual(r.context["calidad"]["total"], 5)

    def test_revisados_sube_al_confirmar(self):
        h = Hallazgo.objects.first()
        h.estado = "confirmado"
        h.save()
        d = datos_calidad(self.e)
        self.assertEqual(d["revisados"], 1)
        self.assertEqual(d["pct_revisados"], 20.0)

    def test_los_filtros_no_duplican_registros(self):
        self.client.force_login(self.usuario)
        for filtro in ({}, {"tipo": "duplicidad"}, {"estado": "pendiente"}, {"dependencia": Dependencia.objects.first().pk}):
            r = self.client.get(reverse("dashboard:hallazgos"), {"ejecucion": self.e.pk, **filtro})
            ids = [h.pk for h in r.context["hallazgos"]]
            self.assertEqual(len(ids), len(set(ids)), filtro)
            self.assertEqual(len(ids), r.context["total"])


class EvaluacionTest(TestCase):
    FILAS = [
        {"similitud": 0.95, "positiva": True}, {"similitud": 0.92, "positiva": True}, {"similitud": 0.88, "positiva": True},
        {"similitud": 0.87, "positiva": False}, {"similitud": 0.82, "positiva": True}, {"similitud": 0.81, "positiva": False},
        {"similitud": 0.60, "positiva": False}, {"similitud": 0.30, "positiva": False},
    ]

    def test_metricas_con_valores_conocidos(self):
        y = [f["positiva"] for f in self.FILAS]
        s = [f["similitud"] for f in self.FILAS]
        m = evaluacion.metricas(y, s, 0.85)  # predichos: 0.95, 0.92, 0.88, 0.87 -> VP 3, FP 1, FN 1
        self.assertEqual((m["vp"], m["fp"], m["fn"], m["vn"]), (3, 1, 1, 3))
        self.assertEqual((m["precision"], m["exhaustividad"], m["f1"]), (0.75, 0.75, 0.75))

    def test_tres_escenarios_y_pares_que_cambian(self):
        r = evaluacion.evaluar(self.FILAS)
        self.assertEqual([m["umbral"] for m in r["sin_ponderar"]], [0.80, 0.85, 0.90])
        # al subir el umbral baja el numero de alertas; la exhaustividad no sube
        exh = [m["exhaustividad"] for m in r["sin_ponderar"]]
        self.assertEqual(exh, sorted(exh, reverse=True))
        self.assertEqual(len(r["cambios"][0]["pares"]), 2)  # 0,82 y 0,81 dejan de ser alerta al pasar de 0,80 a 0,85
        self.assertEqual(len(r["cambios"][1]["pares"]), 2)  # 0,88 y 0,87 al pasar de 0,85 a 0,90

    def test_ponderacion_por_estrato(self):
        filas = [dict(f, peso=2.0) for f in self.FILAS]
        r = evaluacion.evaluar(filas, (0.85,))
        self.assertEqual(r["ponderadas"][0]["vp"], 6.0)
        self.assertEqual(r["ponderadas"][0]["precision"], r["sin_ponderar"][0]["precision"])

    def test_etiquetas_positivas(self):
        self.assertTrue(evaluacion.es_positiva("D") and evaluacion.es_positiva(" d ") and evaluacion.es_positiva("1"))
        self.assertFalse(evaluacion.es_positiva("P") or evaluacion.es_positiva("N") or evaluacion.es_positiva(""))


class SeguridadTest(TestCase):
    """Pruebas basicas de los controles descritos en el documento (sin certificacion ni despliegue)."""

    def setUp(self):
        call_command("seed_plantilla_demo", stdout=io.StringIO())
        self.plantilla = PlantillaMapeoColumnas.objects.get()

    def _form(self, nombre, contenido, vigencia="2026"):
        return CargaArchivoForm(
            {"plantilla": self.plantilla.pk, "vigencia": vigencia},
            {"archivo": SimpleUploadedFile(nombre, contenido)},
        )

    def test_carga_rechaza_formatos_no_permitidos(self):
        for nombre in ("programa.exe", "macro.xlsm", "datos.xls", "doc.pdf", "sin_extension"):
            self.assertFalse(self._form(nombre, b"contenido").is_valid(), nombre)

    def test_carga_valida_la_firma_del_contenido(self):
        self.assertFalse(self._form("falso.xlsx", b"esto no es un zip").is_valid())
        self.assertFalse(self._form("binario.csv", b"a,b\x00\x01").is_valid())
        self.assertTrue(self._form("ok.csv", "nombre,objetivo\nA,B\n".encode()).is_valid())
        self.assertTrue(self._form("ok.xlsx", b"PK\x03\x04resto").is_valid())

    def test_carga_rechaza_archivos_muy_grandes(self):
        with override_settings(CARGA_TAMANO_MAXIMO_MB=1):
            self.assertFalse(self._form("grande.csv", b"a" * (1024 * 1024 + 1)).is_valid())
            self.assertTrue(self._form("chico.csv", b"a,b\n").is_valid())

    def test_exportacion_neutraliza_formulas(self):
        preparar_demo()
        e = auditar_demo()
        h = Hallazgo.objects.filter(ejecucion=e).first()
        h.observacion_revision = '=HYPERLINK("http://ejemplo.invalido","x")'
        h.save()
        self.client.force_login(usuario_con_rol("auditor3"))
        from openpyxl import load_workbook
        hoja = load_workbook(io.BytesIO(self.client.get(reverse("reportes:exportar_excel")).content)).active
        valores = [str(c.value) for fila in hoja.iter_rows(min_row=2) for c in fila if c.value]
        self.assertFalse(any(v.startswith("=") for v in valores))
        self.assertTrue(any(v.startswith("'=HYPERLINK") for v in valores))

    def test_rol_consulta_no_carga_ni_ejecuta_ni_revisa(self):
        self.client.force_login(usuario_con_rol("consulta2", "Consulta"))
        self.assertEqual(self.client.get(reverse("ingesta:cargar")).status_code, 403)
        self.assertEqual(self.client.post(reverse("dashboard:inicio"), {"accion": "ejecutar_auditoria", "vigencia": "2026"}).status_code, 403)

    def test_post_sin_token_csrf_es_rechazado(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(usuario_con_rol("auditor4"))
        self.assertEqual(cliente.post(reverse("dashboard:inicio"), {"accion": "ejecutar_auditoria", "vigencia": "2026"}).status_code, 403)

    def test_sesion_expira_y_cookies_httponly(self):
        from django.conf import settings
        self.assertLessEqual(settings.SESSION_COOKIE_AGE, 12 * 60 * 60)
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(settings.X_FRAME_OPTIONS, "DENY")

    def test_errores_de_carga_no_muestran_rutas_internas(self):
        from apps.ingesta.models import CargaArchivo
        from apps.ingesta.services import procesar_archivo
        carga = CargaArchivo(vigencia="2026", plantilla=self.plantilla, nombre_archivo="roto.xlsx")
        carga.archivo.save("roto.xlsx", SimpleUploadedFile("roto.xlsx", b"PK\x03\x04no es un libro"), save=True)
        procesar_archivo(carga)
        carga.refresh_from_db()
        self.assertEqual(carga.estado, "fallido")
        self.assertNotIn("\\", " ".join(carga.detalle_errores))
        self.assertNotIn("/tmp", " ".join(carga.detalle_errores))
        self.assertFalse(carga.archivo, "el archivo original se elimina tras procesarse")

    def test_el_original_no_se_conserva_por_defecto(self):
        from django.conf import settings
        self.assertFalse(settings.CONSERVAR_ARCHIVO_ORIGINAL)


class ValorFaltanteTest(TestCase):
    """Regla R-1.2: diferencia con ambos valores presentes, valor faltante y ambos ausentes."""

    def test_estado_de_atributo(self):
        from apps.auditoria.reglas import estado_atributo
        self.assertEqual(estado_atributo("mensual", "anual"), "incompatible")
        self.assertEqual(estado_atributo("mensual", "mensual"), "igual")
        self.assertEqual(estado_atributo("Porcentaje", "porcentaje "), "igual")
        self.assertEqual(estado_atributo("mensual", "no_especificada"), "faltante")
        self.assertEqual(estado_atributo("", "Número"), "faltante")
        self.assertEqual(estado_atributo("no_especificada", ""), "ambos_ausentes")

    def test_los_tres_casos_de_la_matriz_cumplen(self):
        call_command("seed_catalogo_gobernanza", stdout=io.StringIO())
        filas = validacion._casos_valor_faltante()
        self.assertEqual([f["caso"] for f in filas], ["CP-20", "CP-21", "CP-22"])
        self.assertTrue(all(f["estado"] == "Cumple" for f in filas), filas)

    def test_valor_faltante_no_cuenta_como_divergencia_en_el_resumen(self):
        call_command("seed_catalogo_gobernanza", stdout=io.StringIO())
        d = Dependencia.objects.create(nombre="D")
        a = Indicador.objects.create(nombre="Visitas guiadas realizadas", objetivo="x", periodicidad="mensual", unidad_medida="Número", dependencia=d, vigencia="2030")
        b = Indicador.objects.create(nombre="Recorridos guiados ejecutados", objetivo="y", periodicidad="no_especificada", unidad_medida="Número", dependencia=d, vigencia="2030")
        from apps.nlp_engine.models import ParCandidato
        ParCandidato.objects.create(indicador_a=a, indicador_b=b, similitud_coseno=0.9, modelo="paraphrase-multilingual-mpnet-base-v2")
        with mock.patch.object(nlp, "generar_embeddings_pendientes", lambda: 0), \
                mock.patch.object(nlp, "generar_pares_candidatos", lambda v: 1):
            e = ejecutar_auditoria("2030")
        por_tipo = e.resumen_metricas["hallazgos_por_tipo"]
        self.assertEqual((por_tipo["divergencia_operativa"], por_tipo["valor_faltante"]), (0, 1))
        self.assertEqual(e.version_reglas, "R-1.2")

    def test_filtro_y_etiqueta_separan_el_valor_faltante(self):
        from apps.auditoria.consultas import filtrar_por_tipo
        call_command("seed_catalogo_gobernanza", stdout=io.StringIO())
        validacion._casos_valor_faltante()
        todos = Hallazgo.objects.all()
        self.assertEqual(filtrar_por_tipo(todos, "valor_faltante").count(), 1)
        self.assertEqual(filtrar_por_tipo(todos, "divergencia_operativa").count(), 1)
        self.assertEqual(filtrar_por_tipo(todos, "valor_faltante").get().tipo_etiqueta, "Valor faltante (regla de divergencia)")
