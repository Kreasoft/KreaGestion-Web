from django.core.management.base import BaseCommand
from articulos.models import Articulo
from decimal import Decimal

class Command(BaseCommand):
    help = 'Corrige los precios mal formateados en la base de datos'

    def handle(self, *args, **options):
        self.stdout.write('Iniciando corrección de precios...')
        
        articulos = Articulo.objects.all()
        corregidos = 0
        
        for articulo in articulos:
            # Función para convertir formato chileno a decimal
            def parse_chilean_number(value):
                if not value:
                    return Decimal('0')
                # Convertir a string y quitar separadores de miles
                value_str = str(value).replace('.', '')
                # Convertir coma decimal a punto
                value_str = value_str.replace(',', '.')
                try:
                    return Decimal(value_str)
                except:
                    return Decimal('0')
            
            # Guardar valores originales para comparar
            precio_costo_original = articulo.precio_costo
            precio_venta_original = articulo.precio_venta
            precio_final_original = articulo.precio_final
            margen_original = articulo.margen_porcentaje
            impuesto_original = articulo.impuesto_especifico
            
            # Convertir valores
            articulo.precio_costo = parse_chilean_number(articulo.precio_costo)
            articulo.precio_venta = parse_chilean_number(articulo.precio_venta)
            articulo.precio_final = parse_chilean_number(articulo.precio_final)
            articulo.margen_porcentaje = parse_chilean_number(articulo.margen_porcentaje)
            articulo.impuesto_especifico = parse_chilean_number(articulo.impuesto_especifico)
            
            # Mostrar cambios
            self.stdout.write(f'\n{articulo.codigo} - {articulo.nombre}:')
            self.stdout.write(f'  Precio Costo: {precio_costo_original} -> {articulo.precio_costo}')
            self.stdout.write(f'  Precio Venta: {precio_venta_original} -> {articulo.precio_venta}')
            self.stdout.write(f'  Precio Final: {precio_final_original} -> {articulo.precio_final}')
            self.stdout.write(f'  Margen: {margen_original} -> {articulo.margen_porcentaje}')
            self.stdout.write(f'  Impuesto: {impuesto_original} -> {articulo.impuesto_especifico}')
            
            articulo.save()
            corregidos += 1
        
        self.stdout.write(f'\nCorrección completada. {corregidos} artículos corregidos.')






