import json
import os
import platform
import sys
import time

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.auditoria import reproducibilidad as repro
from apps.auditoria.reglas import ejecutar_auditoria
from apps.ingesta.models import CargaArchivo, Indicador, PlantillaMapeoColumnas
from apps.ingesta.services import procesar_archivo
from apps.nlp_engine import embeddings as nlp
from apps.nlp_engine.models import EmbeddingIndicador, ParCandidato


class _Revertir(Exception):
    pass


def ficha_equipo() -> dict:
    ficha = {"sistema": platform.system() + " " + platform.release(), "python": platform.python_version(), "nucleos_logicos": os.cpu_count()}
    try:
        if sys.platform == "win32":
            import winreg

            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
                ficha["procesador"] = winreg.QueryValueEx(k, "ProcessorNameString")[0].strip()
            import ctypes

            class Mem(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong), ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]

            m = Mem()
            m.dwLength = ctypes.sizeof(m)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            ficha["memoria_ram_gb"] = round(m.ullTotalPhys / 1024**3, 1)
        else:
            ficha["procesador"] = platform.processor()
            with open("/proc/meminfo") as f:
                ficha["memoria_ram_gb"] = round(int(f.readline().split()[1]) / 1024**2, 1)
    except Exception:
        pass
    try:
        import torch

        ficha["torch"] = torch.__version__
        ficha["gpu"] = "sí" if torch.cuda.is_available() else "no (CPU)"
    except Exception:
        pass
    return ficha


class Command(BaseCommand):
    help = (
        "Mide el rendimiento de la auditoría: tiempo por etapa y memoria máxima. Para cada vigencia borra sus "
        "embeddings dentro de una transacción, ejecuta la auditoría completa (incluida la generación de embeddings) "
        "y revierte todo, de modo que los datos no cambian. Con --factores repite la vigencia de mayor tamaño de "
        "forma sintética (x2, x4...) para observar el crecimiento. Úselo sobre una copia de la base si prefiere no arriesgar datos."
    )

    def add_arguments(self, parser):
        parser.add_argument("--vigencias", nargs="+", default=["2025", "2026"])
        parser.add_argument("--factores", nargs="*", type=int, default=[])
        parser.add_argument("--reporte", nargs="*", default=[], help="Pares VIGENCIA=ruta.xlsx para medir también la lectura y normalización.")
        parser.add_argument("--plantilla", help="Nombre de la plantilla de mapeo para --reporte.")
        parser.add_argument("--salida", help="Ruta del JSON con las mediciones.")

    def handle(self, *args, **options):
        resultados = {"equipo": ficha_equipo(), "mediciones": []}
        t = time.perf_counter()
        try:
            nlp.get_embedding_model()
        except nlp.ModeloNoDisponible as exc:
            raise CommandError(str(exc))
        resultados["carga_modelo_s"] = round(time.perf_counter() - t, 2)
        resultados["memoria_tras_cargar_modelo_mb"] = repro.memoria_pico_mb()

        reportes = dict(par.split("=", 1) for par in options["reporte"])
        for vig in options["vigencias"]:
            fila = {"vigencia": vig, "tipo": "real"}
            if vig in reportes:
                fila["lectura_normalizacion_s"], fila["filas_cargadas"] = self._medir_carga(vig, reportes[vig], options["plantilla"])
            fila.update(self._medir_auditoria(vig))
            resultados["mediciones"].append(fila)

        if options["factores"]:
            base = max(options["vigencias"], key=lambda v: Indicador.objects.filter(vigencia=v).count())
            for k in options["factores"]:
                fila = {"vigencia": f"{base} x{k} (sintético)", "tipo": "sintético"}
                fila.update(self._medir_auditoria(base, copias=k))
                resultados["mediciones"].append(fila)

        self.stdout.write(json.dumps(resultados, ensure_ascii=False, indent=2))
        if options["salida"]:
            with open(options["salida"], "w", encoding="utf-8") as f:
                json.dump(resultados, f, ensure_ascii=False, indent=2)

    def _medir_auditoria(self, vigencia, copias=1):
        try:
            with transaction.atomic():
                destino = vigencia
                if copias > 1:
                    destino = f"S{copias}-{vigencia}"
                    originales = list(Indicador.objects.filter(vigencia=vigencia))
                    nuevos = []
                    for k in range(copias):
                        for i in originales:
                            nuevos.append(Indicador(
                                nombre=f"{i.nombre} [copia {k + 1}]" if k else i.nombre, objetivo=i.objetivo, formula=i.formula,
                                unidad_medida=i.unidad_medida, linea_base=i.linea_base, meta=i.meta, periodicidad=i.periodicidad,
                                fuente=i.fuente, responsable=i.responsable, dependencia_id=i.dependencia_id, programa=i.programa,
                                bien_servicio=i.bien_servicio, producto_actividad_proyecto=i.producto_actividad_proyecto, vigencia=destino,
                            ))
                    Indicador.objects.bulk_create(nuevos)
                else:
                    ParCandidato.objects.filter(indicador_a__vigencia=vigencia).delete()
                    EmbeddingIndicador.objects.filter(indicador__vigencia=vigencia).delete()
                ejecucion = ejecutar_auditoria(destino)
                datos = {
                    "indicadores": ejecucion.indicadores_procesados,
                    "pares_comparados": ejecucion.indicadores_procesados * (ejecucion.indicadores_procesados - 1) // 2,
                    "pares_candidatos": ejecucion.pares_candidatos,
                    "señalamientos": ejecucion.hallazgos.count(),
                    "rendimiento": ejecucion.rendimiento,
                }
                raise _Revertir
        except _Revertir:
            return datos

    def _medir_carga(self, vigencia, ruta, nombre_plantilla):
        plantilla = PlantillaMapeoColumnas.objects.filter(nombre__icontains=nombre_plantilla or "").first()
        if plantilla is None:
            raise CommandError("Indique --plantilla con el nombre de una plantilla de mapeo existente.")
        with open(ruta, "rb") as f:
            contenido = f.read()
        try:
            with transaction.atomic():
                Indicador.objects.filter(vigencia=vigencia).delete()
                carga = CargaArchivo(vigencia=vigencia, plantilla=plantilla, nombre_archivo=os.path.basename(ruta))
                carga.archivo.save("medicion_" + os.path.basename(ruta), ContentFile(contenido), save=True)
                t = time.perf_counter()
                procesar_archivo(carga)
                dt = round(time.perf_counter() - t, 3)
                carga.refresh_from_db()
                datos = (dt, carga.filas_cargadas)
                raise _Revertir
        except _Revertir:
            return datos
