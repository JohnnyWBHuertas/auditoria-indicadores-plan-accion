import os

from django import forms
from django.conf import settings

from .models import CargaArchivo, PlantillaMapeoColumnas

EXTENSIONES_PERMITIDAS = (".xlsx", ".csv")
FIRMA_XLSX = b"PK\x03\x04"  # un .xlsx es un contenedor zip


class CargaArchivoForm(forms.ModelForm):
    class Meta:
        model = CargaArchivo
        fields = ["archivo", "plantilla", "vigencia"]
        widgets = {
            "archivo": forms.ClearableFileInput(attrs={"class": "form-control", "accept": ",".join(EXTENSIONES_PERMITIDAS)}),
            "plantilla": forms.Select(attrs={"class": "form-select"}),
            "vigencia": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej. 2026"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["plantilla"].queryset = PlantillaMapeoColumnas.objects.filter(activa=True)

    def clean_archivo(self):
        """Control de la carga: solo .xlsx o .csv, con tamaño máximo y firma coherente con el formato."""
        archivo = self.cleaned_data["archivo"]
        extension = os.path.splitext(archivo.name)[1].lower()
        if extension not in EXTENSIONES_PERMITIDAS:
            raise forms.ValidationError("Formato no permitido. Cargue un archivo .xlsx o .csv.")
        maximo = settings.CARGA_TAMANO_MAXIMO_MB * 1024 * 1024
        if archivo.size > maximo:
            raise forms.ValidationError(f"El archivo supera el máximo de {settings.CARGA_TAMANO_MAXIMO_MB} MB.")
        inicio = archivo.read(4096)
        archivo.seek(0)
        if extension == ".xlsx" and not inicio.startswith(FIRMA_XLSX):
            raise forms.ValidationError("El contenido no corresponde a un libro de Excel (.xlsx).")
        if extension == ".csv" and b"\x00" in inicio:
            raise forms.ValidationError("El contenido no corresponde a un archivo de texto CSV.")
        return archivo
