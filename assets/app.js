

let pyodideInstance = null;
let excelBytesCache = null;
let currentErrors = [];
let currentRowCount = 0;
let csvText = null;
let fileName = null;

// ============================================================================
// INITIALIZATION  ^^ 
// ============================================================================
async function initPyodide() {
    try {
        setStatus("Cargando motor Python...", true);

        // Wait for loadPyodide to be defined
        while (typeof loadPyodide === 'undefined') {
            await new Promise(resolve => setTimeout(resolve, 100));
        }

        // Load Pyodide from CDN
        const pyodide = await loadPyodide({
            indexURL: "https://cdn.jsdelivr.net/pyodide/v0.27.5/full/",
        });

        // Install micropip and openpyxl
        await pyodide.loadPackage("micropip");
        const micropip = pyodide.pyimport("micropip");
        
        console.log("Installing openpyxl...");
        await micropip.install("openpyxl");
        console.log("openpyxl installed successfully");

        // Fetch Python modules from server
        const mappingCode = await fetch("config/mapping.py").then(r => r.text());
        const transformCode = await fetch("scripts/transform.py").then(r => r.text());

        // Create directories in Pyodide filesystem
        try {
            pyodide.FS.mkdir("/config");
        } catch (e) {
            // Directory might already exist
        }
        try {
            pyodide.FS.mkdir("/scripts");
        } catch (e) {
            // Directory might already exist
        }

        // Write to Pyodide virtual filesystem
        pyodide.FS.writeFile("/config/__init__.py", "# Config module");
        pyodide.FS.writeFile("/config/mapping.py", mappingCode);
        pyodide.FS.writeFile("/scripts/__init__.py", "# Scripts module");
        pyodide.FS.writeFile("/scripts/transform.py", transformCode);

        // Add to path and import
        pyodide.runPython("import sys; sys.path.insert(0, '/')");
        pyodide.runPython("from scripts.transform import run");
        
        console.log("Pyodide initialized successfully");

        pyodideInstance = pyodide;
        setStatus("Motor Python cargado ✓", false);
        document.getElementById("pyodide-status").textContent = "Motor Python listo";

        setTimeout(() => hideStatus(), 2000);
    } catch (error) {
        console.error("Pyodide init error:", error);
        console.error("Full error stack:", error.stack);
        showFatalError(`<strong>Error al cargar:</strong> ${error.message}<br><small>Revisa la consola (F12) para más detalles</small>`);
    }
}

// ============================================================================
// FILE HANDLING
// ============================================================================
function handleFile(file) {
    if (!file.name.endsWith(".csv")) {
        showFatalError("Por favor selecciona un archivo <strong>.csv</strong>");
        return;
    }

    fileName = file.name;
    document.getElementById("file-name").textContent = fileName;
    document.getElementById("file-size").textContent = `Tamaño: ${formatSize(file.size)}`;
    document.getElementById("file-info").style.display = "block";

    clearResults();

    const reader = new FileReader();
    reader.onload = function (e) {
        csvText = e.target.result;
        processCSV(csvText, fileName);
    };
    reader.readAsText(file);
}

function processCSV(csv_text, filename) {
    if (!pyodideInstance) {
        showFatalError("Motor Python no está listo. Recarga la página.");
        return;
    }

    setStatus("Procesando transformación CM → ALFRED...", true);

    pyodideInstance.runPythonAsync(`
try:
    result = run('''${csv_text.replace(/'/g, "\\'")}''', '''${filename}''')
except Exception as e:
    result = {
        "excel_bytes": None,
        "errors": [f"Error: {str(e)}"],
        "row_count": 0,
        "has_errors": True,
    }
    import traceback
    print(traceback.format_exc())
    `).then(() => {
        const result = pyodideInstance.globals.get("result");
        const dict = result.toJs();

        excelBytesCache = dict.get("excel_bytes");
        currentErrors = dict.get("errors") || [];
        currentRowCount = dict.get("row_count") || 0;
        const hasErrors = dict.get("has_errors") || false;

        hideStatus();
        buildPreview();
        showDownload(!hasErrors);

        if (currentErrors.length > 0) {
            showErrors(currentErrors);
        }

        result.destroy();
    }).catch((error) => {
        hideStatus();
        console.error("Pyodide error details:", error);
        showFatalError(`<strong>Error en transformación:</strong> ${error.message}`);
    });
}

// ============================================================================
// PREVIEW RENDERING
// ============================================================================
function buildPreview() {
    // Re-run transform to get first 8 rows
    if (!pyodideInstance || !csvText || !fileName) return;

    try {
        pyodideInstance.runPython(`
            cm_rows = parse_csv('''${csvText.replace(/'/g, "\\'")}''')
            output_rows, errors = transform(cm_rows, '''${fileName}''')
        `);

        const output_rows = pyodideInstance.globals.get("output_rows").toJs();
        const manual_fields = pyodideInstance.globals.get("MANUAL_FIELDS").toJs();
        const alfred_column_order = pyodideInstance.globals.get("ALFRED_COLUMN_ORDER").toJs();

        // Display preview
        const table = document.getElementById("preview-table");
        table.innerHTML = "";

        // Header
        const headerRow = document.createElement("tr");
        alfred_column_order.slice(0, 15).forEach((col) => {
            const th = document.createElement("th");
            th.textContent = col;
            headerRow.appendChild(th);
        });
        table.appendChild(headerRow);

        // Data (first 8 rows)
        const previewRows = output_rows.slice(0, 8);
        previewRows.forEach((row, idx) => {
            const tr = document.createElement("tr");
            alfred_column_order.slice(0, 15).forEach((col) => {
                const td = document.createElement("td");
                const value = row.get ? row.get(col) : row[col] || "";

                td.textContent = String(value).substring(0, 20);

                // Highlight manual fields
                if (manual_fields.includes(col)) {
                    td.className = "manual-field";
                } else {
                    td.className = "auto-field";
                }

                tr.appendChild(td);
            });
            table.appendChild(tr);
        });

        document.getElementById("preview-section").style.display = "block";
        document.getElementById("preview-metadata").textContent = `Mostrando ${previewRows.length} de ${currentRowCount} filas totales`;

        // Cleanup
        if (output_rows.destroy) output_rows.destroy();
        if (manual_fields.destroy) manual_fields.destroy();
        if (alfred_column_order.destroy) alfred_column_order.destroy();
    } catch (error) {
        console.error("Preview build error:", error);
    }
}

// ============================================================================
// DOWNLOAD CONTROL
// ============================================================================
function triggerDownload() {
    if (!excelBytesCache) {
        showFatalError("No hay datos para descargar");
        return;
    }

    const blob = new Blob([excelBytesCache], {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });

    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `ALFRED_${fileName.replace(".csv", ".xlsx")}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function showDownload(hasErrors) {
    const section = document.getElementById("download-section");
    const btn = document.getElementById("download-btn");
    const warningsList = document.getElementById("warnings-list");

    if (hasErrors) {
        btn.disabled = true;
        btn.className = "btn-primary";
        btn.style.opacity = "0.5";
        btn.style.cursor = "not-allowed";
        btn.title = "Corrige los errores de validación para descargar";
        warningsList.innerHTML = `<div class="text-red-700"><strong>⚠️ No se puede descargar:</strong> Hay errores de validación. Revisa la sección de errores arriba.</div>`;
    } else {
        btn.disabled = false;
        btn.className = "btn-primary";
        btn.style.opacity = "1";
        btn.style.cursor = "pointer";
        btn.title = "";
        warningsList.innerHTML = `<div class="text-green-700"><strong>✓ Validación OK:</strong> Puedes descargar el archivo XLSX</div>`;
    }

    section.style.display = "block";
}

// ============================================================================
// UI HELPERS
// ============================================================================
function setStatus(msg, show) {
    const statusBox = document.getElementById("status-box");
    const statusMsg = document.getElementById("status-message");
    const spinner = document.getElementById("pyodide-spinner");

    statusMsg.textContent = msg;
    statusBox.style.display = show ? "block" : "none";
    spinner.style.display = show ? "block" : "none";
}

function hideStatus() {
    document.getElementById("status-box").style.display = "none";
}

function showErrors(errors) {
    const section = document.getElementById("error-section");
    const list = document.getElementById("error-list");

    list.innerHTML = "";
    errors.forEach((error) => {
        const div = document.createElement("div");
        div.className = "error-box";
        div.textContent = error;
        list.appendChild(div);
    });

    section.style.display = "block";
}

function showFatalError(html) {
    const section = document.getElementById("error-section");
    section.innerHTML = `<div class="error-box"><strong>❌ Error fatal:</strong> ${html}</div>`;
    section.style.display = "block";
}

function clearResults() {
    document.getElementById("error-section").style.display = "none";
    document.getElementById("preview-section").style.display = "none";
    document.getElementById("download-section").style.display = "none";
    currentErrors = [];
    currentRowCount = 0;
    excelBytesCache = null;
}

function resetUI() {
    document.getElementById("file-input").value = "";
    document.getElementById("file-info").style.display = "none";
    clearResults();
    csvText = null;
    fileName = null;
}

function formatSize(bytes) {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + " " + sizes[i];
}

// ============================================================================
// EVENT HANDLERS
// ============================================================================
document.addEventListener("DOMContentLoaded", function () {
    // Small delay to ensure Pyodide script is loaded
    setTimeout(() => {
        initPyodide();
    }, 500);

    const dropZone = document.getElementById("drop-zone");
    const fileInput = document.getElementById("file-input");

    dropZone.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            handleFile(e.target.files[0]);
        }
    });

    // Drag and drop
    dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.classList.add("drag-over");
    });

    dropZone.addEventListener("dragleave", () => {
        dropZone.classList.remove("drag-over");
    });

    dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.classList.remove("drag-over");
        if (e.dataTransfer.files.length > 0) {
            handleFile(e.dataTransfer.files[0]);
        }
    });
});
