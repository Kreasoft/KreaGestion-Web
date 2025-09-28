from django.core.management.base import BaseCommand
from articulos.models import Articulo
from decimal import Decimal

class Command(BaseCommand):
    help = 'Corrige precios corruptos en todos los artículos'

    def handle(self, *args, **options):
        articulos = Articulo.objects.all()
        corregidos = 0
        
        for articulo in articulos:
            try:
                # Obtener valores actuales
                precio_costo = articulo._string_to_decimal(articulo.precio_costo)
                precio_venta = articulo._string_to_decimal(articulo.precio_venta)
                margen_porcentaje = articulo._string_to_decimal(articulo.margen_porcentaje)
                
                # Recalcular todo correctamente
                if precio_costo > 0 and margen_porcentaje > 0:
                    # Calcular precio de venta desde costo y margen
                    precio_venta_calculado = precio_costo * (1 + margen_porcentaje / 100)
                    articulo.precio_venta = str(precio_venta_calculado)
                    precio_venta = precio_venta_calculado
                
                # Calcular precio final
                if precio_venta > 0:
                    precio_final_calculado = precio_venta * Decimal('1.19')
                    articulo.precio_final = str(int(precio_final_calculado))
                
                # Recalcular margen si es necesario
                if precio_costo > 0 and precio_venta > 0:
                    margen_calculado = ((precio_venta - precio_costo) / precio_costo) * 100
                    articulo.margen_porcentaje = str(round(margen_calculado, 2))
                
                articulo.save()
                corregidos += 1
                
                self.stdout.write(
                    self.style.SUCCESS(f'Artículo {articulo.nombre} corregido')
                )
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error en artículo {articulo.nombre}: {e}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'Se corrigieron {corregidos} artículos')
        )




