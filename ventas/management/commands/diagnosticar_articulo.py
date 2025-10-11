from django.core.management.base import BaseCommand
from articulos.models import Articulo


class Command(BaseCommand):
    help = 'Diagnostica la configuración de impuestos de un artículo'

    def add_arguments(self, parser):
        parser.add_argument(
            'nombre',
            type=str,
            help='Nombre del artículo a diagnosticar (puede ser parcial)',
        )

    def handle(self, *args, **options):
        nombre = options['nombre']
        
        # Buscar artículos que coincidan
        articulos = Articulo.objects.filter(nombre__icontains=nombre, activo=True)
        
        if not articulos.exists():
            self.stdout.write(self.style.ERROR(f'✗ No se encontraron artículos con "{nombre}"'))
            return
        
        for articulo in articulos:
            self.stdout.write('=' * 80)
            self.stdout.write(f'Artículo: {articulo.nombre}')
            self.stdout.write(f'ID: {articulo.id}')
            self.stdout.write('-' * 80)
            
            # Información de categoría
            if articulo.categoria:
                self.stdout.write(f'Categoría: {articulo.categoria.nombre}')
                self.stdout.write(f'  - Exenta de IVA: {articulo.categoria.exenta_iva}')
                
                if articulo.categoria.impuesto_especifico:
                    imp_esp = articulo.categoria.impuesto_especifico
                    self.stdout.write(f'  - Impuesto Específico: {imp_esp.nombre}')
                    self.stdout.write(f'  - Porcentaje: {imp_esp.porcentaje}%')
                    self.stdout.write(f'  - Porcentaje Decimal: {imp_esp.get_porcentaje_decimal()}')
                else:
                    self.stdout.write(self.style.WARNING('  - ⚠️  NO tiene impuesto específico configurado'))
            else:
                self.stdout.write(self.style.WARNING('⚠️  NO tiene categoría asignada'))
            
            self.stdout.write('-' * 80)
            
            # Información de precios
            self.stdout.write(f'Precio Venta (Neto): ${articulo.precio_venta}')
            self.stdout.write(f'Precio Final: ${articulo.precio_final}')
            
            # Calcular desglose correcto
            self.stdout.write('-' * 80)
            self.stdout.write('Desglose Correcto:')
            
            # Convertir precio_final de string a float
            try:
                precio_final = float(articulo.precio_final.replace(',', '.'))
            except (ValueError, AttributeError):
                self.stdout.write(self.style.ERROR('✗ Error al leer precio_final'))
                continue
            
            if articulo.categoria:
                tiene_iva = not articulo.categoria.exenta_iva
                imp_esp_pct = 0
                
                if articulo.categoria.impuesto_especifico:
                    imp_esp_pct = float(articulo.categoria.impuesto_especifico.get_porcentaje_decimal())
                
                # Calcular factor total
                factor_total = 1 + (0.19 if tiene_iva else 0) + imp_esp_pct
                
                # Calcular neto
                neto = precio_final / factor_total
                iva = neto * 0.19 if tiene_iva else 0
                imp_esp = neto * imp_esp_pct
                
                self.stdout.write(f'  Neto (Base): ${neto:.2f}')
                self.stdout.write(f'  IVA (19%): ${iva:.2f}')
                self.stdout.write(f'  Impuesto Específico ({imp_esp_pct*100:.0f}%): ${imp_esp:.2f}')
                self.stdout.write(f'  TOTAL: ${neto + iva + imp_esp:.2f}')
                
                # Verificar
                total_calculado = neto + iva + imp_esp
                if abs(total_calculado - precio_final) < 0.01:
                    self.stdout.write(self.style.SUCCESS('  ✓ Cálculo correcto'))
                else:
                    self.stdout.write(self.style.ERROR(f'  ✗ Error en cálculo: diferencia de ${abs(total_calculado - precio_final):.2f}'))
            
            self.stdout.write('=' * 80)
            self.stdout.write('')
