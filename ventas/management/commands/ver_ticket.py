from django.core.management.base import BaseCommand
from ventas.models import Venta, VentaDetalle


class Command(BaseCommand):
    help = 'Muestra los datos exactos de un ticket desde la base de datos'

    def add_arguments(self, parser):
        parser.add_argument('numero', type=str, help='Número de ticket')

    def handle(self, *args, **options):
        numero = options['numero']
        
        try:
            ticket = Venta.objects.get(numero_venta=numero, tipo_documento='vale')
            
            self.stdout.write('=' * 80)
            self.stdout.write(f'TICKET #{numero} - DATOS EN BASE DE DATOS')
            self.stdout.write('=' * 80)
            
            # Datos básicos
            self.stdout.write(f'ID: {ticket.id}')
            self.stdout.write(f'Cliente: {ticket.cliente.nombre if ticket.cliente else "Sin cliente"}')
            self.stdout.write(f'Fecha: {ticket.fecha_creacion}')
            self.stdout.write(f'Estado: {ticket.estado}')
            
            self.stdout.write('-' * 80)
            self.stdout.write('TOTALES GUARDADOS EN BD:')
            self.stdout.write('-' * 80)
            
            # Mostrar EXACTAMENTE lo que está en la BD
            self.stdout.write(f'subtotal:            ${ticket.subtotal}')
            self.stdout.write(f'descuento:           ${ticket.descuento}')
            self.stdout.write(f'neto:                ${ticket.neto}')
            self.stdout.write(f'iva:                 ${ticket.iva}')
            self.stdout.write(f'impuesto_especifico: ${ticket.impuesto_especifico}')
            self.stdout.write(f'total:               ${ticket.total}')
            
            self.stdout.write('-' * 80)
            self.stdout.write('DETALLES:')
            self.stdout.write('-' * 80)
            
            detalles = VentaDetalle.objects.filter(venta=ticket)
            for detalle in detalles:
                self.stdout.write(f'{detalle.articulo.nombre}')
                self.stdout.write(f'  Cantidad: {detalle.cantidad}')
                self.stdout.write(f'  Precio Unitario: ${detalle.precio_unitario}')
                self.stdout.write(f'  Precio Total: ${detalle.precio_total}')
                self.stdout.write(f'  Impuesto Específico: ${detalle.impuesto_especifico}')
                self.stdout.write('')
            
            self.stdout.write('=' * 80)
            
            # Verificación
            if ticket.impuesto_especifico == 0 or ticket.impuesto_especifico is None:
                self.stdout.write(self.style.ERROR('⚠️  PROBLEMA: impuesto_especifico es 0 o NULL en la BD'))
                self.stdout.write('')
                self.stdout.write('SOLUCIÓN: Ejecuta:')
                self.stdout.write(f'  python manage.py recalcular_tickets --ticket {numero}')
            else:
                self.stdout.write(self.style.SUCCESS('✓ El ticket tiene impuesto_especifico guardado'))
                
        except Venta.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'✗ Ticket #{numero} no encontrado'))
