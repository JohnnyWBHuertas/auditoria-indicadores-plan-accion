from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("hallazgos/", views.hallazgos, name="hallazgos"),
    path("hallazgos/<int:pk>/", views.hallazgo_detalle, name="hallazgo_detalle"),
]
