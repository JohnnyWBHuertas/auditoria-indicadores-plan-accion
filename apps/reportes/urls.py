from django.urls import path

from . import views

app_name = "reportes"

urlpatterns = [
    path("hallazgos/excel/", views.exportar_excel, name="exportar_excel"),
]
