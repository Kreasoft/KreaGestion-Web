from django.core.management.base import BaseCommand
from articulos.models import Articulo
from decimal import Decimal

class Command(BaseCommand):
    help = 'Corrige los precios mal formateados en la base de datos - Versión 2'

    def handle(self, *args, **options):
        self.stdout.write('Iniciando corrección de precios (Versión 2)...')
        
        articulos = Articulo.objects.all()
        corregidos = 0
        
        for articulo in articulos:
            self.stdout.write(f'\nProcesando: {articulo.codigo} - {articulo.nombre}')
            
            # Valores originales
            precio_costo_original = articulo.precio_costo
            precio_venta_original = articulo.precio_venta
            precio_final_original = articulo.precio_final
            margen_original = articulo.margen_porcentaje
            impuesto_original = articulo.impuesto_especifico
            
            # Función para detectar si un valor está mal formateado
            def is_malformatted(value):
                if not value:
                    return False
                value_str = str(value)
                # Si tiene más de 6 dígitos y no tiene decimales, probablemente está mal
                if len(value_str.replace('.', '').replace(',', '')) > 6 and '.' not in value_str and ',' not in value_str:
                    return True
                return False
            
            # Función para corregir valores mal formateados
            def fix_value(value, expected_range=(1, 1000000)):
                if not value:
                    return Decimal('0')
                
                value_str = str(value)
                value_decimal = Decimal(value_str)
                
                # Si el valor está fuera del rango esperado, probablemente está mal formateado
                if value_decimal > expected_range[1]:
                    # Intentar dividir por 100 para corregir
                    corrected = value_decimal / 100
                    if expected_range[0] <= corrected <= expected_range[1]:
                        return corrected
                    # Intentar dividir por 1000
                    corrected = value_decimal / 1000
                    if expected_range[0] <= corrected <= expected_range[1]:
                        return corrected
                    # Intentar dividir por 10000
                    corrected = value_decimal / 10000
                    if expected_range[0] <= corrected <= expected_range[1]:
                        return corrected
                
                return value_decimal
            
            # Corregir precios
            articulo.precio_costo = fix_value(articulo.precio_costo, (1, 1000000))
            articulo.precio_venta = fix_value(articulo.precio_venta, (1, 1000000))
            articulo.precio_final = fix_value(articulo.precio_final, (1, 1000000))
            articulo.margen_porcentaje = fix_value(articulo.margen_porcentaje, (0, 1000))
            articulo.impuesto_especifico = fix_value(articulo.impuesto_especifico, (0, 100))
            
            # Mostrar cambios
            if (precio_costo_original != articulo.precio_costo or 
                precio_venta_original != articulo.precio_venta or 
                precio_final_original != articulo.precio_final or
                margen_original != articulo.margen_porcentaje or
                impuesto_original != articulo.impuesto_especifico):
                
                self.stdout.write(f'  Precio Costo: {precio_costo_original} -> {articulo.precio_costo}')
                self.stdout.write(f'  Precio Venta: {precio_venta_original} -> {articulo.precio_venta}')
                self.stdout.write(f'  Precio Final: {precio_final_original} -> {articulo.precio_final}')
                self.stdout.write(f'  Margen: {margen_original} -> {articulo.margen_porcentaje}')
                self.stdout.write(f'  Impuesto: {impuesto_original} -> {articulo.impuesto_especifico}')
                
                articulo.save()
                corregidos += 1
            else:
                self.stdout.write('  Sin cambios necesarios')
        
        self.stdout.write(f'\nCorrección completada. {corregidos} artículos corregidos.')
