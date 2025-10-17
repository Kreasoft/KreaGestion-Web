from django.core.management.base import BaseCommand
from articulos.models import HomologacionCodigo


class Command(BaseCommand):
    help = 'Verifica las homologaciones en la base de datos'

    def handle(self, *args, **options):
        self.stdout.write('=' * 60)
        self.stdout.write(self.style.SUCCESS('VERIFICANDO HOMOLOGACIONES EN LA BASE DE DATOS'))
        self.stdout.write('=' * 60)

        total = HomologacionCodigo.objects.count()
        self.stdout.write(f'\nTotal de homologaciones: {total}')

        if total > 0:
            self.stdout.write('\nLista de homologaciones:')
            self.stdout.write('-' * 60)
            for h in HomologacionCodigo.objects.select_related('articulo', 'proveedor').all():
                self.stdout.write(self.style.WARNING(f'\nID: {h.id}'))
                self.stdout.write(f'  Artículo: {h.articulo.codigo} - {h.articulo.nombre}')
                self.stdout.write(f'  Proveedor: {h.proveedor.nombre}')
                self.stdout.write(f'  Código Proveedor: {h.codigo_proveedor}')
                self.stdout.write(f'  Precio: ${h.precio_compra:,}')
                self.stdout.write(f'  Principal: {"Sí" if h.es_principal else "No"}')
                self.stdout.write(f'  Activo: {"Sí" if h.activo else "No"}')
                self.stdout.write('-' * 60)
        else:
            self.stdout.write(self.style.ERROR('\n❌ No hay homologaciones en la base de datos'))
