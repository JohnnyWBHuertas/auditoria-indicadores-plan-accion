import importlib
import sys

from django.conf import settings
from django.core.management.base import BaseCommand

COMPONENTES = [
    ("numpy", "Cálculo numérico"),
    ("openpyxl", "Lectura de Excel y exportación"),
    ("torch", "Cómputo del modelo de embeddings"),
    ("sklearn", "Dependencia de sentence-transformers"),
    ("sentence_transformers", "Modelo de embeddings"),
]


class Command(BaseCommand):
    help = "Comprueba que cada componente del motor de embeddings se pueda cargar en este equipo."

    def handle(self, *args, **options):
        self.stdout.write(f"Python {sys.version.split()[0]} · modelo {settings.NLP_ENGINE['EMBEDDING_MODEL']}\n")
        fallos = 0
        for modulo, descripcion in COMPONENTES:
            try:
                importado = importlib.import_module(modulo)
                version = getattr(importado, "__version__", "")
                self.stdout.write(self.style.SUCCESS(f"  OK       {modulo} {version}") + f"  ({descripcion})")
            except (ImportError, OSError) as exc:
                fallos += 1
                self.stdout.write(self.style.ERROR(f"  BLOQUEADO {modulo}") + f"  ({descripcion}): {exc}")
        if fallos:
            self.stdout.write(self.style.ERROR(
                "\nHay componentes que no cargan. Si el mensaje habla de una directiva de Control de aplicaciones, "
                "Windows (Smart App Control) está bloqueando una biblioteca nativa: ejecute el prototipo en otro "
                "entorno (WSL, otro equipo) o ajuste esa política."
            ))
        else:
            self.stdout.write(self.style.SUCCESS("\nEl motor de embeddings puede ejecutarse en este equipo."))
