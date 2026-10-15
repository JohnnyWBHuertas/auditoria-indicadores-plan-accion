from django.urls import path

from . import views, views_comparar, views_detalle

app_name = "dashboard"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("hallazgos/", views.hallazgos, name="hallazgos"),
    path("comparar/", views_comparar.comparar, name="comparar"),
    path("hallazgos/<int:pk>/", views.hallazgo_detalle, name="hallazgo_detalle"),
    # Detalle de las variables observables de una ejecucion
    path("ejecuciones/<int:pk>/parametros/", views_detalle.parametros, name="detalle_parametros"),
    path("ejecuciones/<int:pk>/correspondencia/", views_detalle.correspondencia, name="detalle_correspondencia"),
    path("ejecuciones/<int:pk>/trazabilidad/", views_detalle.trazabilidad, name="detalle_trazabilidad"),
    path("ejecuciones/<int:pk>/completitud/", views_detalle.completitud, name="detalle_completitud"),
]
