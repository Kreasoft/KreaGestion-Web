
        // -- APP CORE --
        const app = {
            db: null,
            data: {
                products: [],
                categories: [],
                clients: [],
                pendingClients: [],
                vendedores: [],
                formas_pago: [],
                configuracion: {
                    permite_sin_stock: true,
                    intervalo_sync_minutos: 5
                }
            },
            cart: [],
            selectedProducts: {},
            selectedClientValue: '',
            currentClientQuery: '',
            activeCategoryId: null,
            currentProductQuery: '',
            filteredProducts: [],
            returnViewAfterClient: 'viewDashboard',
            deviceId: localStorage.getItem('gc_deviceId'),
            isAuthorized: localStorage.getItem('gc_isAuthorized') === 'true',
            syncTimer: null,
            
            // Map properties
            map: null,
            marker: null,
            currentCoords: null,

            init: async function() {
                console.log("Iniciando App Móvil...");
                
                // Eventos de red
                window.addEventListener('online', () => this.updateNetworkStatus());
                window.addEventListener('offline', () => this.updateNetworkStatus());

                // Inicializar DB local (IndexedDB)
                await this.initDB();
                this.registerServiceWorker();
                
                // Ahora que la DB está lista, podemos verificar estado de red
                this.updateNetworkStatus();
                
                // Cargar datos guardados
                await this.loadLocalData();
                
                // --- ACTUALIZAR VENDEDORES DESDE EL CONTEXTO DEL SERVIDOR ---
                const serverVendedores = [
                    
                ];
                
                // Mezclar sin duplicados (priorizando el id)
                serverVendedores.forEach(sv => {
                    const idx = this.data.vendedores.findIndex(lv => lv.id === sv.id);
                    if (idx === -1) {
                        this.data.vendedores.push(sv);
                    } else {
                        // Actualizar datos por si cambió nombre o código
                        this.data.vendedores[idx] = sv;
                    }
                });
                localStorage.setItem('gc_vendedores', JSON.stringify(this.data.vendedores));
                
                // Verificar login
                this.checkLogin();

                // Verificar dispositivo
                await this.checkDevice();

                if (this.seller && this.isAuthorized) {
                    const mainApp = document.getElementById('mainApp');
                    const loginView = document.getElementById('loginView');
                    if (loginView) loginView.style.display = 'none';
                    if (mainApp) mainApp.style.display = 'block';
                    this.showView('viewDashboard');
                }

                this.renderCategories();
                this.renderProducts();
                this.renderClients();
                this.updateCartCount();
                this.updateDebugCounters();
                this.updateSelectionBar();
                this.scheduleBackgroundSync();
                this.forceVisualOverrides();
                setTimeout(() => this.forceVisualOverrides(), 150);
                console.log("App iniciada correctamente");
            },

            updateDebugCounters: function() {
                const prodDisp = document.getElementById('debugProdCount');
                const cliDisp = document.getElementById('debugCliCount');
                const catDisp = document.getElementById('debugCatCount');
                if (prodDisp) prodDisp.innerText = this.data.products.length;
                if (cliDisp) cliDisp.innerText = this.data.clients.length;
                if (catDisp) catDisp.innerText = this.data.categories.length;
            },

            forceVisualOverrides: function() {
                const placeholderIds = [
                    'sellerCodeInput',
                    'productSearch',
                    'clientPickerSearch',
                    'occasionalClientName',
                    'checkoutComment',
                    'clientSearch',
                    'nc_rut',
                    'nc_nombre',
                    'nc_giro',
                    'nc_direccion',
                    'nc_comuna',
                    'nc_ciudad',
                    'nc_tel',
                    'nc_email'
                ];
                const selectIds = [
                    'docTypeSelect',
                    'finalDocTypeSelect',
                    'clientSelect'
                ];

                let styleTag = document.getElementById('gcRuntimePlaceholderStyles');
                if (!styleTag) {
                    styleTag = document.createElement('style');
                    styleTag.id = 'gcRuntimePlaceholderStyles';
                    document.head.appendChild(styleTag);
                }

                styleTag.textContent = placeholderIds.map(id => `
#${id}::placeholder { color: #cfd5dd !important; opacity: 1 !important; }
#${id}::-webkit-input-placeholder { color: #cfd5dd !important; opacity: 1 !important; }
#${id}::-moz-placeholder { color: #cfd5dd !important; opacity: 1 !important; }
`).join('\n');

                selectIds.forEach(id => {
                    const el = document.getElementById(id);
                    if (el) {
                        el.style.setProperty('color', '#6f7782', 'important');
                    }
                });

                const hint = document.getElementById('stockPolicyHint');
                if (hint) {
                    hint.style.setProperty('color', '#6f7782', 'important');
                    hint.style.setProperty('opacity', '1', 'important');
                    hint.style.setProperty('font-weight', '500', 'important');
                    hint.querySelectorAll('*').forEach(node => {
                        node.style.setProperty('color', '#6f7782', 'important');
                        node.style.setProperty('opacity', '1', 'important');
                    });
                }
            },

            updateNetworkStatus: function() {
                this.isOffline = !navigator.onLine;
                const banner = document.getElementById('offlineBanner');
                const indicator = document.getElementById('syncIndicator');
                if (banner) banner.style.display = this.isOffline ? 'block' : 'none';
                if (indicator) indicator.innerText = this.isOffline ? 'Offline' : 'Online';
                
                if (this.isOffline) {
                    document.body.classList.add('is-offline');
                } else {
                    document.body.classList.remove('is-offline');
                    this.autoSyncPending();
                    this.maybeSyncInBackground(true);
                }
            },

            registerServiceWorker: function() {
                if ('serviceWorker' in navigator) {
                    navigator.serviceWorker.getRegistrations()
                        .then(registrations => Promise.all(registrations.map(reg => reg.unregister())))
                        .catch(err => console.warn('No se pudo desregistrar service workers:', err));
                }

                if ('caches' in window) {
                    caches.keys()
                        .then(keys => Promise.all(keys.map(key => caches.delete(key))))
                        .catch(err => console.warn('No se pudo limpiar cache del navegador:', err));
                }
            },

            // -- DATABASE --
            initDB: function() {
                return new Promise((resolve) => {
                    const request = indexedDB.open('GestionCloudMobile', 2);
                    request.onupgradeneeded = (e) => {
                        const db = e.target.result;
                        if (!db.objectStoreNames.contains('products')) db.createObjectStore('products', { keyPath: 'id' });
                        if (!db.objectStoreNames.contains('categories')) db.createObjectStore('categories', { keyPath: 'id' });
                        if (!db.objectStoreNames.contains('clients')) db.createObjectStore('clients', { keyPath: 'id' });
                        if (!db.objectStoreNames.contains('sales')) db.createObjectStore('sales', { keyPath: 'localId', autoIncrement: true });
                        if (!db.objectStoreNames.contains('pendingClients')) db.createObjectStore('pendingClients', { keyPath: 'localId', autoIncrement: true });
                    };
                    request.onsuccess = (e) => {
                        this.db = e.target.result;
                        resolve();
                    };
                });
            },

            saveDataToDB: async function(storeName, data) {
                const tx = this.db.transaction(storeName, 'readwrite');
                const store = tx.objectStore(storeName);
                if (Array.isArray(data)) {
                    data.forEach(item => store.put(item));
                } else {
                    store.put(data);
                }
                return new Promise(resolve => tx.oncomplete = resolve);
            },

            loadFromDB: function(storeName) {
                return new Promise((resolve) => {
                    const tx = this.db.transaction(storeName, 'readonly');
                    const store = tx.objectStore(storeName);
                    const request = store.getAll();
                    request.onsuccess = () => resolve(request.result);
                });
            },

            clearObjectStore: function(storeName) {
                return new Promise((resolve) => {
                    const tx = this.db.transaction(storeName, 'readwrite');
                    const store = tx.objectStore(storeName);
                    const request = store.clear();
                    request.onsuccess = () => resolve();
                });
            },

            // -- AUTH --
            checkLogin: function() {
                const savedSeller = localStorage.getItem('gc_mobile_seller');
                if (savedSeller) {
                    this.seller = JSON.parse(savedSeller);
                    document.getElementById('loginView').style.display = 'none';
                    const mainApp = document.getElementById('mainApp');
                    if (mainApp) mainApp.style.display = 'block';
                    
                    const sbName = document.getElementById('sidebarSellerNameDisplay');
                    if (sbName) sbName.innerText = this.seller.nombre;
                    const dsName = document.getElementById('dashboardSellerName');
                    if (dsName) dsName.innerText = this.seller.nombre;
                    
                    this.showView('viewDashboard');
                }
            },

            login: function() {
                const code = document.getElementById('sellerCodeInput').value.trim().toUpperCase();
                const sellerFound = this.data.vendedores.find(v => v.codigo.trim().toUpperCase() === code);
                
                if (sellerFound) {
                    this.seller = sellerFound;
                    localStorage.setItem('gc_mobile_seller', JSON.stringify(sellerFound));
                    document.getElementById('loginView').style.display = 'none';
                    document.getElementById('mainApp').style.display = 'block';
                    
                    const sbName = document.getElementById('sidebarSellerNameDisplay');
                    if (sbName) sbName.innerText = sellerFound.nombre;
                    const dsName = document.getElementById('dashboardSellerName');
                    if (dsName) dsName.innerText = sellerFound.nombre;
                    
                    this.renderDashboard();
                    Swal.fire({ title: 'Bienvenido', text: sellerFound.nombre, icon: 'success', timer: 1500, showConfirmButton: false });
                } else {
                    const err = document.getElementById('loginError');
                    err.style.display = 'block';
                    err.innerText = "Código '" + code + "' no encontrado.";
                }
            },

            logout: function() {
                localStorage.removeItem('gc_mobile_seller');
                location.reload();
            },

            // Helper para peticiones API con manejo de sesión y errores
            apiRequest: async function(url, options = {}) {
                if (this.isOffline) throw new Error("Sin conexión a internet.");
                
                const defaults = {
                    method: 'GET',
                    headers: { 
                        'Content-Type': 'application/json',
                        'X-CSRFToken': ''
                    }
                };
                
                const finalOptions = { ...defaults, ...options };
                if (finalOptions.body && typeof finalOptions.body !== 'string') {
                    finalOptions.body = JSON.stringify(finalOptions.body);
                }

                try {
                    const res = await fetch(url, finalOptions);
                    
                    // Si Django nos redirigió al login, la sesión expiró
                    if (res.redirected && res.url.includes('/login')) {
                        Swal.fire('Sesión Expirada', 'Su sesión ha caducado. Recargando...', 'error')
                        .then(() => location.reload());
                        throw new Error("SESION_EXPIRADA");
                    }

                    if (res.status === 403) {
                        const data = await res.json().catch(() => ({}));
                        throw new Error(data.error || "Acceso Denegado (403). Verifique autorización.");
                    }

                    if (res.status >= 500) {
                        throw new Error("Error interno del servidor (500).");
                    }

                    const text = await res.text();
                    try {
                        const data = JSON.parse(text);
                        return data;
                    } catch (e) {
                        // Si no es JSON, probablemente sea una página de error HTML
                        if (text.includes('<!DOCTYPE') || text.includes('<html')) {
                             throw new Error("El servidor devolvió un error (HTML).");
                        }
                        throw new Error("Respuesta no válida.");
                    }
                } catch (e) {
                    if (e.message === "SESION_EXPIRADA") throw e;
                    console.error("API Error:", e);
                    throw e;
                }
            },

            // -- SYNC --
            syncData: async function() {
                if (this.isOffline) {
                    Swal.fire('Error', 'No hay conexión a internet', 'error');
                    return;
                }
                
                const steps = [
                    { id: 'push', label: 'Subiendo Pendientes...' },
                    { id: 'fetch', label: 'Iniciando conexión...' },
                    { id: 'categorias', label: 'Procesando Categorías...' },
                    { id: 'articulos', label: 'Procesando Artículos...' },
                    { id: 'clientes', label: 'Procesando Clientes...' },
                    { id: 'config', label: 'Ajustando Configuraciones...' },
                    { id: 'render', label: 'Finalizando Interfaz...' }
                ];

                let currentStep = 0;
                const updateProgress = (stepIndex) => {
                    const percent = Math.round((stepIndex / steps.length) * 100);
                    const label = steps[stepIndex] ? steps[stepIndex].label : 'Listo';
                    
                    if (Swal.isVisible()) {
                        const content = Swal.getHtmlContainer();
                        if (content) {
                            const bar = content.querySelector('#sync-progress-bar');
                            const text = content.querySelector('#sync-progress-text');
                            const pct = content.querySelector('#sync-progress-percent');
                            if (bar) bar.style.width = percent + '%';
                            if (text) text.innerText = label;
                            if (pct) pct.innerText = percent + '%';
                        }
                    }
                };

                Swal.fire({
                    title: 'Sincronizando Datos',
                    html: `
                        <div class="p-2">
                            <div id="sync-progress-text" class="small mb-2 text-muted">Conectando con el servidor...</div>
                            <div class="progress" style="height: 12px; border-radius: 6px; background: #eee;">
                                <div id="sync-progress-bar" class="progress-bar progress-bar-animated progress-bar-striped" 
                                     role="progressbar" style="width: 0%; background: linear-gradient(90deg, #8B7355, #A0826D);"></div>
                            </div>
                            <div id="sync-progress-percent" class="mt-2 fw-bold" style="color: #8B7355;">0%</div>
                        </div>
                    `,
                    allowOutsideClick: false,
                    showConfirmButton: false,
                    didOpen: () => {
                        updateProgress(0);
                    }
                });

                try {
                    // Step 0: Push Pending
                    updateProgress(0);
                    await this.syncAllPendingData(true);
                    
                    // Step 1: Fetch
                    currentStep++;
                    updateProgress(currentStep);
                    const response = await fetch('/ventas/movil/api/sincronizar/?vendedor_id=' + (this.seller ? this.seller.id : ''));
                    const result = await response.json();
                    
                    if (result.success) {
                        // Step 1: Categorias
                        currentStep++;
                        updateProgress(currentStep);
                        this.data.categories = result.categorias;
                        await this.clearObjectStore('categories'); // Limpiar antes de guardar
                        await this.saveDataToDB('categories', result.categorias);
                        
                        // Step 2: Articulos
                        currentStep++;
                        updateProgress(currentStep);
                        this.data.products = result.articulos;
                        await this.clearObjectStore('products'); // Limpiar antes de guardar
                        await this.saveDataToDB('products', result.articulos);
                        
                        // Step 3: Clientes
                        currentStep++;
                        updateProgress(currentStep);
                        this.data.clients = result.clientes;
                        await this.clearObjectStore('clients'); // Limpiar antes de guardar
                        await this.saveDataToDB('clients', result.clientes);
                        
                        // Step 4: Config info
                        currentStep++;
                        updateProgress(currentStep);
                        this.data.vendedores = result.vendedores;
                        this.data.formas_pago = result.formas_pago;
                        this.data.configuracion = result.configuracion || this.data.configuracion;
                        localStorage.setItem('gc_vendedores', JSON.stringify(result.vendedores));
                        localStorage.setItem('gc_formas_pago', JSON.stringify(result.formas_pago));
                        localStorage.setItem('gc_mobile_config', JSON.stringify(this.data.configuracion));
                        localStorage.setItem('gc_last_sync_ts', String(Date.now()));

                        // Step 5: Render
                        currentStep++;
                        updateProgress(currentStep);
                        this.renderCategories();
                        this.renderProducts();
                        this.renderClients();
                        this.updateDebugCounters();
                        await this.renderDashboard();
                        this.updateStockPolicyHint();
                        
                        // Final step
                        updateProgress(steps.length);
                        setTimeout(() => {
                            Swal.fire({ 
                                title: '¡Éxito!', 
                                text: 'Sincronización completada correctamente', 
                                icon: 'success', 
                                timer: 1500, 
                                showConfirmButton: false 
                            });
                        }, 500);
                    } else {
                        throw new Error(result.error || 'Error desconocido');
                    }
                } catch (err) {
                    console.error(err);
                    Swal.fire('Error', 'Sincronización fallida: ' + err.message, 'error');
                }
            },

            loadLocalData: async function() {
                this.data.products = await this.loadFromDB('products');
                this.data.categories = await this.loadFromDB('categories');
                this.data.clients = await this.loadFromDB('clients');
                this.data.pendingClients = await this.loadFromDB('pendingClients');
                this.data.vendedores = JSON.parse(localStorage.getItem('gc_vendedores') || '[]');
                this.data.formas_pago = JSON.parse(localStorage.getItem('gc_formas_pago') || '[]');
                this.data.configuracion = JSON.parse(localStorage.getItem('gc_mobile_config') || '{"permite_sin_stock": true, "intervalo_sync_minutos": 5}');
                this.filteredProducts = this.data.products.slice();
            },

            scheduleBackgroundSync: function() {
                if (this.syncTimer) clearInterval(this.syncTimer);
                const minutes = Math.max(parseInt(this.data.configuracion?.intervalo_sync_minutos || 5, 10), 2);
                this.syncTimer = setInterval(() => this.maybeSyncInBackground(), minutes * 60 * 1000);
                document.addEventListener('visibilitychange', () => {
                    if (!document.hidden) this.maybeSyncInBackground();
                });
            },

            maybeSyncInBackground: async function(force = false) {
                if (this.isOffline || !this.seller || !this.isAuthorized) return;
                const lastSync = parseInt(localStorage.getItem('gc_last_sync_ts') || '0', 10);
                const intervalMs = Math.max(parseInt(this.data.configuracion?.intervalo_sync_minutos || 5, 10), 2) * 60 * 1000;
                if (!force && Date.now() - lastSync < intervalMs) return;

                try {
                    const result = await this.apiRequest('/ventas/movil/api/sincronizar/?vendedor_id=' + (this.seller ? this.seller.id : ''));
                    if (!result.success) return;
                    this.data.categories = result.categorias || [];
                    this.data.products = result.articulos || [];
                    this.data.clients = result.clientes || [];
                    this.data.vendedores = result.vendedores || [];
                    this.data.formas_pago = result.formas_pago || [];
                    this.data.configuracion = result.configuracion || this.data.configuracion;
                    await this.clearObjectStore('categories');
                    await this.clearObjectStore('products');
                    await this.clearObjectStore('clients');
                    await this.saveDataToDB('categories', this.data.categories);
                    await this.saveDataToDB('products', this.data.products);
                    await this.saveDataToDB('clients', this.data.clients);
                    localStorage.setItem('gc_vendedores', JSON.stringify(this.data.vendedores));
                    localStorage.setItem('gc_formas_pago', JSON.stringify(this.data.formas_pago));
                    localStorage.setItem('gc_mobile_config', JSON.stringify(this.data.configuracion));
                    localStorage.setItem('gc_last_sync_ts', String(Date.now()));
                    this.renderCategories();
                    this.renderProducts();
                    this.renderClients();
                    await this.renderDashboard();
                    this.updateStockPolicyHint();
                } catch (err) {
                    console.warn('Sync liviana omitida:', err.message);
                }
            },

            // -- UI RENDERING --
            toggleSidebar: function() {
                const sb = document.getElementById('sidebar');
                const ov = document.getElementById('sidebarOverlay');
                if (sb) sb.classList.toggle('active');
                if (ov) ov.classList.toggle('active');
            },

            checkDevice: async function(manual = false) {
                if (!this.deviceId) {
                    this.deviceId = 'DEV-' + Math.random().toString(36).substring(2, 7).toUpperCase() + '-' + Date.now().toString(36).slice(-4).toUpperCase();
                    localStorage.setItem('gc_deviceId', this.deviceId);
                }
                
                const dispId = document.getElementById('displayDeviceId');
                if (dispId) dispId.innerText = this.deviceId;
                const statusEl = document.getElementById('deviceRegisterStatus');
                if (statusEl) statusEl.innerText = 'Registrando dispositivo en el servidor...';

                if (manual) {
                    Swal.fire({ title: 'Verificando con el servidor...', didOpen: () => Swal.showLoading() });
                }

                // Siempre verificar con el servidor si hay conexión para detectar revocaciones
                if (!this.isOffline) {
                    try {
                        let detailedModel = navigator.userAgent;
                        if (navigator.userAgentData) {
                            try {
                                const highEntropyData = await navigator.userAgentData.getHighEntropyValues(['model', 'platformVersion']);
                                detailedModel = `${navigator.userAgentData.platform} ${highEntropyData.model} (v${highEntropyData.platformVersion})`;
                            } catch(e) {}
                        }

                        const res = await fetch('/ventas/movil/api/verificar-dispositivo/', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': '' },
                            body: JSON.stringify({ deviceId: this.deviceId, modelo: detailedModel })
                        });
                        const data = await res.json();
                        if (!data.success) throw new Error(data.error || 'No se pudo registrar el dispositivo.');
                        
                        this.isAuthorized = !!data.authorized;
                        localStorage.setItem('gc_isAuthorized', this.isAuthorized ? 'true' : 'false');
                        if (statusEl) {
                            statusEl.innerText = this.isAuthorized
                                ? 'Dispositivo autorizado. Si no entra, verifique que tenga vendedor asignado.'
                                : 'Dispositivo registrado. Autoricelo y asigne vendedor en Gestion Ventas Moviles.';
                        }

                        // Auto-login si el dispositivo tiene un vendedor asignado y no hay sesión activa
                        if (this.isAuthorized && data.vendedor && !this.seller) {
                            console.log("Auto-login detectado para:", data.vendedor.nombre);
                            this.seller = data.vendedor;
                            localStorage.setItem('gc_mobile_seller', JSON.stringify(data.vendedor));
                            
                            // Asegurarse de que el vendedor esté en la lista local por si acaso
                            if (!this.data.vendedores.find(v => v.id === data.vendedor.id)) {
                                this.data.vendedores.push(data.vendedor);
                                localStorage.setItem('gc_vendedores', JSON.stringify(this.data.vendedores));
                            }

                            document.getElementById('loginView').style.display = 'none';
                            const mainApp = document.getElementById('mainApp');
                            if (mainApp) mainApp.style.display = 'block';
                            
                            const sbName = document.getElementById('sidebarSellerNameDisplay');
                            if (sbName) sbName.innerText = data.vendedor.nombre;
                            const dsName = document.getElementById('dashboardSellerName');
                            if (dsName) dsName.innerText = data.vendedor.nombre;
                        }

                        if (manual) {
                            if (this.isAuthorized) {
                                Swal.fire('¡Autorizado!', 'El equipo está validado.', 'success').then(() => this.showView('viewDashboard'));
                            } else {
                                Swal.fire('No Autorizado', 'El administrador aún no autoriza este equipo o ha sido revocado.', 'warning');
                            }
                        }
                    } catch (e) {
                         console.error("Error verificando dispositivo", e);
                         if (statusEl) statusEl.innerText = 'No se pudo registrar en el servidor. Revise conexion, sesion y recargue.';
                    }
                }

                if (!this.isAuthorized) {
                    const loginView = document.getElementById('loginView');
                    const mainApp = document.getElementById('mainApp');
                    if (loginView) loginView.style.display = 'none';
                    if (mainApp) mainApp.style.display = 'block';
                    this.showView('viewNoAuth');
                }
            },

            showView: function(viewId, el) {
                // Ocultar todas las vistas
                document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
                
                // Mostrar vista seleccionada
                const targetView = document.getElementById(viewId);
                if (targetView) {
                    targetView.classList.add('active');
                    // Scroll to top
                    const container = document.querySelector('.app-container');
                    if (container) container.scrollTop = 0;
                }
                
                // Actualizar navegación inferior
                document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
                
                // Si viene de la navegación inferior, marcar como activo
                if (el && el.classList.contains('nav-item')) {
                    el.classList.add('active');
                } else {
                    // Si no viene de el, intentar encontrar el nav-item correspondiente
                    const navItems = document.querySelectorAll('.nav-item');
                    if (navItems.length >= 4) {
                        if (viewId === 'viewDashboard') navItems[0].classList.add('active');
                        if (viewId === 'viewProducts') navItems[1].classList.add('active');
                        if (viewId === 'viewCart') navItems[2].classList.add('active');
                        if (viewId === 'viewLocation') navItems[3].classList.add('active');
                    }
                }

                // Render logic por vista
                if (viewId === 'viewProducts') this.renderProducts();
                if (viewId === 'viewCart') this.renderCart();
                if (viewId === 'viewHistory') this.renderPendingData();
                if (viewId === 'viewDashboard') this.renderDashboard();
                if (viewId === 'viewClients') this.renderClientsFull();
                if (viewId === 'viewLocation') this.initLocationMap();
                if (viewId === 'viewSalesHistory') this.initSalesHistoryView();
                if (viewId === 'viewNoAuth') {
                    const dispId = document.getElementById('displayDeviceId');
                    if (dispId) dispId.innerText = this.deviceId || 'DISPOSITIVO-SIN-CODIGO';
                }
                this.forceVisualOverrides();
                setTimeout(() => this.forceVisualOverrides(), 100);

                // FAB Visibility: Mostrar siempre excepto en vistas de formulario o mapa
                const fab = document.getElementById('fabBtn');
                if (fab) {
                    if (['viewCart', 'viewNewClient', 'viewLocation', 'viewHistory', 'viewClients', 'viewProducts'].includes(viewId)) {
                        fab.style.display = 'none';
                    } else {
                        fab.style.display = 'flex';
                    }
                }

                // Show/Hide Back Button in Header
                const backBtn = document.getElementById('headerBackBtn');
                if (backBtn) {
                    backBtn.style.display = (viewId === 'viewDashboard') ? 'none' : 'block';
                }
            },

            // -- MAP / LOCATION LOGIC --
            initLocationMap: function() {
                if (!this.map) {
                    this.map = L.map('map').setView([-33.4489, -70.6693], 13);
                    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                        attribution: '© OpenStreetMap'
                    }).addTo(this.map);
                } else {
                    setTimeout(() => this.map.invalidateSize(), 200);
                }
                this.getCurrentLocation();
            },

            getCurrentLocation: function() {
                const status = document.getElementById('locationStatus');
                const btn = document.getElementById('btnConfirmarUbicacion');
                
                if (!navigator.geolocation) {
                    status.innerHTML = '<i class="fas fa-exclamation-triangle me-2"></i> GPS no soportado';
                    return;
                }

                status.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i> Obteniendo su posición actual...';
                
                navigator.geolocation.getCurrentPosition(
                    (pos) => {
                        const lat = pos.coords.latitude;
                        const lng = pos.coords.longitude;
                        this.currentCoords = { lat, lng };
                        
                        this.map.setView([lat, lng], 16);
                        if (this.marker) {
                            this.marker.setLatLng([lat, lng]);
                        } else {
                            this.marker = L.marker([lat, lng]).addTo(this.map);
                        }
                        
                        status.className = 'alert alert-success small py-2';
                        status.innerHTML = `<i class="fas fa-check-circle me-2"></i> Ubicación fija: ${lat.toFixed(6)}, ${lng.toFixed(6)}`;
                        btn.disabled = false;
                    },
                    (err) => {
                        status.className = 'alert alert-danger small py-2';
                        status.innerHTML = '<i class="fas fa-times-circle me-2"></i> Error al obtener GPS. Active los permisos.';
                        btn.disabled = true;
                    },
                    { enableHighAccuracy: true, timeout: 10000 }
                );
            },

            confirmLocation: async function() {
                if (!this.currentCoords || !this.seller) return;
                
                try {
                    Swal.fire({ title: 'Enviando...', didOpen: () => Swal.showLoading() });
                    const res = await fetch('/ventas/movil/api/registrar-ubicacion/', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': '' },
                        body: JSON.stringify({
                            vendedor_id: this.seller.id,
                            lat: this.currentCoords.lat,
                            lng: this.currentCoords.lng
                        })
                    });
                    const data = await res.json();
                    if (data.success) {
                        Swal.fire('Ubicación Registrada', 'Su posición ha sido guardada.', 'success');
                        this.showView('viewDashboard');
                    } else throw new Error(data.error);
                } catch (e) {
                    Swal.fire('Error', 'No hay conexión o el servidor no respondió.', 'error');
                }
            },

            showSyncView: function(el) {
                this.showView('viewHistory', null);
                this.toggleSidebar();
            },

            initSalesHistoryView: function() {
                const hoy = this.getLocalDateString();
                const dInput = document.getElementById('historyDateDesde');
                const hInput = document.getElementById('historyDateHasta');
                
                if (dInput && !dInput.value) dInput.value = hoy;
                if (hInput && !hInput.value) hInput.value = hoy;
                this.loadSalesHistory();
            },

            getLocalDateString: function(dateValue = new Date()) {
                const date = new Date(dateValue);
                const year = date.getFullYear();
                const month = String(date.getMonth() + 1).padStart(2, '0');
                const day = String(date.getDate()).padStart(2, '0');
                return `${year}-${month}-${day}`;
            },

            escapeHtml: function(value) {
                return String(value ?? '').replace(/[&<>"']/g, char => ({
                    '&': '&amp;',
                    '<': '&lt;',
                    '>': '&gt;',
                    '"': '&quot;',
                    "'": '&#39;'
                }[char]));
            },

            fetchSellerHistory: async function(desde, hasta) {
                if (!this.seller) {
                    return { success: false, ventas: [] };
                }
                return await this.apiRequest(`/ventas/movil/api/historial-ventas/?vendedor_id=${this.seller.id}&fecha_inicio=${desde}&fecha_fin=${hasta}`);
            },

            loadSalesHistory: async function() {
                if (!this.seller) return;
                
                const desde = document.getElementById('historyDateDesde').value;
                const hasta = document.getElementById('historyDateHasta').value;
                const list = document.getElementById('salesHistoryList');
                
                list.innerHTML = `<div class="text-center py-4"><i class="fas fa-spinner fa-spin me-2" style="color:var(--terracota);"></i>Sincronizando...</div>`;

                try {
                    // 1. Obtener de Servidor (Historial Completo)
                    const response = await this.fetchSellerHistory(desde, hasta);
                    
                    if (response.success) {
                        this.data.fullHistory = response.ventas;
                        
                        // 2. Obtener Locales (Aún no enviadas)
                        const rawLocalSales = await this.loadFromDB('sales');
                        this.data.localHistory = (rawLocalSales || []).filter(s => String(s.vendedor_id || '') === String(this.seller.id));
                        
                        // Activar pestaña por defecto
                        if (!this.currentHistoryTab) this.currentHistoryTab = 'pendientes';
                        this.renderHistory(this.currentHistoryTab);
                    } else {
                        list.innerHTML = '<div class="alert alert-danger mx-3 small">Error de sincronización</div>';
                    }
                } catch (e) {
                    console.error("Error historial:", e);
                    list.innerHTML = '<div class="alert alert-warning mx-3 small">Sin conexión remota</div>';
                }
            },

            isCotizacionItem: function(item) {
                return !!(item && (
                    item.share?.es_cotizacion ||
                    item.tipo_doc === 'cotizacion' ||
                    item.tipo_documento === 'cotizacion'
                ));
            },

            getCotizacionItem: function(id) {
                const items = [
                    ...(this.data.fullHistory || []),
                    ...(this.data.recentHistory || []),
                    ...(this.data.localHistory || [])
                ];
                return items.find(item => String(item.id || item.localId) === String(id));
            },

            normalizeWhatsappPhone: function(phone) {
                const digits = String(phone || '').replace(/\D/g, '');
                if (!digits || digits.length < 8) return '';
                if (digits.startsWith('56')) return digits;
                if (digits.length === 9 && digits.startsWith('9')) return `56${digits}`;
                return '';
            },

            buildCotizacionSharePayload: function(item) {
                const share = item?.share || {};
                if (!share.es_cotizacion && !this.isCotizacionItem(item)) return null;

                const numero = item?.numero || item?.venta_id || 'MOVIL';
                const cliente = item?.cliente || item?.cliente_nombre || 'Cliente';
                const total = Number(item?.total || 0).toLocaleString('es-CL');
                const url = share.url || (item?.id ? `${window.location.origin}/ventas/cotizaciones/${item.id}/html/` : '');
                const subject = share.subject || `Cotizacion ${numero}`;
                const body = share.body || `Hola ${cliente},\n\nTe enviamos la cotizacion ${numero} por $${total}.\n\n${url}`;

                return {
                    url,
                    email: share.email || '',
                    telefono: share.telefono || '',
                    subject,
                    body
                };
            },

            openCotizacionSharePayload: function(share, channel) {
                if (!share) {
                    Swal.fire('Cotizacion no disponible', 'Primero sincroniza la cotizacion para obtener el enlace.', 'warning');
                    return;
                }

                if (channel === 'email') {
                    const recipient = share.email || '';
                    window.location.href = `mailto:${recipient}?subject=${encodeURIComponent(share.subject)}&body=${encodeURIComponent(share.body)}`;
                    return;
                }

                const phone = this.normalizeWhatsappPhone(share.telefono);
                const baseUrl = phone ? `https://wa.me/${phone}` : 'https://wa.me/';
                window.open(`${baseUrl}?text=${encodeURIComponent(share.body)}`, '_blank');
            },

            shareCotizacion: function(id, channel) {
                const item = this.getCotizacionItem(id);
                const share = this.buildCotizacionSharePayload(item);
                this.openCotizacionSharePayload(share, channel);
            },

            renderCotizacionShareActions: function(item) {
                if (!this.isCotizacionItem(item)) return '';
                if (!item.share?.es_cotizacion && !item.id) {
                    return `<div class="small text-muted mt-2"><i class="fas fa-cloud-upload-alt me-1"></i>Sincroniza para compartir</div>`;
                }
                const id = this.escapeHtml(item.id || item.localId);
                return `
                    <div class="d-flex gap-2 mt-2">
                        <button type="button" class="btn btn-sm btn-light flex-fill border" style="border-radius: 10px; font-size: 0.72rem;" onclick="app.shareCotizacion('${id}', 'email')">
                            <i class="fas fa-envelope me-1"></i>Correo
                        </button>
                        <button type="button" class="btn btn-sm btn-light flex-fill border" style="border-radius: 10px; font-size: 0.72rem;" onclick="app.shareCotizacion('${id}', 'whatsapp')">
                            <i class="fab fa-whatsapp me-1"></i>WhatsApp
                        </button>
                    </div>
                `;
            },

            showCotizacionShareDialog: async function(responseData, sale) {
                const item = {
                    id: responseData.venta_id,
                    numero: responseData.numero,
                    cliente: sale?.cliente_nombre,
                    total: sale?.total,
                    tipo_doc: responseData.tipo_documento || sale?.tipo_documento,
                    share: responseData.share
                };
                const share = this.buildCotizacionSharePayload(item);
                const result = await Swal.fire({
                    title: 'Cotizacion guardada',
                    text: 'Puedes enviarla ahora al cliente.',
                    icon: 'success',
                    showDenyButton: true,
                    showCancelButton: true,
                    confirmButtonText: 'Correo',
                    denyButtonText: 'WhatsApp',
                    cancelButtonText: 'Cerrar'
                });

                if (result.isConfirmed) {
                    this.openCotizacionSharePayload(share, 'email');
                } else if (result.isDenied) {
                    this.openCotizacionSharePayload(share, 'whatsapp');
                }
            },

            switchHistoryTab: function(tab) {
                this.currentHistoryTab = tab;
                const btnPend = document.getElementById('hist-pend-tab');
                const btnFact = document.getElementById('hist-fact-tab');
                if (btnPend) btnPend.classList.toggle('active', tab === 'pendientes');
                if (btnFact) btnFact.classList.toggle('active', tab === 'facturadas');
                this.renderHistory(tab);
            },

            renderHistory: function(tab) {
                const list = document.getElementById('salesHistoryList');
                if (!list) return;
                
                const remoteHistory = this.data.fullHistory || [];
                const localHistory = this.data.localHistory || [];
                
                let html = '';
                
                if (tab === 'pendientes') {
                    const pendingRemote = remoteHistory.filter(v => !v.facturado);
                    if (localHistory.length === 0 && pendingRemote.length === 0) {
                        list.innerHTML = `<div class="text-center py-5 text-muted small"><i class="fas fa-history fa-2x mb-2 opacity-25"></i><br>No hay ventas pendientes</div>`;
                        return;
                    }

                    localHistory.forEach(s => {
                        const localTipo = s.tipo_doc || s.tipo_documento || s.modo_documento || 'documento';
                        html += `
                            <div class="card p-3 border-0 shadow-sm mb-2" style="border-radius: 12px; border-left: 4px solid #E6B8A2 !important;">
                                <div class="d-flex justify-content-between align-items-center mb-1">
                                    <span class="small fw-bold text-terracota" style="font-size: 0.65rem;"><i class="fas fa-cloud-upload-alt me-1"></i>SIN ENVIAR</span>
                                    <span class="small text-muted" style="font-size: 0.65rem;">${new Date(s.fecha).toLocaleDateString()}</span>
                                </div>
                                <div class="fw-bold mb-1" style="font-size: 0.9rem;">${s.cliente_nombre || 'Sin Cliente'}</div>
                                <div class="d-flex justify-content-between align-items-center">
                                    <div class="small text-muted uppercase" style="font-size: 0.7rem;">${localTipo}</div>
                                    <div class="fw-bold text-dark">$${s.total.toLocaleString('es-CL')}</div>
                                </div>
                                ${this.renderCotizacionShareActions(s)}
                            </div>
                        `;
                    });

                    pendingRemote.forEach(v => {
                        const date = new Date(v.fecha);
                        const esCotizacion = this.isCotizacionItem(v);
                        html += `
                            <div class="card p-3 border-0 shadow-sm mb-2" style="border-radius: 12px; border-left: 4px solid var(--terracota) !important;">
                                <div class="d-flex justify-content-between align-items-center mb-1">
                                    <span class="small fw-bold text-muted" style="font-size: 0.65rem;">#${v.numero}</span>
                                    <span class="small text-muted" style="font-size: 0.65rem;">${date.toLocaleDateString()}</span>
                                </div>
                                <div class="fw-bold mb-1" style="font-size: 0.9rem;">${v.cliente}</div>
                                <div class="d-flex justify-content-between align-items-center">
                                    <div class="small text-muted uppercase" style="font-size: 0.7rem;">
                                        <i class="fas ${esCotizacion ? 'fa-file-signature' : 'fa-spinner fa-spin'} me-1"></i>${esCotizacion ? 'COTIZACION' : 'PENDIENTE CAJA'}
                                    </div>
                                    <div class="fw-bold text-dark">$${v.total.toLocaleString('es-CL')}</div>
                                </div>
                                ${this.renderCotizacionShareActions(v)}
                            </div>
                        `;
                    });
                } else {
                    const facturadas = remoteHistory.filter(v => v.facturado);
                    if (facturadas.length === 0) {
                        list.innerHTML = `<div class="text-center py-5 text-muted small"><i class="fas fa-check-double fa-2x mb-2 opacity-25"></i><br>No hay ventas facturadas</div>`;
                        return;
                    }

                    facturadas.forEach(v => {
                        const date = new Date(v.fecha);
                        html += `
                            <div class="card p-3 border-0 shadow-sm mb-2" style="border-radius: 12px; background: #fafdfc;">
                                <div class="d-flex justify-content-between align-items-center mb-1">
                                    <span class="small fw-bold text-muted" style="font-size: 0.65rem;">#${v.numero}</span>
                                    <span class="badge bg-teal text-white py-1 px-2" style="font-size: 0.55rem; border-radius: 4px; letter-spacing: 0.5px;">FACTURADO</span>
                                </div>
                                <div class="fw-bold mb-1" style="font-size: 0.9rem; color: #004d4d;">${v.cliente}</div>
                                <div class="d-flex justify-content-between align-items-center mb-2">
                                    <div class="small text-muted" style="font-size: 0.7rem;">${date.toLocaleDateString()}</div>
                                    <div class="fw-bold" style="color: #008080;">$${v.total.toLocaleString('es-CL')}</div>
                                </div>
                                <div class="p-2 rounded-2 bg-white small" style="font-size: 0.65rem; border: 1px dashed #b2d8d8; color: #004d4d;">
                                    <i class="fas fa-receipt me-1 text-teal"></i><b>${v.doc_final}</b>
                                </div>
                                ${this.renderCotizacionShareActions(v)}
                            </div>
                        `;
                    });
                }
                list.innerHTML = html;
            },

            renderDashboard: async function() {
                const today = this.getLocalDateString();
                const desdeRecientesDate = new Date();
                desdeRecientesDate.setDate(desdeRecientesDate.getDate() - 30);
                const desdeRecientes = this.getLocalDateString(desdeRecientesDate);
                const localSales = await this.loadFromDB('sales');
                const todayLocalSales = (localSales || [])
                    .filter(s => String(s.vendedor_id || '') === String(this.seller ? this.seller.id : ''))
                    .filter(s => this.getLocalDateString(s.fecha) >= desdeRecientes && this.getLocalDateString(s.fecha) <= today)
                    .map(s => ({
                        localId: s.localId,
                        fecha: s.fecha,
                        cliente: s.cliente_nombre || 'Sin cliente',
                        cliente_nombre: s.cliente_nombre,
                        total: Number(s.total || 0),
                        facturado: false,
                        tipo_doc: s.tipo_doc || s.tipo_documento || s.modo_documento,
                        doc_final: null,
                        status_label: (s.tipo_documento === 'cotizacion' || s.modo_documento === 'cotizacion') ? 'Cotizacion sin enviar' : 'Sin Enviar',
                        status_color: '#C9892F',
                        source: 'local'
                    }));

                let todayRemoteSales = [];
                if (!this.isOffline && this.seller) {
                    try {
                        const response = await this.fetchSellerHistory(desdeRecientes, today);
                        if (response.success) {
                            this.data.recentHistory = response.ventas || [];
                            todayRemoteSales = (response.ventas || []).map(v => {
                                const esCotizacion = this.isCotizacionItem(v);
                                return {
                                    id: v.id,
                                    fecha: v.fecha,
                                    cliente: v.cliente || 'Sin cliente',
                                    total: Number(v.total || 0),
                                    facturado: !!v.facturado,
                                    tipo_doc: v.tipo_doc,
                                    share: v.share,
                                    doc_final: v.doc_final,
                                    status_label: esCotizacion ? 'Cotizacion' : (v.facturado ? 'Facturado' : 'Pendiente Caja'),
                                    status_color: esCotizacion ? '#8B7355' : (v.facturado ? '#6D8B74' : '#A75D5D'),
                                    source: 'remote'
                                };
                            });
                        }
                    } catch (err) {
                        console.warn('No se pudo cargar operaciones recientes desde servidor:', err.message);
                    }
                }

                const todaySales = [...todayLocalSales, ...todayRemoteSales]
                    .sort((a, b) => new Date(b.fecha) - new Date(a.fecha))
                    .slice(0, 5);
                const total = todaySales.reduce((sum, s) => sum + (s.total || 0), 0);
                
                const cDisp = document.getElementById('statsSalesCount');
                const tDisp = document.getElementById('statsSalesTotal');
                if (cDisp) cDisp.innerText = todaySales.length;
                if (tDisp) tDisp.innerText = `$${total.toLocaleString('es-CL')}`;
                
                const list = document.getElementById('recentSalesList');
                if (list) {
                    if (todaySales.length > 0) {
                        let html = '<div class="list-group list-group-flush">';
                        todaySales.forEach(s => {
                            html += `
                                <div class="list-group-item bg-transparent border-0 px-2 py-2">
                                    <div class="d-flex justify-content-between align-items-start gap-2">
                                        <div class="d-flex flex-column" style="min-width:0;">
                                            <span class="small text-muted">${new Date(s.fecha).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
                                            <span class="small fw-bold text-truncate">${s.cliente}</span>
                                            <span class="small mt-1" style="color:${s.status_color}; font-weight:700;">${s.status_label}</span>
                                            ${s.doc_final ? `<span class="small text-muted">${s.doc_final}</span>` : ''}
                                        </div>
                                        <span class="fw-bold">$${s.total.toLocaleString('es-CL')}</span>
                                    </div>
                                    ${this.renderCotizacionShareActions(s)}
                                </div>
                            `;
                        });
                        html += '</div>';
                        list.innerHTML = html;
                        list.classList.remove('text-center', 'py-4');
                    } else {
                        list.innerHTML = 'No se registran operaciones recientes';
                        list.classList.add('text-center', 'py-4');
                    }
                }
            },

            updateStockPolicyHint: function() {
                const hint = document.getElementById('stockPolicyHint');
                if (!hint) return;
                hint.innerHTML = this.data.configuracion?.permite_sin_stock
                    ? '<span style="color:#7f8791;"><i class="fas fa-box-open me-1"></i>La app móvil permite vender sin stock y sincroniza inventario cada pocos minutos.</span>'
                    : '<span style="color:#7f8791;"><i class="fas fa-shield-alt me-1"></i>La app móvil bloquea artículos sin stock disponible al sincronizar y al guardar.</span>';
                this.forceVisualOverrides();
            },

            canSellProduct: function(product) {
                const stock = Number(product.stock || 0);
                if (!product.control_stock) return true;
                if (this.data.configuracion?.permite_sin_stock) return true;
                return stock > 0;
            },

            getFilteredProducts: function() {
                const query = (this.currentProductQuery || '').toLowerCase();
                return this.data.products.filter(product => {
                    const matchesCategory = this.activeCategoryId === null || product.categoria_id === this.activeCategoryId;
                    const matchesQuery = !query ||
                        product.nombre.toLowerCase().includes(query) ||
                        (product.codigo && product.codigo.toLowerCase().includes(query)) ||
                        (product.codigo_barras && product.codigo_barras.toLowerCase().includes(query));
                    return matchesCategory && matchesQuery;
                });
            },

            renderCategories: function() {
                const container = document.getElementById('categoriesList');
                if (!container) return;
                let html = `<button class="category-pill active" onclick="app.filterByCategory(null, this)">Todos</button>`;
                this.data.categories.forEach(cat => {
                    html += `<button class="category-pill" onclick="app.filterByCategory(${cat.id}, this)">${cat.nombre}</button>`;
                });
                container.innerHTML = html;
            },

            renderProducts: function(productsToRender) {
                const container = document.getElementById('productsList');
                if (!container) return;
                const list = productsToRender || this.getFilteredProducts();
                this.filteredProducts = list;
                const counter = document.getElementById('productCounterLabel');
                if (counter) counter.innerText = `${list.length} productos visibles`;
                if (!list || list.length === 0) {
                    container.innerHTML = '<div class="text-center py-5 text-muted col-12">No se encontraron productos.</div>';
                    this.updateSelectionBar();
                    return;
                }
                let html = '';
                list.slice(0, 120).forEach(prod => {
                    const selected = !!this.selectedProducts[prod.id];
                    const stock = Number(prod.stock || 0);
                    const canSell = this.canSellProduct(prod);
                    const category = this.data.categories.find(cat => cat.id === prod.categoria_id);
                    html += `
                        <div class="product-card compact ${selected ? 'selected' : ''} ${canSell ? '' : 'no-stock'}" onclick="app.toggleProductSelection(${prod.id})">
                            <div class="product-info">
                                <div class="d-flex align-items-start justify-content-between gap-2">
                                    <div class="product-name fw-bold" style="color: var(--secondary); font-size: 0.82rem; line-height: 1.15;">${prod.nombre}</div>
                                    <div class="fw-bold" style="color: var(--primary); font-size: 0.9rem; white-space: nowrap;">$${(prod.precio || 0).toLocaleString('es-CL')}</div>
                                </div>
                                <div class="text-muted mt-1" style="font-size: 0.66rem; line-height: 1.1;"><i class="fas fa-barcode me-1 opacity-50"></i>${prod.codigo || prod.codigo_barras || 'S/C'}</div>
                                <div class="product-meta">
                                    <span class="product-chip">${category ? category.nombre : 'General'}</span>
                                    <span class="product-chip ${canSell ? '' : 'out'}">${prod.control_stock ? `Stock ${stock}` : 'Sin control stock'}</span>
                                </div>
                            </div>
                            <div class="product-select-box"><i class="fas fa-check"></i></div>
                        </div>
                    `;
                });
                container.innerHTML = html;
                this.updateSelectionBar();
            },

            renderClients: function() {
                const select = document.getElementById('clientSelect');
                if (!select) return;
                const currentValue = this.selectedClientValue || select.value || '';
                const query = (this.currentClientQuery || '').trim().toLowerCase();
                let html = '<option value="">Cliente Ocasional</option>';

                const filteredClients = this.data.clients.filter(c => {
                    if (!query) return true;
                    return (c.nombre || '').toLowerCase().includes(query) || ((c.rut || '').toLowerCase().includes(query));
                });
                const filteredPendingClients = this.data.pendingClients.filter(c => {
                    if (!query) return true;
                    return (c.nombre || '').toLowerCase().includes(query) || ((c.rut || '').toLowerCase().includes(query));
                });

                filteredClients.forEach(c => {
                    html += `<option value="${c.id}" data-rut="${c.rut || ''}">${c.nombre}</option>`;
                });

                filteredPendingClients.forEach(c => {
                    html += `<option value="PENDING_${c.localId}" data-rut="${c.rut || ''}" style="color: #6D8B74;">[PENDIENTE] ${c.nombre}</option>`;
                });

                if (filteredClients.length === 0 && filteredPendingClients.length === 0) {
                    html += '<option value="" disabled>Sin clientes disponibles</option>';
                }

                select.innerHTML = html;
                if ([...select.options].some(opt => opt.value === currentValue)) {
                    select.value = currentValue;
                } else {
                    select.value = '';
                }
                this.selectedClientValue = select.value || '';
            },

            handleClientSelection: function(value) {
                this.selectedClientValue = value || '';
                this.toggleOccasionalClientName();
            },

            filterCartClients: function() {
                const input = document.getElementById('clientPickerSearch');
                this.currentClientQuery = input ? input.value || '' : '';
                this.renderClients();
                this.toggleOccasionalClientName();
            },

            filterProducts: function() {
                this.currentProductQuery = document.getElementById('productSearch').value || '';
                this.renderProducts();
            },

            filterByCategory: function(catId, btn) {
                document.querySelectorAll('.category-pill').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.activeCategoryId = catId;
                this.renderProducts();
            },

            filterClientsList: function() {
                const query = document.getElementById('clientSearch').value.toLowerCase();
                const filtered = this.data.clients.filter(c => c.nombre.toLowerCase().includes(query) || (c.rut && c.rut.includes(query)));
                this.renderClientsFull(filtered);
            },

            renderClientsFull: function(toRender) {
                const container = document.getElementById('clientsFullList');
                if (!container) return;
                
                const list = toRender || this.data.clients;
                const pendingList = toRender ? [] : this.data.pendingClients; 
                
                if ((!list || list.length === 0) && (!pendingList || pendingList.length === 0)) {
                    container.innerHTML = '<div class="alert alert-info py-4 text-center rounded-4 border-0 shadow-sm">No hay clientes para mostrar.</div>';
                    return;
                }

                let html = '<div class="list-group list-group-flush">';
                
                // Pendientes (Solo si no hay filtro masivo activo o si coincide con el RUT/Nombre)
                pendingList.forEach(c => {
                    html += `
                        <div class="list-group-item bg-white border-0 mb-2 rounded-4 shadow-sm p-3 d-flex align-items-center" onclick="Swal.fire('Cliente Pendiente', 'Este cliente aún no se ha sincronizado.', 'info')">
                            <div class="flex-shrink-0 bg-info bg-opacity-10 rounded-circle d-flex align-items-center justify-content-center me-3" style="width: 45px; height: 45px; color: var(--action-olive);">
                                <i class="fas fa-user-clock"></i>
                            </div>
                            <div class="flex-grow-1">
                                <div class="fw-bold" style="color: var(--secondary);">${c.nombre}</div>
                                <div class="small text-muted"><i class="far fa-id-card me-1"></i> ${c.rut}</div>
                                <div class="badge bg-info-subtle text-info rounded-pill mt-1" style="font-size: 0.65rem;">PENDIENTE SYNC</div>
                            </div>
                            <i class="fas fa-sync fa-spin text-info opacity-50"></i>
                        </div>
                    `;
                });

                // Reales
                list.forEach(c => {
                    html += `
                        <div class="list-group-item bg-white border-0 mb-2 rounded-4 shadow-sm p-3 d-flex align-items-center" onclick="app.showClientDetail(${c.id})">
                            <div class="flex-shrink-0 bg-light rounded-circle d-flex align-items-center justify-content-center me-3" style="width: 45px; height: 45px; color: var(--primary);">
                                <i class="fas fa-user-tie"></i>
                            </div>
                            <div class="flex-grow-1">
                                <div class="fw-bold" style="color: var(--secondary);">${c.nombre}</div>
                                <div class="small text-muted"><i class="far fa-id-card me-1"></i> ${c.rut || 'Sin RUT'}</div>
                                <div class="text-primary mt-1" style="font-size: 0.7rem;"><i class="fas fa-briefcase me-1"></i> ${c.giro || 'S/G'}</div>
                            </div>
                            <button class="btn btn-sm btn-outline-primary rounded-circle" style="width: 32px; height: 32px; padding:0;"><i class="fas fa-chevron-right"></i></button>
                        </div>
                    `;
                });
                html += '</div>';
                container.innerHTML = html;
            },

            showClientDetail: async function(clientId) {
                const client = this.data.clients.find(c => c.id === clientId);
                if (!client) return;

                this.showView('viewClientDetail');
                const container = document.getElementById('clientDetailContent');
                
                let html = `
                    <div class="card border-0 shadow-sm mb-4" style="border-radius: 20px; overflow: hidden;">
                        <div class="card-body p-4">
                            <div class="d-flex justify-content-between align-items-start mb-3">
                                <div>
                                    <h4 class="fw-bold mb-1" style="color: var(--secondary);">${client.nombre}</h4>
                                    <div class="badge bg-light text-muted border py-2 px-3 rounded-pill">${client.rut || 'Sin RUT'}</div>
                                </div>
                                <div class="bg-primary bg-opacity-10 p-3 rounded-4">
                                    <i class="fas fa-user-check text-primary fa-lg"></i>
                                </div>
                            </div>
                            
                            <hr class="my-4 opacity-25">
                            
                            <div class="mb-4">
                                <label class="small fw-bold text-muted uppercase d-block mb-1"><i class="fas fa-briefcase me-2"></i>Giro Comercial</label>
                                <div class="fw-bold text-dark">${client.giro || 'No especificado'}</div>
                            </div>
                            
                            <div class="mb-4">
                                <label class="small fw-bold text-muted uppercase d-block mb-1"><i class="fas fa-map-marker-alt me-2"></i>Dirección</label>
                                <div class="fw-bold text-dark">${client.direccion || ''}</div>
                                <div class="small text-muted mb-2">${client.comuna || ''}, ${client.ciudad || ''}</div>
                                <button class="btn btn-sm btn-terroso mt-2 rounded-pill px-4" onclick="window.open('https://www.google.com/maps/search/?api=1&query=' + encodeURIComponent('${client.direccion || ''} ${client.comuna || ''} ${client.ciudad || ''}'), '_blank')">
                                    <i class="fas fa-location-arrow me-2"></i>MOSTRAR EN MAPA
                                </button>
                            </div>
                            
                            <div class="row g-3 mb-2">
                                <div class="col-6">
                                    <label class="small fw-bold text-muted uppercase d-block mb-1"><i class="fas fa-phone me-2"></i>Teléfono</label>
                                    <a href="tel:${client.telefono}" class="fw-bold text-primary text-decoration-none">${client.telefono || 'Sin datos'}</a>
                                </div>
                                <div class="col-6">
                                    <label class="small fw-bold text-muted uppercase d-block mb-1"><i class="fas fa-envelope me-2"></i>Email</label>
                                    <div class="small fw-bold text-dark text-truncate">${client.email || 'Sin datos'}</div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <h6 class="fw-bold mb-3 uppercase small text-muted px-2"><i class="fas fa-shopping-bag me-2 text-primary"></i>Historial de Compras (Server)</h6>
                    <div id="clientPurchaseHistory" class="px-1 overflow-auto" style="max-height: 400px;">
                        <div class="text-center py-5 bg-white rounded-4 shadow-sm border-0">
                            <i class="fas fa-circle-notch fa-spin fa-2x text-primary mb-3"></i>
                            <p class="small text-muted mb-0">Consultando historial en tiempo real...</p>
                        </div>
                    </div>
                `;
                
                container.innerHTML = html;
                
                // Cargar historial desde el servidor
                try {
                    const res = await fetch('/ventas/movil/api/cliente-historial/?cliente_id=' + clientId);
                    const data = await res.json();
                    
                    const historyDiv = document.getElementById('clientPurchaseHistory');
                    if (data.success && data.historial.length > 0) {
                        let hHtml = '<div class="list-group list-group-flush shadow-sm rounded-4 overflow-hidden border-0 mb-5">';
                        data.historial.forEach(v => {
                            const total = v.total.toLocaleString('es-CL');
                            const fecha = new Date(v.fecha).toLocaleDateString('es-CL', {
                                day: '2-digit', month: 'short', year: 'numeric'
                            });
                            const statusColor = v.estado === 'confirmada' ? 'text-success' : 'text-warning';
                            
                            hHtml += `
                                <div class="list-group-item bg-white p-3 border-light">
                                    <div class="d-flex justify-content-between align-items-center">
                                        <div>
                                            <div class="small fw-bold text-primary mb-1">#${v.numero}</div>
                                            <div class="small text-muted uppercase" style="font-size: 0.65rem;">${v.tipo_doc} • ${fecha}</div>
                                        </div>
                                        <div class="text-end">
                                            <div class="fw-bold text-dark">$${total}</div>
                                            <div class="small fw-bold ${statusColor}" style="font-size: 0.65rem;">${v.estado.toUpperCase()}</div>
                                        </div>
                                    </div>
                                </div>
                            `;
                        });
                        hHtml += '</div>';
                        historyDiv.innerHTML = hHtml;
                    } else {
                        historyDiv.innerHTML = '<div class="alert bg-white shadow-sm rounded-4 py-4 text-center border-0 small text-muted">No se registran compras anteriores en el servidor.</div>';
                    }
                } catch (e) {
                    document.getElementById('clientPurchaseHistory').innerHTML = '<div class="alert alert-danger small rounded-4 mt-2">Error al conectar con el servidor para obtener el historial.</div>';
                }
            },

            saveNewClient: async function() {
                const rut = document.getElementById('nc_rut').value;
                if (!this.validateRut(rut)) {
                    Swal.fire('RUT Inválido', 'Por favor ingrese un RUT chileno válido.', 'error');
                    return;
                }

                const client = {
                    nombre: document.getElementById('nc_nombre').value,
                    rut: rut,
                    giro: document.getElementById('nc_giro').value,
                    direccion: document.getElementById('nc_direccion').value,
                    comuna: document.getElementById('nc_comuna').value,
                    ciudad: document.getElementById('nc_ciudad').value,
                    telefono: document.getElementById('nc_tel').value,
                    email: document.getElementById('nc_email').value,
                    vendedor_id: this.seller ? this.seller.id : null,
                    fecha: new Date().toISOString()
                };
                await this.saveDataToDB('pendingClients', client);
                const pendingClients = await this.loadFromDB('pendingClients');
                const savedClient = pendingClients[pendingClients.length - 1];
                Swal.fire('Cliente Guardado', 'El cliente se sincronizará pronto.', 'success');
                document.getElementById('newClientForm').reset();
                document.getElementById('rutValidationMsg').style.display = 'none';
                await this.loadLocalData();
                this.renderClients();
                if (savedClient) {
                    const clientSelect = document.getElementById('clientSelect');
                    if (clientSelect) {
                        clientSelect.value = `PENDING_${savedClient.localId}`;
                        this.selectedClientValue = clientSelect.value;
                    }
                }
                this.toggleOccasionalClientName();
                this.showView(this.returnViewAfterClient || 'viewDashboard');
            },

            // -- RUT VALIDATION & FORMATTING --
            handleRutInput: function(input) {
                let valor = input.value.replace(/[^0-9kK]/g, '');
                if (valor.length > 1) {
                    const cuerpo = valor.slice(0, -1);
                    const dv = valor.slice(-1).toUpperCase();
                    valor = cuerpo + '-' + dv;
                }
                input.value = valor;
                
                const msg = document.getElementById('rutValidationMsg');
                const btn = document.getElementById('btnSaveClient');
                if (valor.length > 7) {
                    if (this.validateRut(valor)) {
                        msg.innerText = 'RUT Válido';
                        msg.style.color = 'green';
                        msg.style.display = 'block';
                        btn.disabled = false;
                    } else {
                        msg.innerText = 'RUT Inválido';
                        msg.style.color = 'red';
                        msg.style.display = 'block';
                        btn.disabled = true;
                    }
                } else {
                    msg.style.display = 'none';
                    btn.disabled = false;
                }
            },

            validateRut: function(rutCompleto) {
                if (!/^[0-9]+-[0-9kK]{1}$/.test(rutCompleto)) return false;
                const tmp = rutCompleto.split('-');
                let digv = tmp[1];
                const rut = tmp[0];
                if (digv == 'K') digv = 'k';
                return (this.dv(rut) == digv);
            },

            dv: function(T) {
                let M = 0, S = 1;
                for (; T; T = Math.floor(T / 10))
                    S = (S + T % 10 * (9 - M++ % 6)) % 11;
                return S ? S - 1 : 'k';
            },

            showAbout: function() {
                Swal.fire({ title: 'GestionCloud Móvil', html: 'Versión 1.3<br>KreaSoft spa &copy; 2026', icon: 'info' });
                this.toggleSidebar();
            },

            showConfig: function() {
                Swal.fire({ title: 'Configuración', text: 'Próximamente disponible.', icon: 'info' });
                this.toggleSidebar();
            },

            // -- CART LOGIC --
            toggleProductSelection: function(prodId) {
                const prod = this.data.products.find(p => p.id === prodId);
                if (!prod) return;
                if (!this.canSellProduct(prod)) {
                    Swal.fire('Sin stock', 'Este artículo no puede agregarse porque el stock actual es cero.', 'warning');
                    return;
                }

                if (this.selectedProducts[prodId]) {
                    delete this.selectedProducts[prodId];
                } else {
                    this.selectedProducts[prodId] = {
                        id: prod.id,
                        nombre: prod.nombre,
                        precio: Number(prod.precio || 0),
                        cantidad: 1,
                        total: Number(prod.precio || 0)
                    };
                }
                this.renderProducts();
            },

            addSelectedProductsToCart: function() {
                const selected = Object.values(this.selectedProducts);
                if (selected.length === 0) return;

                selected.forEach(item => {
                    const existing = this.cart.find(i => i.id === item.id);
                    if (existing) {
                        existing.cantidad += item.cantidad;
                        existing.total = existing.cantidad * existing.precio;
                    } else {
                        this.cart.push({ ...item });
                    }
                });

                this.selectedProducts = {};
                this.updateCartCount();
                this.renderCart();
                this.renderProducts();
                this.showView('viewCart');
            },

            clearProductSelection: function() {
                this.selectedProducts = {};
                this.updateSelectionBar();
                this.renderProducts();
            },

            updateSelectionBar: function() {
                const selected = Object.values(this.selectedProducts);
                const bar = document.getElementById('productSelectionBar');
                const count = document.getElementById('selectedProductsCount');
                const total = document.getElementById('selectedProductsTotal');
                if (!bar || !count || !total) return;
                const estimated = selected.reduce((sum, item) => sum + (item.precio * item.cantidad), 0);
                count.innerText = `${selected.length} ${selected.length === 1 ? 'artículo' : 'artículos'}`;
                total.innerText = `Total estimado $${estimated.toLocaleString('es-CL')}`;
                bar.classList.toggle('active', selected.length > 0);
            },

            addToCart: function(prodId, cantidad = 1) {
                const prod = this.data.products.find(p => p.id === prodId);
                if (!prod) return;
                const existing = this.cart.find(i => i.id === prodId);
                if (existing) {
                    existing.cantidad += cantidad;
                    existing.total = existing.cantidad * existing.precio;
                } else {
                    this.cart.push({
                        id: prod.id,
                        nombre: prod.nombre,
                        precio: Number(prod.precio || 0),
                        cantidad: cantidad,
                        total: cantidad * Number(prod.precio || 0)
                    });
                }
                this.updateCartCount();
            },

            updateCartCount: function() {
                const count = this.cart.reduce((sum, item) => sum + item.cantidad, 0);
                const badge = document.getElementById('cartCountBadge');
                if (badge) {
                    badge.innerText = count;
                    badge.style.display = count > 0 ? 'block' : 'none';
                }
            },

            renderCart: function() {
                const container = document.getElementById('cartItems');
                if (!container) return;
                if (this.cart.length === 0) {
                    container.innerHTML = '<div class="text-center py-5 text-muted"><i class="fas fa-shopping-basket fa-3x mb-3"></i><p>Vacío</p></div>';
                    document.getElementById('cartSummary').style.display = 'none';
                    return;
                }
                let html = '';
                let total = 0;
                this.cart.forEach((item, idx) => {
                    total += item.total;
                    html += `<div class="cart-item-card">
                        <div class="cart-item-top">
                            <div class="cart-item-meta">
                                <div class="cart-item-name text-truncate">${item.nombre}</div>
                                <div class="cart-item-price">$${item.precio.toLocaleString('es-CL')} c/u</div>
                            </div>
                            <div class="cart-qty-control">
                                <button class="btn btn-sm p-0 px-2 border-0" onclick="app.updateCartQuantity(${idx}, -1)" style="color: var(--primary);"><i class="fas fa-minus" style="font-size: 0.65rem;"></i></button>
                                <span class="cart-qty-value" onclick="app.editCartQuantity(${idx})">${item.cantidad}</span>
                                <button class="btn btn-sm p-0 px-2 border-0" onclick="app.updateCartQuantity(${idx}, 1)" style="color: var(--primary);"><i class="fas fa-plus" style="font-size: 0.65rem;"></i></button>
                            </div>
                            <div class="cart-item-total">
                                $${item.total.toLocaleString('es-CL')}
                            </div>
                            <button class="btn btn-sm btn-outline-danger border-0 p-1 cart-remove-btn" onclick="app.removeFromCart(${idx})">
                                <i class="fas fa-times"></i>
                            </button>
                        </div>
                    </div>`;
                });
                container.innerHTML = html;
                const tDisp = document.getElementById('cartTotal');
                if (tDisp) tDisp.innerText = `$${total.toLocaleString('es-CL')}`;
                document.getElementById('cartSummary').style.display = 'block';

                // Inyectar clientes en el select si no están ya
                this.renderClients();
                this.toggleOccasionalClientName();
                this.toggleDocumentFlow();
                this.updateStockPolicyHint();
                this.forceVisualOverrides();
            },

            removeFromCart: function(idx) { this.cart.splice(idx, 1); this.renderCart(); this.updateCartCount(); },

            updateCartQuantity: function(idx, change) {
                const item = this.cart[idx];
                const newQty = item.cantidad + change;
                if (newQty <= 0) {
                    this.removeFromCart(idx);
                } else {
                    item.cantidad = newQty;
                    item.total = item.cantidad * item.precio;
                    this.renderCart();
                    this.updateCartCount();
                }
            },

            editCartQuantity: async function(idx) {
                const item = this.cart[idx];
                const { value: qty } = await Swal.fire({
                    title: 'Editar Cantidad',
                    text: item.nombre,
                    input: 'number',
                    inputValue: item.cantidad,
                    showCancelButton: true,
                    confirmButtonText: 'Guardar',
                    cancelButtonText: 'Cancelar',
                    confirmButtonColor: 'var(--primary)',
                    inputAttributes: {
                        min: 0,
                        step: 'any'
                    }
                });
                
                if (qty !== undefined && qty !== null) {
                    const newQty = parseFloat(qty);
                    if (newQty <= 0) {
                        this.removeFromCart(idx);
                    } else {
                        item.cantidad = newQty;
                        item.total = item.cantidad * item.precio;
                        this.renderCart();
                        this.updateCartCount();
                    }
                }
            },
            clearCart: function() {
                this.cart = [];
                this.selectedClientValue = '';
                const checkoutComment = document.getElementById('checkoutComment');
                if (checkoutComment) checkoutComment.value = '';
                this.renderCart();
                this.updateCartCount();
            },

            toggleOccasionalClientName: function() {
                const select = document.getElementById('clientSelect');
                const row = document.getElementById('occasionalClientNameRow');
                if (select && row) {
                    this.selectedClientValue = select.value || '';
                    row.style.display = select.value === "" ? "grid" : "none";
                }
            },

            toggleDocumentFlow: function() {
                const docType = document.getElementById('docTypeSelect');
                const finalRow = document.getElementById('finalDocumentRow');
                if (!docType || !finalRow) return;
                finalRow.style.display = docType.value === 'cotizacion' ? 'none' : 'grid';
            },

            openQuickClientForm: function() {
                this.returnViewAfterClient = 'viewCart';
                this.showView('viewNewClient');
            },

            checkout: async function() {
                if (this.cart.length === 0) return;
                const clientSelect = document.getElementById('clientSelect');
                if (clientSelect && this.selectedClientValue !== clientSelect.value) {
                    clientSelect.value = this.selectedClientValue || '';
                }
                let clientName = clientSelect.options[clientSelect.selectedIndex]?.text || 'Sin cliente';
                
                const cliente_id = clientSelect.value;
                const cliente_rut = clientSelect.options[clientSelect.selectedIndex]?.getAttribute('data-rut') || '';
                
                // Si es cliente ocasional, intentar usar el nombre ingresado
                if (cliente_id === "") {
                    const extraName = document.getElementById('occasionalClientName')?.value.trim();
                    if (extraName) {
                        clientName = extraName;
                    }
                }

                const modoDocumento = document.getElementById('docTypeSelect').value;
                const tipoFinal = modoDocumento === 'cotizacion'
                    ? 'cotizacion'
                    : document.getElementById('finalDocTypeSelect').value;
                const comentarioCierre = document.getElementById('checkoutComment')?.value.trim() || '';

                const sale = {
                    localId: Date.now(),
                    cliente_id: cliente_id,
                    cliente_rut: cliente_rut,
                    cliente_nombre: clientName,
                    items: this.cart.map(item => ({ ...item })),
                    total: this.cart.reduce((s, i) => s + i.total, 0),
                    fecha: new Date().toISOString(),
                    vendedor_id: this.seller ? this.seller.id : '',
                    deviceId: this.deviceId,
                    tipo_documento: tipoFinal,
                    modo_documento: modoDocumento,
                    comentario_cierre: comentarioCierre,
                    observaciones: `[MOVIL] Cliente: ${clientName}`
                };
                if (this.isOffline) {
                    await this.saveDataToDB('sales', sale);
                    Swal.fire('Guardado Offline', 'Se sincronizará al recuperar conexión.', 'info');
                    this.clearCart();
                    this.showView('viewDashboard');
                } else {
                    Swal.fire({
                        title: '¿Guardar documento?',
                        text: `${modoDocumento === 'cotizacion' ? 'Cotización' : 'Nota de venta'} por $${sale.total.toLocaleString()}`,
                        showCancelButton: true,
                        confirmButtonText: 'Sí, guardar'
                    })
                    .then(res => { if (res.isConfirmed) this.sendSaleToServer(sale); });
                }
            },

            sendSaleToServer: async function(sale) {
                try {
                    Swal.fire({ title: 'Enviando...', didOpen: () => Swal.showLoading() });
                    const data = await this.apiRequest('/ventas/movil/api/guardar-venta/', {
                        method: 'POST',
                        body: { ...sale, deviceId: this.deviceId }
                    });
                    if (data.success) {
                        if (data.share?.es_cotizacion) {
                            await this.showCotizacionShareDialog(data, sale);
                        } else {
                            await Swal.fire('Exito', 'Documento enviado correctamente.', 'success');
                        }
                        this.clearCart();
                        this.showView('viewDashboard');
                    } else throw new Error(data.error || 'Error desconocido');
                } catch (e) {
                    await this.saveDataToDB('sales', sale);
                    Swal.fire('Error', 'Venta guardada localmente.', 'warning');
                    this.clearCart();
                    this.showView('viewDashboard');
                }
            },

            renderPendingData: async function() {
                const sales = await this.loadFromDB('sales');
                const contS = document.getElementById('pendingSyncSales');
                if (contS) {
                    contS.innerHTML = sales.length === 0 ? '<div class="alert alert-light text-center small">Sin ventas pendientes</div>' : '';
                    sales.forEach(s => {
                        contS.innerHTML += `<div class="card mb-2 border-start border-4 border-warning p-2"><div class="d-flex justify-content-between align-items-center">
                            <div class="small"><div class="fw-bold">${new Date(s.fecha).toLocaleString()}</div><div>$${(s.total || 0).toLocaleString()}</div></div>
                            <button class="btn btn-sm btn-terroso shadow-sm" style="min-width: 40px; height: 40px; border-radius: 12px;" onclick="app.syncOneSale(${s.localId})"><i class="fas fa-upload"></i></button>
                        </div></div>`;
                    });
                }

                const clients = await this.loadFromDB('pendingClients');
                const contC = document.getElementById('pendingSyncClients');
                if (contC) {
                    contC.innerHTML = clients.length === 0 ? '<div class="alert alert-light text-center small">Sin clientes pendientes</div>' : '';
                    clients.forEach(c => {
                        contC.innerHTML += `<div class="card mb-2 border-start border-4 border-info p-2">
                            <div class="d-flex justify-content-between align-items-center">
                                <div class="small fw-bold">${c.nombre}<br><span class="text-muted fw-normal">${c.rut}</span></div>
                                <button class="btn btn-sm btn-info text-white shadow-sm" style="min-width: 40px; height: 40px; border-radius: 12px;" onclick="app.syncOneClient(${c.localId})"><i class="fas fa-sync"></i></button>
                            </div>
                        </div>`;
                    });
                }
            },

            syncOneSale: async function(localId, silent = false) {
                let sales = await this.loadFromDB('sales');
                let sale = sales.find(s => s.localId === localId);
                if (!sale) return { success: false, error: 'Documento no encontrado localmente.' };
                
                // --- GUARD: No subir si el cliente sigue pendiente ---
                if (sale.cliente_id && String(sale.cliente_id).startsWith('PENDING_')) {
                    return { success: false, error: 'El cliente de esta venta aún no se ha sincronizado.' };
                }

                // --- BACKFILL: Si la venta es vieja y no tiene cliente_rut, intentar buscarlo ---
                if (!sale.cliente_rut && sale.cliente_id) {
                    try {
                        if (String(sale.cliente_id).startsWith('PENDING_')) {
                            const lId = parseInt(sale.cliente_id.split('_')[1]);
                            const clients = await this.loadFromDB('pendingClients');
                            const pc = clients.find(c => c.localId === lId);
                            if (pc) sale.cliente_rut = pc.rut;
                        } else {
                            const clients = await this.loadFromDB('clients');
                            const rc = clients.find(c => String(c.id) === String(sale.cliente_id));
                            if (rc) sale.cliente_rut = rc.rut;
                        }
                    } catch (e) { console.warn("No se pudo backfillear RUT:", e); }
                }

                try {
                    if (!silent) Swal.fire({ title: 'Subiendo venta...', didOpen: () => Swal.showLoading() });
                    
                    const data = await this.apiRequest('/ventas/movil/api/guardar-venta/', {
                        method: 'POST',
                        body: { ...sale, deviceId: this.deviceId }
                    });

                    if (data.success) {
                        const tx = this.db.transaction('sales', 'readwrite');
                        tx.objectStore('sales').delete(localId);
                        await new Promise(r => tx.oncomplete = r);
                        this.renderPendingData();
                        if (!silent) {
                            if (data.share?.es_cotizacion) {
                                await this.showCotizacionShareDialog(data, sale);
                            } else {
                                await Swal.fire('Sincronizado', 'Venta subida correctamente.', 'success');
                            }
                        }
                        return { success: true, share: data.share };
                    } else throw new Error(data.error || 'Error desconocido');
                } catch (e) { 
                    if (!silent && e.message !== "SESION_EXPIRADA") {
                        Swal.fire('Fallo de Sincronización', e.message, 'error');
                    }
                    return { success: false, error: e.message };
                }
            },

            syncOneClient: async function(localId, silent = false) {
                const clients = await this.loadFromDB('pendingClients');
                const client = clients.find(c => c.localId === localId);
                if (!client) return { success: false, error: 'Cliente no encontrado localmente.' };

                try {
                    if (!silent) Swal.fire({ title: 'Subiendo cliente...', didOpen: () => Swal.showLoading() });
                    
                    const data = await this.apiRequest('/ventas/movil/api/guardar-cliente/', {
                        method: 'POST',
                        body: client
                    });

                    if (data.success) {
                        const newClientId = data.cliente_id;
                        const oldPendingId = "PENDING_" + localId;
                        
                        // Actualizar ventas pendientes que usaban este cliente temporal
                        const sales = await this.loadFromDB('sales');
                        for (const s of sales) {
                            if (s.cliente_id === oldPendingId) {
                                s.cliente_id = newClientId;
                                await this.saveDataToDB('sales', s);
                            }
                        }

                        const tx = this.db.transaction('pendingClients', 'readwrite');
                        tx.objectStore('pendingClients').delete(localId);
                        await new Promise(r => tx.oncomplete = r);
                        
                        await this.loadLocalData();
                        this.renderPendingData();
                        this.renderClients();
                        this.renderClientsFull();
                        
                        if (!silent) Swal.fire('Cliente Sincronizado', data.nombre, 'success');
                        return { success: true, newId: newClientId };
                    } else throw new Error(data.error || 'Error desconocido');
                } catch (e) { 
                    if (!silent && e.message !== "SESION_EXPIRADA") {
                        Swal.fire('Error de Cliente', e.message, 'error');
                    }
                    return { success: false, error: e.message };
                }
            },

            syncAllPendingData: async function(silent = false) {
                if (this.isOffline) {
                    if (!silent) Swal.fire('Sin conexión', 'No se pueden subir documentos sin internet.', 'warning');
                    return false;
                }

                const pendingSales = await this.loadFromDB('sales');
                const pendingClients = await this.loadFromDB('pendingClients');
                
                if (pendingSales.length === 0 && pendingClients.length === 0) {
                    if (!silent) Swal.fire('Todo al día', 'No hay documentos pendientes por subir.', 'info');
                    return true;
                }

                if (!silent) {
                    Swal.fire({
                        title: 'Sincronizando Todo',
                        html: '<div class="p-3"><div class="spinner-border text-primary mb-2"></div><p id="batch-sync-text">Subiendo clientes y ventas...</p></div>',
                        allowOutsideClick: false,
                        showConfirmButton: false,
                        didOpen: () => Swal.showLoading()
                    });
                }

                let successCount = 0;
                let errorCount = 0;
                const errors = [];

                // 1. Clientes primero
                for (const c of pendingClients) {
                    const res = await this.syncOneClient(c.localId, true);
                    if (res.success) successCount++; 
                    else {
                        errorCount++;
                        errors.push(`Cliente ${c.nombre}: ${res.error}`);
                    }
                }

                // --- CRÍTICIO: Recargar ventas después de sincronizar clientes ---
                // Porque syncOneClient actualiza los IDs de las ventas en la DB local
                const updatedPendingSales = await this.loadFromDB('sales');

                // 2. Ventas
                for (const s of updatedPendingSales) {
                    const res = await this.syncOneSale(s.localId, true);
                    if (res.success) successCount++; 
                    else {
                        errorCount++;
                        errors.push(`Venta ${new Date(s.fecha).toLocaleDateString()}: ${res.error}`);
                    }
                }

                this.renderPendingData();
                
                if (!silent) {
                    if (errorCount === 0) {
                        Swal.fire('Éxito', `Se sincronizaron ${successCount} documentos correctamente.`, 'success');
                    } else {
                        Swal.fire({
                            title: 'Sincronización Parcial',
                            html: `<p>Se subieron ${successCount} documentos, pero ${errorCount} fallaron:</p>
                                   <div class="text-start small p-2 bg-light mt-2" style="max-height: 150px; overflow-y: auto;">
                                   ${errors.map(e => `• ${e}`).join('<br>')}
                                   </div>`,
                            icon: 'warning'
                        });
                    }
                }
                return errorCount === 0;
            },

            autoSyncPending: async function() {
                const sales = await this.loadFromDB('sales');
                const clients = await this.loadFromDB('pendingClients');
                const total = sales.length + clients.length;
                
                if (total > 0) {
                    Swal.fire({
                        title: 'Documentos Pendientes',
                        text: `Tiene ${total} documentos sin sincronizar. ¿Desea subirlos ahora?`,
                        icon: 'info',
                        showConfirmButton: true,
                        confirmButtonText: 'Subir Todo',
                        confirmButtonColor: '#8D7B68',
                        showCancelButton: true,
                        cancelButtonText: 'Después',
                        cancelButtonColor: '#A8A095'
                    }).then(res => {
                        if (res.isConfirmed) this.syncAllPendingData();
                    });
                }
            }
        };

        window.app = app;

        // Iniciar app
        app.init();
    
