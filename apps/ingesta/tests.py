import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from openpyxl import Workbook

import tempfile

from apps.ingesta.models import CargaArchivo, HistorialCambioIndicador, Indicador, PlantillaMapeoColumnas
from apps.ingesta.services import procesar_archivo

MAPEO = {"Indicador": "nombre", "Dependencia": "dependencia", "Meta": "meta", "Periodicidad": "periodicidad", "Fórmula": "formula"}


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class IngestaTest(TestCase):
    def setUp(self):
        self.plantilla = PlantillaMapeoColumnas.objects.create(nombre="p", vigencia="2026", mapeo_columnas=MAPEO)

    def _cargar(self, nombre, contenido):
        carga = CargaArchivo.objects.create(
            archivo=SimpleUploadedFile(nombre, contenido), plantilla=self.plantilla, vigencia="2026"
        )
        procesar_archivo(carga)
        carga.refresh_from_db()
        return carga

    def _xlsx(self, filas):
        libro = Workbook()
        hoja = libro.active
        hoja.append(list(MAPEO))
        for fila in filas:
            hoja.append(fila)
        salida = io.BytesIO()
        libro.save(salida)
        return salida.getvalue()

    def test_csv_con_punto_y_coma_y_bom(self):
        texto = "Indicador;Dependencia;Meta;Periodicidad;Fórmula\nBibliotecas asistidas;Grupo A;10;Anual;N\n"
        carga = self._cargar("a.csv", texto.encode("utf-8-sig"))
        self.assertEqual((carga.estado, carga.filas_cargadas), ("completado", 1))
        self.assertEqual(Indicador.objects.get().periodicidad, "anual")

    def test_excel(self):
        carga = self._cargar("a.xlsx", self._xlsx([["Indicador uno", "Grupo A", 5, "Mensual", "x"], ["Indicador dos", "Grupo B", 7, "Anual", "y"]]))
        self.assertEqual((carga.estado, carga.filas_cargadas), ("completado", 2))
        self.assertEqual(Indicador.objects.count(), 2)

    def test_fila_sin_indicador_se_omite_sin_ser_error(self):
        carga = self._cargar("a.xlsx", self._xlsx([["", "Grupo A", 5, "Anual", "x"], ["Indicador bueno", "Grupo A", 5, "Anual", "x"]]))
        self.assertEqual((carga.filas_cargadas, carga.filas_sin_indicador, carga.filas_con_error), (1, 1, 0))
        self.assertEqual(carga.estado, "completado")

    def test_vigencia_con_texto_se_normaliza_al_anio(self):
        plantilla = PlantillaMapeoColumnas.objects.create(
            nombre="v", vigencia="2025", mapeo_columnas={"Indicador": "nombre", "Dependencia": "dependencia", "VIGENCIA": "vigencia"}
        )
        carga = CargaArchivo.objects.create(
            archivo=SimpleUploadedFile("v.csv", "Indicador,Dependencia,VIGENCIA\nUno,Grupo A,Año 2025\n".encode()),
            plantilla=plantilla, vigencia="2025",
        )
        procesar_archivo(carga)
        self.assertEqual(Indicador.objects.get().vigencia, "2025")

    def test_filas_de_varias_lineas_paa_se_consolidan_en_un_indicador(self):
        plantilla = PlantillaMapeoColumnas.objects.create(
            nombre="paa", vigencia="2025",
            mapeo_columnas={"Indicador": "nombre", "Dependencia": "dependencia", "Código PAA": "codigo_paa"},
        )
        texto = "Indicador,Dependencia,Código PAA\nUno,Grupo A,1-0-1\nUno,Grupo A,1-0-2\nUno,Grupo A,1-0-3\n"
        carga = CargaArchivo.objects.create(archivo=SimpleUploadedFile("p.csv", texto.encode()), plantilla=plantilla, vigencia="2025")
        procesar_archivo(carga)
        indicador = Indicador.objects.get()
        self.assertEqual(indicador.lineas_paa.count(), 3)

    def test_columna_de_la_plantilla_ausente_se_informa(self):
        carga = self._cargar("a.csv", b"Indicador,Dependencia\nUno,Grupo A\n")
        self.assertIn("Columnas de la plantilla no encontradas", carga.detalle_errores[0])

    def test_historial_solo_registra_cambios_reales(self):
        base = "Indicador,Dependencia,Meta,Periodicidad,Fórmula\nUno,Grupo A,10,Anual,N\n"
        self._cargar("a.csv", base.encode("utf-8"))
        self._cargar("b.csv", base.encode("utf-8"))
        self.assertEqual(HistorialCambioIndicador.objects.count(), 0)
        self._cargar("c.csv", base.replace(",10,", ",12,").encode("utf-8"))
        cambio = HistorialCambioIndicador.objects.get()
        self.assertEqual((cambio.campo, cambio.valor_anterior, cambio.valor_nuevo), ("meta", "10", "12"))

    def test_un_valor_vacio_no_borra_un_dato_existente(self):
        self._cargar("a.csv", "Indicador,Dependencia,Meta,Periodicidad,Fórmula\nUno,Grupo A,10,Anual,N\n".encode())
        self._cargar("b.csv", "Indicador,Dependencia,Meta,Periodicidad,Fórmula\nUno,Grupo A,10,,\n".encode())
        self.assertEqual(Indicador.objects.get().formula, "N")

    def test_conjunto_de_control_de_ejemplo(self):
        call_command("seed_plantilla_demo", stdout=io.StringIO())
        from apps.auditoria.validacion import cargar_conjunto_control
        carga = cargar_conjunto_control()
        self.assertEqual((carga.estado, carga.filas_cargadas), ("completado", 9))


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PrivacidadDelArchivoTest(TestCase):
    """El archivo original (puede traer datos personales) no se conserva por defecto."""

    def setUp(self):
        self.plantilla = PlantillaMapeoColumnas.objects.create(nombre="p", vigencia="2026", mapeo_columnas={"Indicador": "nombre", "Dependencia": "dependencia"})

    def _cargar(self):
        carga = CargaArchivo.objects.create(
            archivo=SimpleUploadedFile("reporte.csv", "Indicador,Dependencia,Documento\nUno,Grupo A,1234567890\n".encode()),
            plantilla=self.plantilla, vigencia="2026", nombre_archivo="reporte.csv",
        )
        nombre_en_disco = carga.archivo.name
        procesar_archivo(carga)
        carga.refresh_from_db()
        return carga, nombre_en_disco

    def test_por_defecto_el_original_se_elimina_y_el_historial_se_conserva(self):
        carga, nombre = self._cargar()
        self.assertFalse(carga.archivo.storage.exists(nombre))
        self.assertEqual((carga.archivo.name, carga.nombre_archivo, carga.estado), ("", "reporte.csv", "completado"))
        self.assertEqual(Indicador.objects.count(), 1)  # los datos procesados siguen ahi

    @override_settings(CONSERVAR_ARCHIVO_ORIGINAL=True)
    def test_se_puede_conservar_si_se_activa(self):
        carga, nombre = self._cargar()
        self.assertTrue(carga.archivo.storage.exists(nombre))

    def test_purgar_elimina_los_originales_ya_almacenados(self):
        with override_settings(CONSERVAR_ARCHIVO_ORIGINAL=True):
            carga, nombre = self._cargar()
        self.assertTrue(carga.archivo.storage.exists(nombre))
        salida = io.StringIO()
        call_command("purgar_archivos_originales", stdout=salida)
        carga.refresh_from_db()
        self.assertFalse(carga.archivo.storage.exists(nombre))
        self.assertEqual(carga.nombre_archivo, "reporte.csv")
        self.assertIn("1 archivo", salida.getvalue())
