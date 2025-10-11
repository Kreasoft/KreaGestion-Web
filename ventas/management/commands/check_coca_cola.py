from django.core.management.base import BaseCommand
from articulos.models import Articulo
from decimal import Decimal

class Command(BaseCommand):
    help = 'Ver configuración de Coca Cola'

    def handle(self, *args, **options):
        try:
            coca = Articulo.objects.get(nombre__icontains='Coca Cola 350ml')
            
            self.stdout.write(f"\n=== COCA COLA 350ML ===")
            self.stdout.write(f"ID: {coca.id}")
            self.stdout.write(f"Precio Venta: ${coca.precio_venta}")
            self.stdout.write(f"Categoría: {coca.categoria.nombre if coca.categoria else 'N/A'}")
            
            if coca.categoria:
                self.stdout.write(f"\n--- CATEGORÍA ---")
                self.stdout.write(f"Exenta IVA: {coca.categoria.exenta_iva}")
                if coca.categoria.impuesto_especifico:
                    self.stdout.write(f"Impuesto Específico: {coca.categoria.impuesto_especifico.nombre}")
                    self.stdout.write(f"Porcentaje: {coca.categoria.impuesto_especifico.porcentaje}%")
                    self.stdout.write(f"Decimal: {coca.categoria.impuesto_especifico.get_porcentaje_decimal()}")
                else:
                    self.stdout.write(f"Impuesto Específico: No tiene")
            
            # Calcular manualmente
            self.stdout.write(f"\n--- CÁLCULO CORRECTO ---")
            precio_venta = Decimal(str(coca.precio_venta))
            self.stdout.write(f"Precio Venta (neto): ${precio_venta}")
            
            iva = precio_venta * Decimal('0.19')
            self.stdout.write(f"IVA (19%): ${iva}")
            
            imp_esp_pct = coca.categoria.impuesto_especifico.get_porcentaje_decimal() if coca.categoria and coca.categoria.impuesto_especifico else Decimal('0')
            imp_esp = precio_venta * imp_esp_pct
            self.stdout.write(f"Imp. Específico ({imp_esp_pct * 100}%): ${imp_esp}")
            
            total = precio_venta + iva + imp_esp
            self.stdout.write(f"TOTAL: ${total}")
            
        except Articulo.DoesNotExist:
            self.stdout.write(self.style.ERROR('Coca Cola no encontrada'))
