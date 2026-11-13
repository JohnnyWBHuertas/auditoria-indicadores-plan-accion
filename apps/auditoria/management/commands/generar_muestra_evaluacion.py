import csv

from django.core.management.base import BaseCommand, CommandError

from apps.auditoria.muestreo import detalle_indicadores, generar_muestra


class Command(BaseCommand):
    help = (
        "Genera la muestra estratificada de pares de indicadores que se etiqueta a mano (columna «etiqueta»: "
        "D = duplicado o redundante, P = patrón repetido legítimo, N = no relacionado). "
        "Escribe un CSV con el texto de cada par. No lo versione: contiene datos institucionales."
    )

    def add_arguments(self, parser):
        parser.add_argument("--vigencias", nargs="+", default=["2025", "2026"])
        parser.add_argument("--semilla", type=int, default=42)
        parser.add_argument("--salida", required=True, help="Ruta del CSV de salida.")

    def handle(self, *args, **options):
        muestra, poblacion = generar_muestra(options["vigencias"], semilla=options["semilla"])
        if not muestra:
            raise CommandError("No hay embeddings para las vigencias indicadas. Ejecute antes la auditoría.")
        det = detalle_indicadores(muestra)
        campos = ["id", "estrato", "peso", "vigencia", "similitud", "id_a", "dependencia_a", "nombre_a", "objetivo_a",
                  "producto_a", "id_b", "dependencia_b", "nombre_b", "objetivo_b", "producto_b", "etiqueta", "observacion"]
        with open(options["salida"], "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=campos)
            w.writeheader()
            for n, fila in enumerate(muestra, start=1):
                a, b = det[fila["id_a"]], det[fila["id_b"]]
                w.writerow({
                    "id": n, **fila,
                    "dependencia_a": a.dependencia.nombre, "nombre_a": a.nombre, "objetivo_a": a.objetivo, "producto_a": a.producto_actividad_proyecto,
                    "dependencia_b": b.dependencia.nombre, "nombre_b": b.nombre, "objetivo_b": b.objetivo, "producto_b": b.producto_actividad_proyecto,
                    "etiqueta": "", "observacion": "",
                })
        self.stdout.write(f"{len(muestra)} pares escritos en {options['salida']} (semilla {options['semilla']}).")
        for estrato, n in poblacion.items():
            self.stdout.write(f"  {estrato}: {n} pares en la población")
