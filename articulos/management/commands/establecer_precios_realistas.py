from django.core.management.base import BaseCommand
from articulos.models import Articulo
from decimal import Decimal

class Command(BaseCommand):
    help = 'Establece precios realistas basados en el tipo de producto'

    def handle(self, *args, **options):
        self.stdout.write('Estableciendo precios realistas...')
        
        # Definir precios realistas por tipo de producto
        precios_realistas = {
            'AGU001': {'costo': 400, 'venta': 800, 'final': 952, 'margen': 100},
            'ROP001': {'costo': 15000, 'venta': 25000, 'final': 29750, 'margen': 66.67},
            'CER001': {'costo': 1200, 'venta': 2000, 'final': 2380, 'margen': 66.67},
            'TAB001': {'costo': 3000, 'venta': 5000, 'final': 5950, 'margen': 66.67},
            'GAS001': {'costo': 800, 'venta': 1500, 'final': 1785, 'margen': 87.5},
            'JUG001': {'costo': 1200, 'venta': 2000, 'final': 2380, 'margen': 66.67},
            'LIB001': {'costo': 18000, 'venta': 30000, 'final': 35700, 'margen': 66.67},
            'DEP001': {'costo': 25000, 'venta': 40000, 'final': 47600, 'margen': 60},
            'ENE001': {'costo': 1500, 'venta': 2500, 'final': 2975, 'margen': 66.67},
            'HOG001': {'costo': 120000, 'venta': 200000, 'final': 238000, 'margen': 66.67},
            'ELE001': {'costo': 450000, 'venta': 600000, 'final': 714000, 'margen': 33.33},
            'VIN001': {'costo': 8000, 'venta': 15000, 'final': 17850, 'margen': 87.5},
            'LIC001': {'costo': 25000, 'venta': 40000, 'final': 47600, 'margen': 60},
        }
        
        articulos = Articulo.objects.all()
        corregidos = 0
        
        for articulo in articulos:
            if articulo.codigo in precios_realistas:
                precios = precios_realistas[articulo.codigo]
                
                self.stdout.write(f'\n{articulo.codigo} - {articulo.nombre}:')
                self.stdout.write(f'  Precio Costo: {articulo.precio_costo} -> {precios["costo"]}')
                self.stdout.write(f'  Precio Venta: {articulo.precio_venta} -> {precios["venta"]}')
                self.stdout.write(f'  Precio Final: {articulo.precio_final} -> {precios["final"]}')
                self.stdout.write(f'  Margen: {articulo.margen_porcentaje} -> {precios["margen"]}')
                
                articulo.precio_costo = Decimal(str(precios['costo']))
                articulo.precio_venta = Decimal(str(precios['venta']))
                articulo.precio_final = Decimal(str(precios['final']))
                articulo.margen_porcentaje = Decimal(str(precios['margen']))
                articulo.impuesto_especifico = Decimal('0')
                
                articulo.save()
                corregidos += 1
            else:
                self.stdout.write(f'\n{articulo.codigo} - {articulo.nombre}: Sin precios definidos')
        
        self.stdout.write(f'\nCorrección completada. {corregidos} artículos corregidos.')
