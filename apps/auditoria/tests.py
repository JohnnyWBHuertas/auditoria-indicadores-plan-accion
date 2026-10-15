import io
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from apps.auditoria import validacion
from apps.auditoria.models import Hallazgo
from apps.auditoria.reglas import ejecutar_auditoria, es_trazable
from apps.gobernanza.models import ParametroGobernanza
from apps.nlp_engine import embeddings as nlp


class MatrizDeValidacionTest(TestCase):
    """Cada caso de la matriz de validacion funcional (Anexo D) se convierte
    en una prueba automatizada sobre el conjunto de control."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.filas = validacion.ejecutar_matriz(usar_modelo=False)

    def test_hay_diecinueve_casos(self):
        self.assertEqual(len(self.filas), 19)

    def test_todos_los_casos_cumplen(self):
        incumplidos = [f"{f['caso']}: {f['obtenido']}" for f in self.filas if f["estado"] != "Cumple"]
        self.assertEqual(incumplidos, [])

    def test_la_matriz_no_deja_datos(self):
        self.assertEqual(Hallazgo.objects.count(), 0)


class CatalogoDeParametrosTest(TestCase):
    def setUp(self):
        call_command("seed_catalogo_gobernanza", stdout=io.StringIO())

    def test_once_parametros_en_cinco_tipos(self):
        self.assertEqual(ParametroGobernanza.objects.count(), 11)
        self.assertEqual(ParametroGobernanza.objects.values("categoria").distinct().count(), 5)

    def test_estado_de_operacionalizacion(self):
        conteo = {
            estado: ParametroGobernanza.objects.filter(operacionalizacion=estado).count()
            for estado in ("si", "parcial", "no")
        }
        self.assertEqual(conteo, {"si": 9, "parcial": 1, "no": 1})

    def test_sembrar_dos_veces_no_duplica(self):
        call_command("seed_catalogo_gobernanza", stdout=io.StringIO())
        self.assertEqual(ParametroGobernanza.objects.count(), 11)


class EjecucionDeAuditoriaTest(TestCase):
    def setUp(self):
        call_command("seed_catalogo_gobernanza", stdout=io.StringIO())
        call_command("seed_datos_demo", stdout=io.StringIO())

    def _auditar(self):
        with mock.patch.object(nlp, "generar_embeddings_pendientes", lambda: 0), \
                mock.patch.object(nlp, "generar_pares_candidatos", validacion._pares_simulados):
            return ejecutar_auditoria("2026")

    def test_cinco_hallazgos_trazables_y_pendientes(self):
        ejecucion = self._auditar()
        hallazgos = list(ejecucion.hallazgos.all())
        self.assertEqual(len(hallazgos), 5)
        self.assertTrue(all(es_trazable(h) for h in hallazgos))
        self.assertTrue(all(h.estado == "pendiente" for h in hallazgos))

    def test_dos_ejecuciones_dan_el_mismo_resultado(self):
        primera = self._auditar()
        segunda = self._auditar()
        self.assertEqual(
            sorted(primera.hallazgos.values_list("tipo", flat=True)),
            sorted(segunda.hallazgos.values_list("tipo", flat=True)),
        )

    def test_parametros_aplicados_se_registran(self):
        ejecucion = self._auditar()
        self.assertEqual(ejecucion.parametros_aplicados.count(), 9)

    def test_la_formula_no_dispara_divergencia(self):
        """Regresion del error corregido en la validacion funcional: dos
        indicadores equivalentes con formulas redactadas distinto no son una
        divergencia operativa."""
        ejecucion = self._auditar()
        duplicidad = ejecucion.hallazgos.get(tipo="duplicidad")
        self.assertNotEqual(duplicidad.indicador_principal.formula, duplicidad.indicador_relacionado.formula)
        self.assertEqual(ejecucion.hallazgos.filter(tipo="divergencia_operativa").count(), 1)
