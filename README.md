# Eevee — CM to ALFRED Converter

**Herramienta web para transformar exportaciones de Campaign Manager (CM) al formato ALFRED de P&G.**

![Status](https://img.shields.io/badge/status-beta-yellow) ![Python](https://img.shields.io/badge/python-3.8+-blue) ![License](https://img.shields.io/badge/license-P%26G-blue)

---

## 📋 Contenido Rápido

- [¿Qué es Eevee?](#qué-es-eevee)
- [Estructura de archivos](#estructura-de-archivos)
- [Explicación por archivo](#explicación-por-archivo)
- [Flujo completo](#flujo-completo)
- [Plataformas soportadas](#plataformas-soportadas)
- [Requisitos de entrada](#requisitos-de-entrada)
- [Git workflow](#git-workflow)

---

## ¿Qué es Eevee?

**Eevee** es una herramienta web que convierte archivos CSV de Campaign Manager a formato XLSX compatible con ALFRED (el sistema de P&G que recibe los datos de medios).

**Características:**
- ✅ Conversión completa CM → ALFRED en el navegador (sin servidor backend)
- ✅ Soporta 6 plataformas: DV360, Meta, TikTok, Pinterest, Google Ads, Amazon Prime
- ✅ Validaciones automáticas contra especificaciones de ALFRED
- ✅ Generación de XLSX con estilos, dropdowns y hoja de errores
- ✅ Sin dependencias externas (Python en el navegador via Pyodide)

---

## 📁 Estructura de archivos

```
Eevee/
├── index.html                 → UI Web (interfaz usuario)
├── assets/
│   ├── app.js                → Orquestación Pyodide + manejo CSV
│   └── server.ps1            → Servidor HTTP local (desarrollo)
├── config/
│   └── mapping.py            → Configuración: campos, validaciones, opciones
├── scripts/
│   └── transform.py          → Motor de transformación CM → ALFRED
├── .git/                     → Control de versiones (git)
├── .gitignore               → Archivos ignorados en git
└── README.md                → Este archivo
```

---

## 📖 Explicación por archivo

### **1. index.html** — UI (La página que ve el usuario)

**¿Qué es?** La interfaz web que Eevee muestra en el navegador.

**¿Qué hace?**
- Zona de arrastrar-soltar para CSV de CM
- Mostrar archivo seleccionado (nombre y tamaño)
- Esperar mientras se procesa (spinner de carga)
- Mostrar tabla preview de las primeras 8 filas con colores:
  - 🟢 Verde = Campos automáticos
  - 🟡 Amarillo = Campos que el usuario debe llenar en Excel
- Descargar XLSX resultado
- Mostrar errores de validación en rojo

**Tecnología:** Tailwind CSS + HTML5 + JavaScript vanilla

**Dependencias externas:**
- Tailwind CSS (CDN)
- Pyodide v0.27.5 (CDN)

---

### **2. assets/app.js** — Orquestador JavaScript

**¿Qué es?** El "cerebro" del navegador que conecta la UI con Python.

**¿Qué hace?**
1. Carga **Pyodide** (Python ejecutándose en WebAssembly)
2. Instala **openpyxl** para generar Excel
3. Crea sistema de archivos virtual en JavaScript
4. Lee CSV del usuario
5. Copia `config/mapping.py` y `scripts/transform.py` al filesystem virtual
6. Ejecuta transformación (llama función `run()` de transform.py)
7. Genera XLSX y lo descarga como Blob
8. Maneja errores y actualiza UI en tiempo real

**Flujo de inicialización:**
- Espera a que `loadPyodide` esté definido (defer + wait loop)
- Carga Pyodide desde CDN (500ms de delay para stability)
- Instala micropip y openpyxl
- Importa `run` de transform.py
- Listo para procesar CSVs

**Tecnología:** JavaScript vanilla + Pyodide v0.27.5 + openpyxl

---

### **3. assets/server.ps1** — Servidor HTTP (Desarrollo)

**¿Qué es?** Servidor HTTP local, 100% PowerShell, sin dependencias externas.

**¿Qué hace?** Sirve los archivos de Eevee en `http://localhost:8000` para testing local.

**Por qué es importante:** Permite desarrollar sin necesidad de Python/Node.js instalados.

**Uso:**
```powershell
cd C:\Users\[user]\OneDrive - Procter and Gamble\Desktop\Eevee
.\server.ps1
# Accede a http://localhost:8000 en el navegador
```

---

### **4. config/mapping.py** — Configuración (La "receta" de negocio)

**¿Qué es?** Archivo centralizado con TODAS las reglas de transformación y validación.

**¿Por qué es importante?** Es el único archivo que cambia cuando Alfred cambia sus especificaciones.

**¿Qué contiene?**

| Sección | Descripción |
|---------|-------------|
| **DIRECT_MAPPING** | Qué campos de CM van a ALFRED (7 campos: Brand → BRAND, etc) |
| **FIXED_VALUES** | Valores que son siempre iguales (BUY_TYPE="Auction", REGION="National", etc) |
| **PLATFORM_CONFIG** | Estructura de niveles por plataforma y prefijos de ID |
| **TYPE_OPTIONS** | Opciones de TYPE por (Platform, Level) - dropdowns en Excel |
| **BID_TYPE_OPTIONS** | Opciones de estrategia de pujas por (Platform, Tipo) |
| **STAGE_MAPPING** | Normalización (performance → Awareness, etc) |
| **PACING_OPTIONS** | Opciones de ritmo (solo DV360): Flight_Ahead, Flight_Even, Daily_Asap, Daily_Even |
| **BUDGET_TYPE_OPTIONS** | Tipos de presupuesto (Meta + TikTok): Standard, Advantage |
| **IMP_STATUS_OPTIONS** | Estados de implementación (todas plataformas): Implemented, Pending, Manual Imp. |
| **ALFRED_COLUMN_ORDER** | Orden exacto de las 61 columnas (fuente de verdad de Alfred) |
| **ALFRED_MANDATORY** | 29 campos que no pueden ser vacíos (valida por plataforma) |

**Ejemplo de PLATFORM_CONFIG:**
```python
"DV360": {
    "prefix": "DV",
    "levels": ["Campaign", "Insertion Order", "Line Item", "Ad Group"],
    "uses_plan_level": False  # Usa prefijo en Line Item (IO/LI/ADG)
},
"Meta": {
    "prefix": "M",
    "levels": ["Campaign", "Ad Group"],
    "uses_plan_level": True  # Lee Plan Level de columna
}
```

---

### **5. scripts/transform.py** — Motor de transformación

**¿Qué es?** La lógica que convierte CM → ALFRED, valida y genera Excel.

**¿Qué hace?**

**Parsing:**
- Lee CSV de CM como diccionarios (csv.DictReader)

**Transformación (3 passes):**
1. **Pass 1:** Detecta niveles jerárquicos y filtra filas válidas
2. **Pass 2:** Genera IDs jerárquicos (DV1, DV1-1, DV1-1-1, etc)
3. **Pass 3:** Construye filas ALFRED aplicando:
   - Mapeos directos (Brand → BRAND)
   - Transformaciones complejas:
     - Parseo de fechas (YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY)
     - Limpieza de monedas (detección formato europeo vs americano)
     - Extracción de género/edad de Target Audience
     - Normalización de etapas
     - Extracción de taxonomía de Line Item
   - Validaciones

**Validación:**
- Verifica campos MANDATORY contra ALFRED_MANDATORY
- Validaciones condicionales por plataforma:
  - DV360 sin Campaign: requiere PACING, BID_VALUE, KPI_VALUE
  - DV360 Campaign: no requiere estos campos
  - Meta/TikTok: requieren BUDGET_TYPE
  - Reporte de errores en hoja separada

**Excel Output:**
- Headers azul oscuro (#00205B) con texto blanco
- Campos manuales en amarillo (#FFF2CC)
- Dropdowns contextuales:
  - STATUS: para todas las filas (todas plataformas)
  - PACING: solo DV360 no-Campaign
  - BUDGET_TYPE: solo Meta/TikTok
  - IMP_STATUS: todas las filas (todas plataformas)
- Hoja "Errores" si hay validaciones fallidas
- Filas congeladas en header

---

## 🔄 Flujo completo

```
Usuario descarga CSV de Campaign Manager
              ↓
Abre index.html en navegador
              ↓
Arrastra CSV a la zona de drop (drag-and-drop)
              ↓
app.js carga Pyodide desde CDN + micropip + openpyxl
              ↓
app.js lee CSV del usuario
              ↓
app.js copia mapping.py y transform.py al filesystem virtual
              ↓
app.js llama transform.run(csv_text, filename)
              ↓
transform.py ejecuta 3-pass algorithm:
  - Pass 1: Detecta niveles
  - Pass 2: Genera IDs
  - Pass 3: Transforma a ALFRED
              ↓
transform.py valida contra ALFRED_MANDATORY (por plataforma)
              ↓
transform.py genera XLSX con estilos, dropdowns, errores
              ↓
app.js descarga XLSX al navegador del usuario
              ↓
Usuario recibe ALFRED.xlsx + Errores.xlsx (si hay)
```

**Tiempo típico:** 2-5 segundos (depende de tamaño del CSV)

---

## 🌍 Plataformas soportadas

| Plataforma | Niveles | ID Prefix | Plan Level | Validaciones especiales |
|---|---|---|---|---|
| **DV360** | Campaign, Insertion Order, Line Item, Ad Group | DV | NO (prefijo en Line Item) | Campaign no requiere PACING, BID_VALUE, KPI_VALUE |
| **Meta** | Campaign, Ad Group | M | SÍ | Requiere BUDGET_TYPE |
| **TikTok** | Campaign, Ad Group | TK | SÍ | Requiere BUDGET_TYPE, BID_VALUE |
| **Pinterest** | Campaign, Ad Group | P | SÍ | PACING/BUDGET_TYPE/BID_VALUE = NULL |
| **Google Ads** | Campaign, Ad Group | G | SÍ | PACING/BUDGET_TYPE/BID_VALUE = NULL |
| **Amazon Prime** | Campaign, Ad Group | A | SÍ | PACING/BUDGET_TYPE/BID_VALUE = NULL |

---

## 📥 Requisitos de entrada (CM CSV)

**OBLIGATORIOS (sin estos rompe el tool):**

| Campo | Formato | Razón |
|---|---|---|
| Platform | DV360, Meta, TikTok, Pinterest, Google Ads, Amazon Prime | Define tipo de campaña |
| Line Item | Jerarquía con → (ej: "Herbal Essences→IO1→LI2→ADG3") | Extrae LEVEL, IDs, taxonomía |
| Plan Level* | Campaign, Insertion Order, Line Item, Ad Group | Para Meta, TikTok, Pinterest, Google Ads, Amazon Prime |
| Start Date | YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY | Genera START_DAY/MONTH/YEAR |
| End Date | Mismo formato que Start Date | Genera END_DAY/MONTH/YEAR |
| Brand | Texto | BRAND en ALFRED (MANDATORY) |
| Sub Brand | Texto | SUB_BRAND en ALFRED (MANDATORY) |
| Total Budget | Número (1.234,56 o 1,234.56) | TOTAL_BUDGET en ALFRED (MANDATORY) |
| Target Audience | Formato [W/M/P]_[18-24/25-34/etc] | Genera GENDER, AGE_RANGE (MANDATORY) |
| Media Objective | performance, awareness, consideration, conversion, data gathering | Genera STAGE (MANDATORY) |
| Initiative | Texto | INITIATIVE en ALFRED (MANDATORY) |
| Cost Type | Texto | Genera PRICING_MODEL (MANDATORY) |
| **Filename** | Contiene código país (MX, AR, BR, US, etc) | Extrae COUNTRY (MANDATORY) |

*Plan Level NO es necesario para DV360 (usa prefijo en Line Item)

---

## 🌳 Git Workflow

**Branching model (3-branch):**

```
main
  ├── Código probado, listo para producción
  └── Tagged releases (v0.1-alpha, etc)

develop
  ├── Rama de integración
  └── Agrupa features completadas

feature/cm-to-alfred
  ├── Desarrollo activo
  ├── Testing local
  └── Commits frecuentes
```

**Flujo típico:**
```bash
# En feature branch, comitea cambios
git add .
git commit -m "config: Update TYPE_OPTIONS"
git push origin feature/cm-to-alfred

# Cuando está listo, merge a develop
git checkout develop
git merge feature/cm-to-alfred
git push origin develop

# Cuando todo funciona, merge a main para release
git checkout main
git merge develop
git tag v0.1-alpha
git push origin main --tags
```

**Commits recientes (Sept 2-3):**
- Corrección de TYPE_OPTIONS (todas 14 combinaciones Platform/Level)
- Simplificación de BID_TYPE_OPTIONS para DV360 (Fixed only para Non_Skip, Skip, Bumper)
- Exclusión de PACING, BID_VALUE, KPI_VALUE para DV360 Campaign

---

## 🚀 Próximos pasos

- [ ] Testing con CSV reales de todas las plataformas
- [ ] Validación de STAGE_MAPPING con stakeholder (Performance/Data Gathering)
- [ ] Definir flujo de entrada de usuarios para campos manuales
- [ ] Merge feature → develop → main
- [ ] Configurar GitHub Pages o Netlify para deployment
- [ ] Documentación de usuario final

---

## 📞 Contacto & Preguntas

Para cambios en las reglas de transformación, editar `config/mapping.py`  
Para cambios en lógica de validación, editar `scripts/transform.py`  
Para cambios en UI, editar `index.html` y `assets/app.js`

---

**v0.1-beta | Sept 2026 | P&G Media Technology**