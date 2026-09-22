"""Servicio de ingesta (CU1): carga un archivo y normaliza la hoja de vida.

Decision de arquitectura: el cargue se resuelve por PlantillaMapeoColumnas
(columna_origen -> campo_hoja_de_vida), no por posicion fija de columna,
porque la estructura del archivo exportado puede cambiar entre vigencias
y el prototipo se disena desacoplado de un dataset de referencia fijo.
"""

from __future__ import annotations

import pandas as pd

from apps.gobernanza.models import Dependencia

from .models import CargaArchivo, HistorialCambioIndicador, Indicador, LineaPAA

CAMPOS_HOJA_DE_VIDA = [
    "objetivo", "formula", "unidad_medida", "linea_base",
    "meta", "periodicidad", "fuente", "responsable",
]


def _leer_dataframe(archivo_field) -> pd.DataFrame:
    nombre = archivo_field.name.lower()
    if nombre.endswith(".csv"):
        return pd.read_csv(archivo_field, dtype=str).fillna("")
    return pd.read_excel(archivo_field, dtype=str).fillna("")


def procesar_archivo(carga: CargaArchivo) -> None:
    mapeo = carga.plantilla.mapeo_columnas  # {"columna_origen": "campo_hoja_de_vida"}

    try:
        df = _leer_dataframe(carga.archivo)
    except Exception as exc:
        carga.estado = "fallido"
        carga.detalle_errores = [f"No fue posible leer el archivo: {exc}"]
        carga.save(update_fields=["estado", "detalle_errores"])
        return

    columnas_mapeadas = {origen: campo for origen, campo in mapeo.items() if origen in df.columns}
    errores = []
    faltantes = [c for c in mapeo if c not in df.columns]
    if faltantes:
        errores.append(f"Columnas de la plantilla no encontradas en el archivo: {faltantes}")

    carga.filas_totales = len(df)
    filas_cargadas = 0
    filas_con_error = 0

    for indice_fila, fila in df.iterrows():
        try:
            datos = {campo: str(fila[origen]).strip() for origen, campo in columnas_mapeadas.items()}
            _normalizar_fila(carga, datos)
            filas_cargadas += 1
        except Exception as exc:
            filas_con_error += 1
            errores.append(f"Fila {indice_fila + 2}: {exc}")

    carga.filas_cargadas = filas_cargadas
    carga.filas_con_error = filas_con_error
    carga.detalle_errores = errores[:50]
    carga.estado = "completado" if not errores else "completado_con_errores"
    carga.save(
        update_fields=["filas_totales", "filas_cargadas", "filas_con_error", "detalle_errores", "estado"]
    )


def _normalizar_fila(carga: CargaArchivo, datos: dict) -> None:
    nombre_dependencia = datos.get("dependencia", "").strip() or "Sin dependencia"
    dependencia, _ = Dependencia.objects.get_or_create(nombre=nombre_dependencia)

    vigencia = datos.get("vigencia", "").strip() or carga.vigencia

    clave = dict(
        dependencia=dependencia,
        programa=datos.get("programa", "").strip(),
        bien_servicio=datos.get("bien_servicio", "").strip(),
        nombre=datos.get("nombre", "").strip(),
        producto_actividad_proyecto=datos.get("producto_actividad_proyecto", "").strip(),
        vigencia=vigencia,
    )
    if not clave["nombre"]:
        raise ValueError("La fila no tiene nombre de indicador (columna mapeada a 'nombre').")

    campos_hoja_de_vida = {campo: datos.get(campo, "").strip() for campo in CAMPOS_HOJA_DE_VIDA}

    indicador, creado = Indicador.objects.get_or_create(
        **clave, defaults={**campos_hoja_de_vida, "carga_origen": carga}
    )

    if not creado:
        _registrar_cambios(indicador, campos_hoja_de_vida, carga)

    codigo_paa = datos.get("codigo_paa", "").strip()
    if codigo_paa:
        LineaPAA.objects.get_or_create(
            indicador=indicador, codigo_paa=codigo_paa, defaults={"vigencia": vigencia}
        )


def _registrar_cambios(indicador: Indicador, campos_nuevos: dict, carga: CargaArchivo) -> None:
    """Historial append-only: solo se registra cuando el valor nuevo difiere
    y no está vacío (una carga posterior no debe borrar un dato ya bueno)."""
    cambios = []
    for campo, valor_nuevo in campos_nuevos.items():
        valor_anterior = getattr(indicador, campo)
        if valor_nuevo and valor_nuevo != valor_anterior:
            cambios.append(
                HistorialCambioIndicador(
                    indicador=indicador,
                    campo=campo,
                    valor_anterior=valor_anterior,
                    valor_nuevo=valor_nuevo,
                    origen="carga_archivo",
                )
            )
            setattr(indicador, campo, valor_nuevo)

    if cambios:
        HistorialCambioIndicador.objects.bulk_create(cambios)
        indicador.carga_origen = carga
        indicador.save()
