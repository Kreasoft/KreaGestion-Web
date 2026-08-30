/**
 * Cerrar un visor de documento y volver a quien lo abrió.
 * Nunca cae al POS salvo que el llamador haya sido el POS (return_url / referrer).
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

    function currentPath() {
        return window.location.pathname + window.location.search + window.location.hash;
    }

    function resolveReturnUrl(fallbackUrl) {
        var params = new URLSearchParams(window.location.search);
        var fromQuery = normalizeReturnUrl(params.get('return_url'));
        if (fromQuery) return fromQuery;

        var stored = normalizeReturnUrl(
            sessionStorage.getItem('gc_visor_return') ||
            localStorage.getItem('print_referer') ||
            sessionStorage.getItem('print_referer')
        );
        if (stored) return stored;

        var fromReferrer = normalizeReturnUrl(document.referrer);
        if (fromReferrer && fromReferrer !== currentPath()) return fromReferrer;

        var fallback = normalizeReturnUrl(fallbackUrl);
        return fallback || '/';
    }

    function rememberCaller() {
        var params = new URLSearchParams(window.location.search);
        var fromQuery = normalizeReturnUrl(params.get('return_url'));
        if (fromQuery) {
            sessionStorage.setItem('gc_visor_return', fromQuery);
            return;
        }
        var fromReferrer = normalizeReturnUrl(document.referrer);
        if (fromReferrer && fromReferrer !== currentPath()) {
            sessionStorage.setItem('gc_visor_return', fromReferrer);
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
