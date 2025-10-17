from django.core.management.base import BaseCommand
from articulos.models import HomologacionCodigo, Articulo


class Command(BaseCommand):
    help = 'Verifica las homologaciones con empresa y sucursal'

    def handle(self, *args, **options):
        self.stdout.write('=' * 70)
        self.stdout.write(self.style.SUCCESS('VERIFICANDO HOMOLOGACIONES CON EMPRESA'))
        self.stdout.write('=' * 70)

        total = HomologacionCodigo.objects.count()
        self.stdout.write(f'\nTotal de homologaciones: {total}')

        if total > 0:
            self.stdout.write('\nDetalles completos:')
            self.stdout.write('-' * 70)
            for h in HomologacionCodigo.objects.select_related('articulo', 'articulo__empresa', 'proveedor', 'proveedor__empresa').all():
                self.stdout.write(self.style.WARNING(f'\nID Homologación: {h.id}'))
                self.stdout.write(f'  Artículo ID: {h.articulo.id}')
                self.stdout.write(f'  Artículo Código: {h.articulo.codigo}')
                self.stdout.write(f'  Artículo Nombre: {h.articulo.nombre}')
                self.stdout.write(f'  Artículo Empresa: {h.articulo.empresa.nombre if h.articulo.empresa else "Sin empresa"}')
                self.stdout.write(f'  Proveedor: {h.proveedor.nombre}')
                self.stdout.write(f'  Proveedor Empresa: {h.proveedor.empresa.nombre if h.proveedor.empresa else "Sin empresa"}')
                self.stdout.write(f'  Código Proveedor: {h.codigo_proveedor}')
                self.stdout.write(f'  Precio: ${h.precio_compra:,}')
                self.stdout.write(f'  Principal: {"Sí" if h.es_principal else "No"}')
                self.stdout.write(f'  Activo: {"Sí" if h.activo else "No"}')
                self.stdout.write('-' * 70)
        else:
            self.stdout.write(self.style.ERROR('\n❌ No hay homologaciones'))

        # Verificar también el artículo 2144
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('VERIFICANDO ARTÍCULO 2144'))
        self.stdout.write('=' * 70)
        
        try:
            articulo = Articulo.objects.get(id=2144)
            self.stdout.write(f'\nArtículo encontrado:')
            self.stdout.write(f'  ID: {articulo.id}')
            self.stdout.write(f'  Código: {articulo.codigo}')
            self.stdout.write(f'  Nombre: {articulo.nombre}')
            self.stdout.write(f'  Empresa: {articulo.empresa.nombre if articulo.empresa else "Sin empresa"}')
            
            # Verificar homologaciones de este artículo
            homos = HomologacionCodigo.objects.filter(articulo=articulo)
            self.stdout.write(f'\nHomologaciones de este artículo: {homos.count()}')
            for h in homos:
                self.stdout.write(f'  - {h.proveedor.nombre}: {h.codigo_proveedor}')
        except Articulo.DoesNotExist:
            self.stdout.write(self.style.ERROR('\n❌ Artículo 2144 no existe'))
