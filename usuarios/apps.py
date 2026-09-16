from django.apps import AppConfig


class UsuariosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'usuarios'

    def ready(self):
        # Desactivar el bypass automatico de has_perm para superusuarios,
        # obligando a evaluar estrictamente los permisos asignados a sus roles/grupos.
        from django.contrib.auth.models import PermissionsMixin, _user_has_perm
        
        def strict_has_perm(self, perm, obj=None):
            if not self.is_active:
                return False
            if self.is_superuser:
                return True
            return _user_has_perm(self, perm, obj)
            
        PermissionsMixin.has_perm = strict_has_perm
