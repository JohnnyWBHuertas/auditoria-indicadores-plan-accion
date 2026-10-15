import io
import tempfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.auditoria import validacion
from apps.gobernanza.models import EjecucionAuditoria, ParametroGobernanza
from apps.ingesta.models import Indicador, PlantillaMapeoColumnas
from apps.nlp_engine import embeddings as nlp


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PrepararDemoTest(TestCase):
    """«preparar_demo» deja el prototipo listo para que un revisor lo pruebe sin pasos manuales."""

    def _preparar(self, **opciones):
        salida = io.StringIO()
        call_command("preparar_demo", stdout=salida, **opciones)
        return salida.getvalue()

    def test_deja_catalogo_usuarios_plantilla_e_indicadores(self):
        texto = self._preparar(password="clave-de-prueba")
        self.assertEqual(ParametroGobernanza.objects.count(), 11)
        Usuario = get_user_model()
        self.assertTrue(Usuario.objects.get(username="auditor").check_password("clave-de-prueba"))
        self.assertTrue(Usuario.objects.get(username="administrador").is_staff)
        self.assertTrue(PlantillaMapeoColumnas.objects.filter(nombre="Conjunto de control 2026").exists())
        self.assertEqual(Indicador.objects.filter(vigencia="2026").count(), 9)
        self.assertIn("runserver", texto)

    def test_no_audita_si_no_se_pide(self):
        self._preparar()
        self.assertEqual(EjecucionAuditoria.objects.count(), 0)

    def test_se_puede_repetir_sin_duplicar(self):
        self._preparar()
        self._preparar()
        self.assertEqual(Indicador.objects.filter(vigencia="2026").count(), 9)
        self.assertEqual(ParametroGobernanza.objects.count(), 11)
        self.assertEqual(get_user_model().objects.filter(username="auditor").count(), 1)

    def test_con_auditar_produce_los_cinco_hallazgos(self):
        with mock.patch.object(nlp, "generar_embeddings_pendientes", lambda: 0), \
                mock.patch.object(nlp, "generar_pares_candidatos", validacion._pares_simulados):
            self._preparar(auditar=True)
        ejecucion = EjecucionAuditoria.objects.get()
        self.assertEqual(ejecucion.hallazgos.count(), 5)
