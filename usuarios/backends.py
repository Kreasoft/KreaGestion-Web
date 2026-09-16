from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import Permission

class StrictPermissionBackend(ModelBackend):
    """
    Backend de autenticacion que evalua permisos estrictamente segun los grupos/roles
    y permisos individuales del usuario, sin bypass automatico por ser superusuario.
    """
    def _get_user_permissions(self, user_obj):
        return user_obj.user_permissions.all()

    def _get_group_permissions(self, user_obj):
        return Permission.objects.filter(group__in=user_obj.groups.all())

    def _get_permissions(self, user_obj, obj, from_name):
        if not user_obj.is_active or user_obj.is_anonymous:
            return set()
        
        perm_cache_name = f"_{from_name}_perm_cache"
        if not hasattr(user_obj, perm_cache_name):
            if from_name == 'user':
                perms = self._get_user_permissions(user_obj)
            else:
                perms = self._get_group_permissions(user_obj)
            perms = perms.values_list('content_type__app_label', 'codename').order_by()
            setattr(user_obj, perm_cache_name, {f"{app}.{codename}" for app, codename in perms})
        return getattr(user_obj, perm_cache_name)

    def get_user_permissions(self, user_obj, obj=None):
        return self._get_permissions(user_obj, obj, 'user')

    def get_group_permissions(self, user_obj, obj=None):
        return self._get_permissions(user_obj, obj, 'group')

    def get_all_permissions(self, user_obj, obj=None):
        if not user_obj.is_active or user_obj.is_anonymous:
            return set()
        if not hasattr(user_obj, '_perm_cache'):
            user_obj._perm_cache = {
                *self.get_user_permissions(user_obj, obj=obj),
                *self.get_group_permissions(user_obj, obj=obj),
            }
        return user_obj._perm_cache

    def has_perm(self, user_obj, perm, obj=None):
        if not user_obj.is_active:
            return False
        if user_obj.is_superuser:
            return True
        return perm in self.get_all_permissions(user_obj, obj)

    def has_module_perms(self, user_obj, app_label):
        if not user_obj.is_active:
            return False
        if user_obj.is_superuser:
            return True
        return any(perm.startswith(app_label + '.') for perm in self.get_all_permissions(user_obj))
