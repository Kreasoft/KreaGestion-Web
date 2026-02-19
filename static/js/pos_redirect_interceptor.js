/*
 * FIX TEMPORAL: Interceptar respuesta de pos_procesar_preventa y redirigir si hay redirect_url
 */

// Interceptar todas las promesas fetch y revisar si es la respuesta de procesar-preventa
(function() {
    const originalFetch = window.fetch;
    
    window.fetch = function(...args) {
        return originalFetch.apply(this, args)
            .then(async response => {
                // Clonar para no consumir el stream
                const clonedResponse = response.clone();
                
                // Intentar parsear JSON
                try {
                    const data = await clonedResponse.json();
                    
                    // Si la respuesta tiene redirect_url, redirigir
                    if (data && data.redirect_url && typeof window.location !== 'undefined') {
                        console.log('[INTERCEPT] Redirigiendo a:', data.redirect_url);
                        window.location.href = data.redirect_url;
                        // Retornar una promesa que nunca se resuelve para detener el flujo
                        return new Promise(() => {});
                    }
                } catch (e) {
                    // No es JSON o ya fue consumido, devolver la respuesta original
                }
                
                return response;
            });
    };
    
    console.log('[POS FIX] Interceptor de redirect_url instalado');
})();
