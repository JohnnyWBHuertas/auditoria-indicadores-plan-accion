import csv

import numpy as np
from django.core.management.base import BaseCommand, CommandError
from openpyxl import Workbook

from apps.auditoria.evaluacion import UMBRALES_POR_DEFECTO, es_positiva, evaluar
from apps.nlp_engine.models import EmbeddingIndicador


class Command(BaseCommand):
    help = (
        "Compara escenarios de umbral de similitud (por defecto 0,80, 0,85 y 0,90) sobre una muestra etiquetada. "
        "Reutiliza los embeddings guardados y solo varía el parámetro de decisión; calcula precisión, exhaustividad y F1. "
        "Los umbrales son escenarios de experimentación y no cambian el umbral del sistema."
    )

    def add_arguments(self, parser):
        parser.add_argument("--muestra", required=True, help="CSV generado por generar_muestra_evaluacion con la columna «etiqueta» diligenciada.")
        parser.add_argument("--umbrales", nargs="+", type=float, default=list(UMBRALES_POR_DEFECTO))
        parser.add_argument("--salida", help="Ruta del .xlsx donde guardar tablas, cambios y errores.")

    def handle(self, *args, **options):
        with open(options["muestra"], newline="", encoding="utf-8-sig") as f:
            filas = [r for r in csv.DictReader(f) if (r.get("etiqueta") or "").strip()]
        if not filas:
            raise CommandError("La muestra no tiene etiquetas diligenciadas.")
        ids = {int(r["id_a"]) for r in filas} | {int(r["id_b"]) for r in filas}
        vect = {i: np.array(v, dtype=np.float32) for i, v in EmbeddingIndicador.objects.filter(indicador_id__in=ids).values_list("indicador_id", "vector")}
        for r in filas:
            a, b = vect[int(r["id_a"])], vect[int(r["id_b"])]
            r["similitud"] = float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))
            r["positiva"] = es_positiva(r["etiqueta"])
            r["peso"] = float(r.get("peso") or 1.0)
        res = evaluar(filas, options["umbrales"])

        self.stdout.write(f"Muestra: {res['n']} pares, {res['positivas']} etiquetados como duplicado o redundante.")
        for titulo, bloque in (("Sin ponderar (la muestra tal cual)", res["sin_ponderar"]), ("Ponderadas por estrato", res["ponderadas"])):
            if not bloque:
                continue
            self.stdout.write(titulo)
            for m in bloque:
                self.stdout.write(f"  umbral {m['umbral']:.2f}: precisión {m['precision']:.3f}, exhaustividad {m['exhaustividad']:.3f}, F1 {m['f1']:.3f} (VP {m['vp']}, FP {m['fp']}, FN {m['fn']}, VN {m['vn']})")
        for c in res["cambios"]:
            self.stdout.write(f"Pares que cambian de {c['de']:.2f} a {c['a']:.2f}: {len(c['pares'])}")

        if options["salida"]:
            self._exportar(options["salida"], filas, res)
            self.stdout.write(f"Resultados guardados en {options['salida']}")

    def _exportar(self, ruta, filas, res):
        wb = Workbook()
        ws = wb.active
        ws.title = "Métricas"
        ws.append(["Tipo", "Umbral", "Precisión", "Exhaustividad", "F1", "VP", "FP", "FN", "VN"])
        for tipo, bloque in (("Sin ponderar", res["sin_ponderar"]), ("Ponderada", res["ponderadas"])):
            for m in bloque:
                ws.append([tipo, m["umbral"], m["precision"], m["exhaustividad"], m["f1"], m["vp"], m["fp"], m["fn"], m["vn"]])
        ws = wb.create_sheet("Cambios entre umbrales")
        ws.append(["De", "A", "id", "similitud", "etiqueta", "nombre A", "nombre B"])
        for c in res["cambios"]:
            for i in c["pares"]:
                r = filas[i]
                ws.append([c["de"], c["a"], r["id"], round(r["similitud"], 4), r["etiqueta"], r["nombre_a"], r["nombre_b"]])
        ws = wb.create_sheet("Errores")
        ws.append(["Tipo de error", "Umbral", "id", "similitud", "etiqueta", "nombre A", "nombre B", "observación"])
        for u, idx in res["falsos_positivos"].items():
            for i in idx:
                r = filas[i]
                ws.append(["Falso positivo", u, r["id"], round(r["similitud"], 4), r["etiqueta"], r["nombre_a"], r["nombre_b"], r.get("observacion", "")])
        for u, idx in res["falsos_negativos"].items():
            for i in idx:
                r = filas[i]
                ws.append(["Falso negativo", u, r["id"], round(r["similitud"], 4), r["etiqueta"], r["nombre_a"], r["nombre_b"], r.get("observacion", "")])
        wb.save(ruta)
