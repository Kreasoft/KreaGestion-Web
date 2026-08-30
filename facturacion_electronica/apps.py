from django.apps import AppConfig


class FacturacionElectronicaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'facturacion_electronica'
    verbose_name = 'Facturación Electrónica'

    def ready(self):
        try:
            from .background_sender import debe_iniciar_sender_en_proceso, get_background_sender
            if debe_iniciar_sender_en_proceso():
                get_background_sender()
        except Exception:
            pass
