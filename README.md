# Prototipo de auditoría de indicadores del Plan de Acción

Producto tecnológico de la monografía *Diseño de un prototipo web basado en inteligencia artificial para la auditoría de indicadores bajo parámetros de gobernanza de datos: caso del Plan de Acción del Ministerio de las Culturas, las Artes y los Saberes (2025-2026)* (Especialización en Desarrollo de Software, UNIMINUTO).

El sistema carga el reporte de indicadores de una vigencia, compara semánticamente sus formulaciones y señala, con su regla, atributos comparados y evidencia, cinco tipos de hallazgo: **duplicidad, clonación, divergencia operativa, incompletitud de atributos y problema metodológico**. Cada hallazgo nace *pendiente*: solo el auditor lo confirma o lo descarta.

- **Una sola IA:** el modelo de embeddings `paraphrase-multilingual-mpnet-base-v2` (sentence-transformers), ejecutado localmente. Propone pares candidatos; la clasificación por tipo la hacen reglas deterministas.
- **Ejecución 100 % local:** sin nube ni APIs externas. Solo la primera descarga del modelo requiere red.
- **Datos:** el conjunto de control (`datos_ejemplo/conjunto_control_2026.csv`) es sintético; no contiene datos reales del Ministerio.

## Inicio rápido: demostración con el conjunto de control

Permite a un revisor probar el prototipo sin reportes reales: el conjunto de control (`datos_ejemplo/conjunto_control_2026.csv`) es sintético, de nueve indicadores, y produce exactamente un hallazgo de cada tipo.

```bash
git clone https://github.com/JohnnyWBHuertas/auditoria-indicadores-plan-accion.git
cd auditoria-indicadores-plan-accion
python -m venv .venv
.venv\Scripts\activate            # Windows (en Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
```

Con SQLite no necesita instalar PostgreSQL. Defina la variable de entorno y prepare todo con un solo comando:

```bash
set USE_SQLITE_LOCAL=True          # Windows (en Linux/macOS: export USE_SQLITE_LOCAL=True)
python manage.py preparar_demo --auditar
python manage.py runserver
```

`preparar_demo` aplica las migraciones, siembra el catálogo (11 parámetros y 5 reglas), crea los usuarios, crea la plantilla de mapeo, carga los nueve indicadores y ejecuta la auditoría. Es repetible. Luego abra <http://localhost:8000/> e ingrese con el usuario `auditor` o `administrador` (contraseña `demo`, solo para esta demostración local; cámbiela con `--password`).

Qué esperar:

- **Primera ejecución con `--auditar`:** descarga el modelo de embeddings (unos 1,1 GB) y requiere internet esa única vez; `torch` ocupa unos 0,5 GB. Después todo funciona sin conexión.
- **Tablero:** 5 hallazgos, uno por tipo, todos *pendientes de revisión*, con 9 de 11 parámetros operacionalizados.
- Si el modelo no carga (por ejemplo, Windows bloquea una biblioteca nativa), `python manage.py verificar_entorno` indica qué componente falla. Sin `--auditar` puede explorar el resto de las pantallas.

Para probar con reportes reales, cargue su archivo en *Cargar archivo* con una plantilla de mapeo (hay una de ejemplo para el reporte de asociación de indicadores con PAA: `python manage.py seed_plantilla_paa_2025`). Los reportes reales no se incluyen en el repositorio porque contienen datos personales.

## Instalación detallada

### Requisitos

- Python 3.12
- PostgreSQL (o SQLite para pruebas funcionales: `USE_SQLITE_LOCAL=True`)

### Instalación

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env          # usa SQLite por defecto; para PostgreSQL ajuste DATABASE_URL
python manage.py migrate
```

### Puesta en marcha (paso a paso)

```bash
python manage.py seed_catalogo_gobernanza   # 11 parámetros y 5 reglas de auditoría
python manage.py seed_roles --usuarios --password <clave>   # grupos Administrador, Auditor y Consulta + usuarios de demostración
python manage.py seed_plantilla_demo        # plantilla de mapeo del conjunto de control
python manage.py runserver
```

Ingrese en <http://localhost:8000/> con el usuario `auditor`, `administrador` o `consulta`.

Flujo de uso (cinco casos de uso):

1. **CU1** Cargar archivo: suba `datos_ejemplo/conjunto_control_2026.csv` con la plantilla *Conjunto de control 2026* y la vigencia 2026.
2. **CU2–CU4** En el tablero, ejecute la auditoría sobre la vigencia 2026 (embeddings + reglas).
3. **CU5** Consulte los hallazgos, revíselos (confirmar o descartar), registre la correspondencia con la caracterización manual y exporte a Excel.
4. **Comparar vigencias** (menú superior): seleccione una o varias vigencias y vea sus indicadores, hallazgos (de la última auditoría de cada una), la variación porcentual entre ellas y una gráfica.

El acceso es por roles (RBAC), con permisos de Django asignados a tres grupos:

| Rol | Puede |
|---|---|
| **Administrador** | Todo lo del auditor y, además, configurar plantillas de mapeo, parámetros y reglas desde `/admin/` |
| **Auditor** | Cargar reportes, ejecutar la auditoría, confirmar o descartar hallazgos, registrar la correspondencia, comparar vigencias y exportar |
| **Consulta** | Solo lectura: tablero, hallazgos, comparación de vigencias y exportación |

Un rol sin el permiso recibe una página 403; las opciones que no le corresponden no aparecen en el menú.

## Validación funcional

```bash
python manage.py test                                   # pruebas automatizadas (no cargan el modelo)
python manage.py matriz_validacion --salida matriz.xlsx # 19 casos sobre el conjunto de control, con el modelo real
python manage.py matriz_validacion --sin-modelo         # misma matriz con pares candidatos simulados
```

`matriz_validacion` ejecuta la matriz de validación funcional (Anexo D de la monografía) dentro de una transacción que se revierte: no deja datos en la base.

## Estructura

| Módulo | Responsabilidad |
|---|---|
| `apps/gobernanza` | Dependencias, catálogo de parámetros (11, en 5 tipos) y ejecuciones de auditoría |
| `apps/ingesta` | Carga de Excel/CSV con plantillas de mapeo configurables; hoja de vida e historial |
| `apps/nlp_engine` | Embeddings y pares candidatos por similitud coseno |
| `apps/auditoria` | Reglas de auditoría, hallazgos con trazabilidad y matriz de validación |
| `apps/dashboard` | Tablero, listado y revisión de hallazgos |
| `apps/reportes` | Exportación de hallazgos a Excel |

## Configuración

Variables de `.env`: `DATABASE_URL`, `USE_SQLITE_LOCAL`, `EMBEDDING_MODEL`, `UMBRAL_DUPLICIDAD` (0.85) y `UMBRAL_CLONACION_TEXTUAL` (0.95).

## Stack

Python 3.12 · Django 5.2 LTS · PostgreSQL · sentence-transformers 6.1 (PyTorch 2.14) · openpyxl 3.1 · django-environ · Bootstrap 5.3 (CDN).

## Licencia

Código publicado bajo licencia MIT (ver [LICENSE](LICENSE)). El conjunto de datos de ejemplo es sintético. Los reportes institucionales reales del Plan de Acción no hacen parte del repositorio.
