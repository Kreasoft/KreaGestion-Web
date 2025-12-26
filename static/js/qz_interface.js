/* 
 * Interfaz QZ Tray para Impresión Directa
 * Requiere que qz-tray.js esté cargado previamente
 */

var qzConfig = {
    printerName: null, // Se cargará del localStorage o selección del usuario
    isConnected: false,
    host: 'localhost'
};

const QZ_Printers = {
    // Configuración de Seguridad (Necesaria para evitar error 'certificate undefined')
    initSecurity: function () {
        qz.security.setCertificatePromise(function (resolve, reject) {
            // Resolver vacío para permitir conexión (mostrará alerta de "Entidad no confiable" que el usuario debe aceptar)
            resolve();
        });

        qz.security.setSignaturePromise(function (toSign) {
            return function (resolve, reject) {
                // Resolver vacío (sin firma)
                resolve();
            };
        });
    },

    // Inicializar conexión
    connect: function () {
        if (typeof qz === 'undefined') {
            console.warn("Librería QZ Tray no cargada");
            return Promise.reject("Librería QZ Tray no cargada");
        }

        // Inicializar seguridad antes de conectar
        QZ_Printers.initSecurity();

        if (qz.websocket.isActive()) {
            console.log("QZ Tray ya está conectado");
            qzConfig.isConnected = true;
            return Promise.resolve();
        }

        return qz.websocket.connect().then(function () {
            console.log("Conectado a QZ Tray");
            qzConfig.isConnected = true;
            // Restaurar impresora guardada
            QZ_Printers.loadSavedPrinter();
        }).catch(function (e) {
            console.error("Error conectando a QZ Tray:", e);
            qzConfig.isConnected = false;
            throw e; // Relanzar error para que el llamador lo maneje
        });
    },

    // Obtener lista de impresoras
    getPrinters: function () {
        if (!qzConfig.isConnected) return Promise.reject("No conectado a QZ Tray");
        return qz.printers.find();
    },

    // Guardar impresora preferida
    setPrinter: function (printerName) {
        qzConfig.printerName = printerName;
        localStorage.setItem('qz_selected_printer', printerName);
        console.log("Impresora establecida a:", printerName);
    },

    loadSavedPrinter: function () {
        const saved = localStorage.getItem('qz_selected_printer');
        if (saved) {
            qzConfig.printerName = saved;
            console.log("Impresora guardada cargada:", saved);
        }
        return saved;
    },

    // Imprimir contenido HTML directamente
    printHTML: function (htmlContent) {
        if (!qzConfig.isConnected) {
            return QZ_Printers.connect().then(() => QZ_Printers.printHTML(htmlContent));
        }

        const printer = QZ_Printers.loadSavedPrinter();
        if (!printer) {
            alert("No hay impresora térmica configurada. Por favor seleccione una en la configuración.");
            return Promise.reject("Ninguna impresora seleccionada");
        }

        // Crear configuración para impresora de recibos
        // Units can be 'in', 'mm', 'cm'
        var config = qz.configs.create(printer, {
            scaleContent: true,
            // margins: { top: 0, right: 0, bottom: 0, left: 0 },
            // size: { width: 80, height: null }, // 80mm ancho, altura auto
            // units: 'mm'
        });

        // Impresión HTML
        var printData = [
            {
                type: 'pixel',
                format: 'html',
                flavor: 'plain',
                data: htmlContent
            }
        ];

        return qz.print(config, printData).then(function () {
            console.log("Impresión enviada exitosamente a " + printer);
        }).catch(function (e) {
            console.error(e);
            alert("Error al imprimir con QZ Tray: " + e);
            throw e;
        });
    },

    // Imprimir desde URL (descargar HTML luego imprimir)
    printTicketFromUrl: function (url) {
        console.log("Obteniendo ticket desde:", url);
        return fetch(url)
            .then(response => {
                if (!response.ok) throw new Error("Error obteniendo ticket");
                return response.text();
            })
            .then(html => {
                return QZ_Printers.printHTML(html);
            });
    }
};

// Auto-conectar al cargar

