# Eevee — Plan de pruebas y manejo de errores

Versión base: rama `feature/cm-to-alfred`, commit `0ee3b54`.

## 1. Arquitectura y puntos donde Eevee puede fallar

```
[Usuario] → index.html / app.js ─(FileReader)→ Pyodide (CDN) → parse_csv → transform → validación → write_excel → [Descarga XLSX]
```

| # | Capa | Qué puede fallar |
|---|------|------------------|
| A | Carga de la página | CDN de Pyodide caído o bloqueado por proxy, `micropip install openpyxl` falla, `mapping.py` o `transform.py` no se descargan (404) o quedan en caché |
| B | Entrada del archivo | Archivo que no es CSV, `.CSV` en mayúsculas, XLSX renombrado, archivo vacío, codificación UTF-16/Latin-1, BOM, separador `;` |
| C | Paso de JS a Python | El contenido del CSV y el nombre del archivo se insertan dentro de un string Python `'''...'''`. Un `\`, `'''` o `'` en el nombre o los datos puede romper o alterar la ejecución |
| D | Parseo (`parse_csv`) | Fila de encabezado no detectada, encabezados duplicados, columnas faltantes, filas más cortas o largas que el encabezado |
| E | Normalización | Fechas en formatos no soportados (`Jan-26`, `2026-01-05 00:00:00`), ambigüedad dd/mm frente a mm/dd, montos como `1,234` o `1.234`, `USD`/`€`, país ausente en el nombre del archivo |
| F | Reglas de negocio | Plataforma desconocida, nivel no inferible, alias de TYPE o BID_TYPE, STAGE, GENDER, AGE_RANGE, PRICING_MODEL |
| G | Jerarquía e IDs | Campaigns implícitas, IO huérfanos de DV360, duplicados, contadores por padre, sumas de presupuesto |
| H | Validación | Obligatorios por plataforma y nivel, exclusión de campos manuales |
| I | Excel | Dropdowns, columnas mayores a Z, hoja "Errores", volumen |
| J | Descarga y UI | Habilitar o bloquear la descarga, vista previa, reinicio, mensajes |

## 2. Manejo de errores actual

| Tipo de error | Dónde se captura | Qué ve el usuario hoy | ¿Bloquea la descarga? |
|---|---|---|---|
| Falla la carga de Pyodide, openpyxl o los módulos | `initPyodide` try/catch | "Error al cargar: …" | Sí, no se puede procesar |
| Archivo sin `.csv` | `handleFile` | "Por favor selecciona un archivo .csv" | Sí |
| Motor no listo | `processCSV` | "Motor Python no está listo. Recarga la página." | Sí |
| Excepción en Python (`run`) | try/except en `run` y en `processCSV` | Nada visible: la lista de errores está desactivada temporalmente | Sí, porque no hay XLSX |
| Falta un campo obligatorio | `transform` → lista `errors` | No se muestra en la UI (desactivada); aparece en la hoja **Errores** del XLSX, en inglés | No (definido por negocio) |
| Error en la vista previa | `buildPreview` catch | Solo en la consola (F12) | No |
| Plataforma desconocida o nivel no inferible | `transform` (`continue`) | Se omite la fila y se reporta un error con su número de fila de CM | No |
| Fecha no parseable | `parse_date` → vacío | Se convierte en error de obligatorio START_/END_ | Indirectamente |
| Monto no parseable | `clean_currency` → vacío | Se convierte en error de obligatorio BUDGET | Indirectamente |
| País no encontrado en el nombre del archivo | `extract_country_from_filename` → "" | Error de obligatorio COUNTRY | Indirectamente |
| Error al generar el Excel | `run` except | "Fatal error" dentro de `errors` (no visible) | Sí, porque no hay bytes |

## 3. Hallazgos críticos (corregir antes de producción)

> Comportamiento definido por negocio (no se modifica): un archivo con errores de validación **sí se puede descargar**; los errores quedan registrados en la hoja **Errores** del XLSX.

1. **La lista de errores está desactivada en la UI** (temporal, por la reunión). El usuario no sabe qué corregir.
2. **Inyección o rotura por string embebido.** El CSV se concatena dentro de un string Python. Una `\` en los datos se interpreta como escape (`\n`, `\t`, `\x`), y un `'` en el nombre del archivo rompe el código. Corrección: pasar los datos con `pyodide.globals.set("csv_text", ...)` en lugar de interpolarlos.
3. **Corregido: filas descartadas en silencio.** Una plataforma no reconocida o un Line Item sin código de nivel se siguen omitiendo (no se inventa plataforma ni nivel), pero ahora se reportan como error con el número de fila de CM. Las filas sin Line Item ni plataforma no generan aviso.
4. **Montos ambiguos.** `1,234` se interpreta como 1.234 (formato europeo) y `1.234` como 1.234 (formato americano). Hay que confirmar el formato real del export de CM y fijarlo.
5. **Fechas ambiguas.** `03/04/2026` siempre se toma como dd/mm. Si CM exporta mm/dd, las fechas salen cruzadas sin error. Además, `Jan-26` y los datetime con hora no están soportados.
6. **El número de fila de los errores no corresponde al CSV de CM.** "Row N" es la posición en la salida de ALFRED, que incluye filas generadas y excluye las descartadas, así que no coincide con la fila que el usuario debe corregir en CM.
7. **Mensajes en inglés** ("Missing mandatory field") cuando el requisito es español y sin jerga.
8. **BOM y codificación.** Un CSV con BOM (`\ufeffPlatform`) o en UTF-16 puede dejar de reconocer la columna `Platform`, y todas las filas se descartan en silencio.
9. **El archivo se transforma dos veces** (proceso + vista previa). Duplica el tiempo con archivos grandes.
10. **Corregido: país detectado por subcadena del nombre del archivo.** Ahora se ignoran la extensión y las carpetas y solo se reconocen códigos completos separados por signos o espacios. `Campaign_GT.csv` devuelve GT. Sin código válido o con varios países distintos, COUNTRY queda vacío y se reporta como obligatorio faltante; se mantiene la descarga.
11. **El dropdown de BID_TYPE_OPTIMIZATION_TYPE supera el límite de 255 caracteres** que Excel permite en una lista de validación. Excel puede pedir "reparar" el archivo y eliminar ese dropdown.

## 4. Matriz de pruebas

Prioridad: **P0** = bloquea producción · **P1** = importante · **P2** = deseable.

### 4.1 Unitarias (motor Python, pytest)

| ID | Función | Caso | Esperado | P |
|---|---|---|---|---|
| U-01 | `parse_date` | `2026-01-15`, `15/01/2026` | (15, 1, 2026) | P0 |
| U-02 | `parse_date` | `03/04/2026` | Documentar la interpretación (dd/mm) | P0 |
| U-03 | `parse_date` | `Jan-26`, `2026-01-15 00:00:00`, `abc`, vacío | Definir el soporte; hoy devuelve None | P1 |
| U-04 | `clean_currency` | `$1,234.56`, `1.234,56`, `1000`, `0` | 1234.56 / 1234.56 / 1000 / 0 | P0 |
| U-05 | `clean_currency` | `1,234`, `1.234`, `USD 500`, `-50`, `N/A` | Documentar o corregir la ambigüedad | P0 |
| U-06 | `extract_country_from_filename` | Nombre con país, sin país, en minúsculas, dos países | Código correcto o "" | P1 |
| U-07 | `extract_gender` / `extract_age_range` | Códigos y etiquetas de Target Audience (`HM` = People; `Female/Male/People 18+`), vacío y herencia bidireccional | Conserva edad; hereda del ancestro más cercano o completa padres con consenso de hijos. Audiencias diferentes no se mezclan; un valor propio prevalece. Incluye padres generados y conflictos multinivel | P0 |
| U-08 | `normalize_stage` | Todos los valores de `STAGE_MAPPING` + desconocido | Valor válido o vacío | P0 |
| U-09 | `normalize_platform` | Cada plataforma, alias (Facebook, Instagram, Messenger, YT), fallback por Publisher y OU Planning Level, desconocida | Plataforma de catálogo | P0 |
| U-10 | `determine_level_dv360` | Campaign, IO, LI, Ad Group, filler | Nivel correcto o None | P0 |
| U-11 | `determine_level_two_tier` | Meta/TikTok/etc. por jerarquía, sin usar Plan Level | Nivel correcto | P0 |
| U-12 | `infer_type` | `nonskip` antes de `skip`; `VV` = Video Views | TYPE correcto | P0 |
| U-13 | `resolve_pricing_model` | Cost Type válido, `N/A`, vacío | Valor o fallback | P1 |
| U-14 | `normalize_bid_type_key` / `get_bid_type_options_for_row` | Por plataforma | Opciones correctas | P1 |
| U-15 | `parse_csv` | Fila decorativa encima del encabezado, `Plan level`, encabezados duplicados, filas cortas o vacías | Diccionarios correctos | P0 |
| U-16 | `parse_csv` | Vacío, solo encabezado, BOM, `;` como separador | `[]` o un error explícito | P0 |
| U-17 | `generate_ids` | Contador reiniciado por padre (TK2-1, TK2-2) | IDs únicos y secuenciales | P0 |
| U-18 | `inject_implicit_campaigns` | IO huérfanos de DV360 → una Campaign compartida | 1 Campaign y datos del hijo | P0 |
| U-19 | `reconcile_parent_budgets` | Suma de BUDGET, TOTAL_BUDGET y BONO de hijos directos | Suma exacta | P0 |
| U-20 | AUTOBIDDERS | `yes`, `sí`, `1`, vacío, `No` | Yes/No; No por defecto | P1 |

### 4.2 Flujo (end-to-end del motor: `run(csv, filename)` con fixtures)

| ID | Fixture | Verifica | P |
|---|---|---|---|
| F-01 | `dv360_completo.csv` (Campaign → IO → LI) | Ad Group generado que hereda del LI; BUDGET/TOTAL_BUDGET/BONO = 0; IDs | P0 |
| F-02 | `dv360_io_huerfanos.csv` | Una sola Campaign generada; suma de hijos; `CAMPAIGN_TAXO` vacío | P0 |
| F-03 | IO/LI repetido con datos distintos y `dv360_io_li_repetido.csv` (idéntico) | Regresión del commit `0ee3b54`: con datos distintos, ambos Ad Groups existen con IDs distintos; si son idénticos, sale una sola rama | P0 |
| F-04 | `meta_campaign_duplicada.csv` | Se elimina la Campaign vacía duplicada y se conserva la única sin hijos | P0 |
| F-05 | `tiktok_ids.csv` | Regresión: TK2-1/TK2-2 en lugar de TK2-3/TK2-4 | P0 |
| F-06 | Un fixture por plataforma (Pinterest, Google Ads, Amazon Prime) | Las 61 columnas en orden; obligatorios OK | P0 |
| F-07 | `multiplataforma.csv` | Mezcla de plataformas sin que se crucen IDs ni jerarquías | P1 |
| F-08 | `faltan_obligatorios.csv` (sin GENDER, AGE_RANGE, STAGE o PRICING_MODEL) | `has_errors=True` y error por campo | P0 |
| F-09 | `plataforma_desconocida.csv` | La fila se omite y se reporta error visible (implementado) | P0 |
| F-10 | `bono_allocated_coupons.csv` | BONO leído de `Allocated Coupons (Planned)` | P1 |
| F-11 | `volumen_5000_filas.csv` | Tiempo menor a X s y memoria estable | P1 |
| F-13 | Filas que solo difieren en columnas que Eevee ignora (`Publisher ID`, `Planned CPM`, ...) | Salen como una sola fila; IDs consecutivos y presupuesto del padre sin inflar. Si difiere un dato usado (p. ej. presupuesto), se conservan ambas | P0 |
| F-12 | Golden file: CSV real anonimizado → XLSX esperado validado por el PO | Comparación celda a celda (detecta cualquier regresión) | P0 |

### 4.3 Excel (salida)

| ID | Caso | Esperado | P |
|---|---|---|---|
| X-01 | Encabezados | Exactamente `ALFRED_COLUMN_ORDER` (61) | P0 |
| X-02 | Dropdowns | STATUS, STAGE, PACING, BUDGET_TYPE, IMP_STATUS, CAMPAIGN_GOAL, TYPE y AUTOBIDDERS con sus opciones | P0 |
| X-03 | Sin NamedRange ni `INDIRECT` | El archivo abre sin reparación en Excel | P0 |
| X-04 | Hoja "Errores" | Existe solo si hay errores | P1 |
| X-05 | Tipos | Montos numéricos, no texto | P1 |
| X-06 | Importación en ALFRED | El XLSX de F-12 se carga en ALFRED sin rechazo (prueba manual con el PO) | P0 |

### 4.4 UI e integración (Playwright o manual)

| ID | Caso | Esperado | P |
|---|---|---|---|
| I-01 | Archivo válido | Vista previa y estado de descarga según el comportamiento actual | P0 |
| I-02 | Archivo con errores de validación | **Descarga habilitada**; los errores aparecen en la hoja "Errores" del XLSX | P0 |
| I-03 | Archivo `.xlsx`, `.txt` o `.CSV` | Mensaje claro; `.CSV` en mayúsculas debería aceptarse | P1 |
| I-04 | Archivo vacío | Mensaje "El archivo no tiene datos" | P0 |
| I-05 | Nombre del archivo con `'` o datos con `\` | El proceso no se rompe ni altera datos | P0 |
| I-06 | CDN bloqueado o sin internet | Mensaje de carga en español, sin pantalla rota | P1 |
| I-07 | Subir un segundo archivo / Reset | No quedan datos ni errores del archivo anterior | P1 |
| I-08 | Caché | Tras un deploy, el navegador usa el `transform.py` nuevo | P1 |
| I-09 | Nombre de descarga | `ALFRED_<nombre>.xlsx` | P2 |
| I-10 | Navegadores | Edge y Chrome corporativos | P1 |

### 4.5 No funcionales

| ID | Caso | P |
|---|---|---|
| N-01 | Privacidad: los datos nunca salen del navegador (sin llamadas de red con datos) | P0 |
| N-02 | Tiempo de carga inicial de Pyodide en la red de P&G | P1 |
| N-03 | Rendimiento con el archivo más grande esperado | P1 |

## 5. Herramientas recomendadas

- **pytest** para las capas U, F y X, con openpyxl para leer el XLSX generado y comparar contra el golden file.
- **GitHub Actions** para correr los tests en cada push o PR. Así no hace falta Python ni Node instalados en el equipo local.
- **Playwright** para la capa I (opcional; se pueden empezar como checklist manual).
- **Fixtures**: `tests/fixtures/*.csv` anonimizados, uno por caso de la matriz.

## 6. Orden sugerido de ejecución

1. Corregir los hallazgos 1 y 2 (P0) y crear sus pruebas de regresión.
2. Crear el golden file F-12 con un export real validado por el PO.
3. Implementar las pruebas P0 (unitarias + flujo) en pytest y GitHub Actions.
4. Convertir las filas omitidas en silencio en errores visibles en español.
5. Pruebas P1/P2 y la checklist manual de UI.

## 7. Suite automatizada (implementada)

| Archivo | Cubre |
|---|---|
| `tests/test_unit_normalizacion.py` | U-01 a U-09, U-13: fechas, montos, país, género, edad, STAGE, plataforma, PRICING_MODEL |
| `tests/test_unit_jerarquia.py` | U-10 a U-17: parseo del CSV, niveles, TYPE, BID_TYPE, IDs |
| `tests/test_flujo.py` | F-01 a F-11, U-18 a U-20: DV360, IO huérfanos, regresión de `0ee3b54`, IDs de TikTok, Meta duplicada, multiplataforma, casteo, obligatorios, `run()`, volumen de 5.000 filas |
| `tests/test_excel.py` | X-01 a X-05: encabezados, valores, hoja Errores, dropdowns, sin NamedRange ni `INDIRECT` |
| `tests/test_frequency.py` | Frequency numérico → texto `Nx7`; herencia bidireccional por consenso, conflictos, prioridad del valor propio, padres generados de DV360, deduplicación, valores inválidos y formato de celdas del Excel |
| `tests/test_zero_duplicates.py` | Copias en cero frente a una única alternativa con datos; conserva conflictos, alternativas no cero distintas y ceros sin alternativa. Regresión de los cuatro Ad Groups de Herbal Essences con IDs consecutivos |
| `tests/test_brechas_conocidas.py` | Hallazgos abiertos como `xfail` estrictos: cuando alguien corrige uno, la suite avisa para quitar la marca |
| `tests/fixtures/*.csv` | Un CSV por escenario; agregar aquí los exports reales anonimizados |

Resultado actual: **303 pruebas pasan y 9 casos están marcados como `xfail`**. Los casos de detección de país ya pasan, incluidas mayúsculas/minúsculas, límites de códigos, ambigüedad y verificación de COUNTRY vacío con errores en el Excel descargable. Se incluyen formatos de audiencia con códigos o etiquetas, HM = People y herencia bidireccional con consenso y conflictos multinivel. Frequency se transforma a texto `Nx7` con las mismas reglas de herencia.

### Cobertura de países y UAT

- La suite parametriza los 25 códigos de `COUNTRY_CODES`, tanto en mayúsculas como en minúsculas, sin asumir que todo archivo es de México.
- El UAT en `uat/Eevee_UAT.xlsx` contiene 32 escenarios por Key User: 17 de Data Validation, 10 de Tool Functionality y 5 de Workflow/Integration.
- El UAT mantiene solo dos escenarios de negocio para país: 1.7 valida el mercado correcto con Colombia y Guatemala (`CO_2026.csv`, `GT_2026.csv`); 1.17 valida que un mercado no identificable quede vacío y se reporte en el Excel (`export.csv`), manteniendo la descarga.
- La matriz completa de 25 códigos, mayúsculas/minúsculas, códigos dentro de palabras, extensión, separadores y ambigüedad corresponde a pytest, no a tareas del Key User.
- Los 28 CSV de países generados contienen las mismas 5 filas de TikTok para aislar el efecto del nombre del archivo. Solo tres se requieren en el UAT; el resto queda como material técnico opcional.
- Se corrigió la detección: los 25 códigos configurados deben obtenerse correctamente. `export.csv` queda sin país, `Campaign_GT.csv` devuelve GT y `MX_CO.csv` queda sin país.
- Los resultados del UAT se dejan vacíos para ejecución por los Key Users. La corrección solo afecta a la detección de COUNTRY; no modifica la política de descarga con errores ni otras reglas de transformación.

Quedan fuera de pytest: la capa de UI (I-01 a I-10), la importación real en ALFRED (X-06) y el golden file con datos reales (F-12).

Ejecución:

```
pip install -r requirements-dev.txt
pytest
```

GitHub Actions (`.github/workflows/tests.yml`) corre la suite en cada push y pull request.
