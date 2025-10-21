from django.core.management.base import BaseCommand
from empresas.models import Empresa


class Command(BaseCommand):
    help = 'Cambiar la empresa activa en la sesión del usuario'

    def add_arguments(self, parser):
        parser.add_argument('empresa_id', type=int, help='ID de la empresa a activar')

    def handle(self, *args, **options):
        empresa_id = options['empresa_id']
        
        try:
            empresa = Empresa.objects.get(id=empresa_id)
            self.stdout.write(
                self.style.SUCCESS(f'Empresa activada: {empresa.nombre} (ID: {empresa.id})')
            )
            self.stdout.write(
                f'Para usar esta empresa en el POS, asegúrate de que la sesión tenga empresa_activa_id = {empresa_id}'
            )
            
            # Mostrar artículos de esta empresa
            from articulos.models import Articulo
            articulos = Articulo.objects.filter(empresa=empresa, activo=True)
            self.stdout.write(f'\nArtículos en {empresa.nombre}:')
            for a in articulos:
                self.stdout.write(f'  ID: {a.id}, Nombre: {a.nombre}, Stock: {a.stock_actual}')
                
        except Empresa.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Empresa con ID {empresa_id} no encontrada')
            )












