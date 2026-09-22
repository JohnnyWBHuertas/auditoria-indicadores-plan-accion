from django import forms

from .models import CargaArchivo, PlantillaMapeoColumnas


class CargaArchivoForm(forms.ModelForm):
    class Meta:
        model = CargaArchivo
        fields = ["archivo", "plantilla", "vigencia"]
        widgets = {
            "archivo": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "plantilla": forms.Select(attrs={"class": "form-select"}),
            "vigencia": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej. 2026"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["plantilla"].queryset = PlantillaMapeoColumnas.objects.filter(activa=True)
