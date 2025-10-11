from django.core.management.base import BaseCommand
from ventas.models import Venta, VentaDetalle
from decimal import Decimal

class Command(BaseCommand):
    help = 'Recalcular valores de todos los tickets (vales) con impuestos incorrectos'

    def handle(self, *args, **options):
        # Buscar todos los vales
        tickets = Venta.objects.filter(tipo_documento='vale')
        
        self.stdout.write(f"\nEncontrados {tickets.count()} tickets para revisar\n")
        
        corregidos = 0
        
        for ticket in tickets:
            # Obtener detalles
            detalles = VentaDetalle.objects.filter(venta=ticket)
            
            if not detalles.exists():
                continue
            
            # Recalcular totales correctamente
            subtotal = Decimal('0')
            neto_total = Decimal('0')
            iva_total = Decimal('0')
            imp_esp_total = Decimal('0')
            
            for detalle in detalles:
                articulo = detalle.articulo
                cantidad = detalle.cantidad
                precio_unitario = detalle.precio_unitario  # Precio final con impuestos
                
                # Calcular subtotal
                subtotal += precio_unitario * cantidad
                
                # Obtener información de impuestos de la categoría
                categoria = articulo.categoria
                exenta_iva = categoria.exenta_iva if categoria else False
                imp_especifico_pct = categoria.impuesto_especifico.get_porcentaje_decimal() if categoria and categoria.impuesto_especifico else Decimal('0')
                
                # Calcular precio neto (sin impuestos)
                factor_total = Decimal('1') + (Decimal('0') if exenta_iva else Decimal('0.19')) + imp_especifico_pct
                precio_neto_unitario = precio_unitario / factor_total
                
                # Calcular impuestos
                iva_unitario = Decimal('0') if exenta_iva else precio_neto_unitario * Decimal('0.19')
                imp_esp_unitario = precio_neto_unitario * imp_especifico_pct
                
                neto_total += precio_neto_unitario * cantidad
                iva_total += iva_unitario * cantidad
                imp_esp_total += imp_esp_unitario * cantidad
            
            # Verificar si necesita corrección
            if (abs(ticket.neto - neto_total) > Decimal('0.01') or 
                abs(ticket.iva - iva_total) > Decimal('0.01') or
                abs(ticket.impuesto_especifico - imp_esp_total) > Decimal('0.01')):
                
                self.stdout.write(f"\n--- Ticket #{ticket.numero_venta} ---")
                self.stdout.write(f"ANTES: Neto={ticket.neto}, IVA={ticket.iva}, Imp.Esp={ticket.impuesto_especifico}")
                
                # Actualizar valores
                ticket.subtotal = subtotal
                ticket.neto = neto_total.quantize(Decimal('0.01'))
                ticket.iva = iva_total.quantize(Decimal('0.01'))
                ticket.impuesto_especifico = imp_esp_total.quantize(Decimal('0.01'))
                ticket.total = subtotal
                ticket.save()
                
                self.stdout.write(f"DESPUÉS: Neto={ticket.neto}, IVA={ticket.iva}, Imp.Esp={ticket.impuesto_especifico}")
                corregidos += 1
        
        self.stdout.write(self.style.SUCCESS(f'\n✓ {corregidos} tickets corregidos exitosamente'))
