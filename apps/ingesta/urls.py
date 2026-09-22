from django.urls import path

from . import views

app_name = "ingesta"

urlpatterns = [
    path("cargar/", views.cargar_archivo, name="cargar"),
    path("historial/", views.historial, name="historial"),
]
