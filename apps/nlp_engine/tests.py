from django.test import TestCase

from apps.gobernanza.models import Dependencia
from apps.ingesta.models import Indicador
from apps.nlp_engine import embeddings as nlp
from apps.nlp_engine.models import EmbeddingIndicador, ParCandidato


class ParesCandidatosTest(TestCase):
    """Comparacion por bloques con vectores construidos a mano (no carga el modelo)."""

    def setUp(self):
        dependencia = Dependencia.objects.create(nombre="Dependencia de prueba")
        self.indicadores = []
        vectores = [[1.0, 0.0], [0.99, 0.14], [0.0, 1.0], [0.1, 0.995]]
        for i, vector in enumerate(vectores):
            indicador = Indicador.objects.create(nombre=f"Indicador {i}", dependencia=dependencia, vigencia="2026")
            EmbeddingIndicador.objects.create(
                indicador=indicador, modelo="paraphrase-multilingual-mpnet-base-v2", texto_fuente="x", vector=vector
            )
            self.indicadores.append(indicador)

    def test_solo_pares_sobre_el_umbral(self):
        nlp.generar_pares_candidatos("2026", umbral=0.85)
        pares = {(p.indicador_a_id, p.indicador_b_id) for p in ParCandidato.objects.all()}
        i = [x.pk for x in self.indicadores]
        self.assertEqual(pares, {(i[0], i[1]), (i[2], i[3])})

    def test_bloques_pequenos_dan_el_mismo_resultado(self):
        nlp.generar_pares_candidatos("2026", umbral=0.85, bloque=1)
        self.assertEqual(ParCandidato.objects.count(), 2)

    def test_repetir_no_duplica_pares(self):
        nlp.generar_pares_candidatos("2026", umbral=0.85)
        nlp.generar_pares_candidatos("2026", umbral=0.85)
        self.assertEqual(ParCandidato.objects.count(), 2)

    def test_similitud_coseno(self):
        self.assertAlmostEqual(nlp.similitud_coseno([1, 0], [1, 0]), 1.0)
        self.assertAlmostEqual(nlp.similitud_coseno([1, 0], [0, 1]), 0.0)
