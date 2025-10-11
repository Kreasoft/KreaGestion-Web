from django.core.management.base import BaseCommand
from ventas.models import Venta


class Command(BaseCommand):
    help = 'Recalcula los totales de los tickets (vales) para actualizar el impuesto específico'

    def add_arguments(self, parser):
        parser.add_argument(
            '--ticket',
            type=str,
            help='Número de ticket específico a recalcular (ej: 000068)',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Recalcular todos los tickets pendientes',
        )

    def handle(self, *args, **options):
        ticket_numero = options.get('ticket')
        recalcular_todos = options.get('all')

        if ticket_numero:
            # Recalcular un ticket específico
            try:
                ticket = Venta.objects.get(numero_venta=ticket_numero, tipo_documento='vale')
                self.stdout.write(f'Recalculando ticket #{ticket_numero}...')
                
                # Mostrar valores antes
                self.stdout.write(f'  Antes:')
                self.stdout.write(f'    Neto: ${ticket.neto}')
                self.stdout.write(f'    IVA: ${ticket.iva}')
                self.stdout.write(f'    Impuesto Específico: ${ticket.impuesto_especifico}')
                self.stdout.write(f'    Total: ${ticket.total}')
                
                # Recalcular
                ticket.calcular_totales()
                ticket.refresh_from_db()
                
                # Mostrar valores después
                self.stdout.write(f'  Después:')
                self.stdout.write(f'    Neto: ${ticket.neto}')
                self.stdout.write(f'    IVA: ${ticket.iva}')
                self.stdout.write(f'    Impuesto Específico: ${ticket.impuesto_especifico}')
                self.stdout.write(f'    Total: ${ticket.total}')
                
                self.stdout.write(self.style.SUCCESS(f'✓ Ticket #{ticket_numero} recalculado exitosamente'))
            except Venta.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'✗ Ticket #{ticket_numero} no encontrado'))
        
        elif recalcular_todos:
            # Recalcular todos los tickets pendientes
            tickets = Venta.objects.filter(tipo_documento='vale', estado='borrador')
            total = tickets.count()
            
            self.stdout.write(f'Recalculando {total} tickets pendientes...')
            
            for i, ticket in enumerate(tickets, 1):
                ticket.calcular_totales()
                if i % 10 == 0:
                    self.stdout.write(f'  Procesados: {i}/{total}')
            
            self.stdout.write(self.style.SUCCESS(f'✓ {total} tickets recalculados exitosamente'))
        
        else:
            self.stdout.write(self.style.WARNING('Debes especificar --ticket NUMERO o --all'))
            self.stdout.write('Ejemplos:')
            self.stdout.write('  python manage.py recalcular_tickets --ticket 000068')
            self.stdout.write('  python manage.py recalcular_tickets --all')
