/**
 * Cerrar un visor de documento y volver a quien lo abrió.
 * El sistema siempre vuelve al origen exacto desde donde fue invocado.
 */
(function (global) {
    function decodeMaybe(value) {
        if (!value) return '';
        try {
            return decodeURIComponent(value);
        } catch (e) {
            return value;
        }
    }

    function normalizeReturnUrl(url) {
        if (!url || typeof url !== 'string') return null;
        var raw = decodeMaybe(url).trim();
        if (!raw) return null;
        try {
            var parsed = new URL(raw, window.location.origin);
            if (parsed.origin !== window.location.origin) return null;
            return parsed.pathname + parsed.search + parsed.hash;
        } catch (e) {
            if (raw.charAt(0) === '/' && raw.charAt(1) !== '/') return raw;
            return null;
        }
    }

    function isAuthUrl(url) {
        if (!url) return false;
        return url.indexOf('/accounts/login') >= 0 ||
               url.indexOf('/accounts/logout') >= 0 ||
               url.indexOf('/admin/login') >= 0;
    }

    function currentPath() {
        return window.location.pathname + window.location.search + window.location.hash;
    }

    function resolveReturnUrl(fallbackUrl) {
        // 1. Prioridad 1: return_url explícito en la query string de la página actual
        var params = new URLSearchParams(window.location.search);
        var fromQuery = normalizeReturnUrl(params.get('return_url'));
        if (fromQuery && !isAuthUrl(fromQuery)) return fromQuery;

        // 2. Prioridad 2: Referrer de navegación directa si es del mismo origen y no es login/logout
        var fromReferrer = normalizeReturnUrl(document.referrer);
        if (fromReferrer && fromReferrer !== currentPath() && !isAuthUrl(fromReferrer)) {
            return fromReferrer;
        }

        // 3. Prioridad 3: Fallback contextual del backend (orden despacho, transferencia, venta, etc.)
        var fallback = normalizeReturnUrl(fallbackUrl || global.GC_CERRAR_VISOR_FALLBACK);
        if (fallback && fallback !== '/' && !isAuthUrl(fallback)) {
            return fallback;
        }

        // 4. Prioridad 4: Memoria temporal de sesión (y se limpia para no contaminar)
        var stored = normalizeReturnUrl(
            sessionStorage.getItem('gc_visor_return') ||
            sessionStorage.getItem('print_referer')
        );
        try {
            sessionStorage.removeItem('gc_visor_return');
            sessionStorage.removeItem('print_referer');
            localStorage.removeItem('print_referer');
        } catch (e) {}

        if (stored && !isAuthUrl(stored)) return stored;

        return fallback || '/';
    }

    function rememberCaller() {
        try {
            localStorage.removeItem('print_referer');
        } catch (e) {}

        var params = new URLSearchParams(window.location.search);
        var fromQuery = normalizeReturnUrl(params.get('return_url'));
        if (fromQuery && !isAuthUrl(fromQuery)) {
            sessionStorage.setItem('gc_visor_return', fromQuery);
            return;
        }
        var fromReferrer = normalizeReturnUrl(document.referrer);
        if (fromReferrer && fromReferrer !== currentPath() && !isAuthUrl(fromReferrer)) {
            sessionStorage.setItem('gc_visor_return', fromReferrer);
            return;
        }
        var fallback = normalizeReturnUrl(global.GC_CERRAR_VISOR_FALLBACK);
        if (fallback && fallback !== '/' && !isAuthUrl(fallback)) {
            sessionStorage.setItem('gc_visor_return', fallback);
        }
    }

    function goTo(url) {
        var target = normalizeReturnUrl(url) || '/';
        if (target === currentPath()) target = '/';
        window.location.replace(target);
    }

    function cerrarVisor(options) {
        options = options || {};
        var fallback = options.fallbackUrl || global.GC_CERRAR_VISOR_FALLBACK || '/';
        var message = options.message || { kind: 'print_done' };

        try {
            if (global.opener && global.opener !== global && !global.opener.closed) {
                global.opener.postMessage(message, window.location.origin);
            }
        } catch (e) { /* noop */ }

        if (global.opener && global.opener !== global && !global.opener.closed) {
            try {
                global.close();
            } catch (e) { /* noop */ }
            setTimeout(function () {
                if (!global.closed) goTo(resolveReturnUrl(fallback));
            }, 150);
            return;
        }

        if (window.history.length <= 1) {
            try {
                global.close();
            } catch (e) { /* noop */ }
            setTimeout(function () {
                if (!global.closed) goTo(resolveReturnUrl(fallback));
            }, 150);
            return;
        }

        goTo(resolveReturnUrl(fallback));
    }

    rememberCaller();
    global.cerrarVisor = cerrarVisor;
    global.safeCloseWindow = function () { cerrarVisor(); };
    global.cerrarVentana = function () { cerrarVisor(); };
})(window);
