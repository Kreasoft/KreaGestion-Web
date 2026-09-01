from django.apps import AppConfig


class VentasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ventas'
    
    def ready(self):
        """Importar señales cuando la app esté lista"""
        import ventas.signals
        try:
            from ventas.models import ensure_estacion_caja_impresion, ensure_terminalpos_table
            from caja.models import ensure_impresoras_agente
            ensure_terminalpos_table()
            ensure_estacion_caja_impresion()
            ensure_impresoras_agente()
        except Exception:
            pass
