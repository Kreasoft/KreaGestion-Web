from django.core.management.base import BaseCommand
from articulos.models import Articulo, StockArticulo
from inventario.models import Stock


class Command(BaseCommand):
    help = 'Verifica el stock del artículo 2144'

    def handle(self, *args, **options):
        articulo_id = 2144
        
        self.stdout.write('=' * 70)
        self.stdout.write(self.style.SUCCESS(f'VERIFICANDO STOCK DEL ARTÍCULO {articulo_id}'))
        self.stdout.write('=' * 70)
        
        try:
            articulo = Articulo.objects.get(id=articulo_id)
            self.stdout.write(f'\nArtículo: {articulo.codigo} - {articulo.nombre}')
            self.stdout.write(f'Empresa: {articulo.empresa.nombre}')
            self.stdout.write(f'Control Stock: {"Sí" if articulo.control_stock else "No"}')
            
            # Verificar en StockArticulo
            self.stdout.write('\n' + '-' * 70)
            self.stdout.write(self.style.WARNING('Stock en StockArticulo:'))
            stocks_articulo = StockArticulo.objects.filter(articulo=articulo)
            self.stdout.write(f'Total registros: {stocks_articulo.count()}')
            
            if stocks_articulo.exists():
                for stock in stocks_articulo:
                    self.stdout.write(f'\n  Sucursal: {stock.sucursal.nombre}')
                    self.stdout.write(f'  Disponible: {stock.cantidad_disponible}')
                    self.stdout.write(f'  Reservada: {stock.cantidad_reservada}')
                    self.stdout.write(f'  Total: {stock.cantidad_total}')
            else:
                self.stdout.write(self.style.ERROR('  ❌ No hay registros en StockArticulo'))
            
            # Verificar en Stock (inventario)
            self.stdout.write('\n' + '-' * 70)
            self.stdout.write(self.style.WARNING('Stock en Inventario (Stock):'))
            stocks_inventario = Stock.objects.filter(articulo=articulo)
            self.stdout.write(f'Total registros: {stocks_inventario.count()}')
            
            if stocks_inventario.exists():
                for stock in stocks_inventario:
                    self.stdout.write(f'\n  Bodega: {stock.bodega.nombre}')
                    self.stdout.write(f'  Cantidad: {stock.cantidad}')
                    self.stdout.write(f'  Última actualización: {stock.fecha_actualizacion}')
            else:
                self.stdout.write(self.style.ERROR('  ❌ No hay registros en Stock (inventario)'))
                
        except Articulo.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'\n❌ Artículo {articulo_id} no existe'))
