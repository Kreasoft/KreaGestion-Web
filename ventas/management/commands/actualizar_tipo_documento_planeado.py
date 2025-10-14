from django.core.management.base import BaseCommand
from django.db import transaction
from ventas.models import Venta

class Command(BaseCommand):
    help = 'Actualiza el campo tipo_documento_planeado en tickets existentes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostrar qué se actualizaría sin hacer cambios',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # Buscar tickets que tienen tipo_documento_planeado = None
        tickets_a_actualizar = Venta.objects.filter(
            tipo_documento='vale',
            estado='borrador',
            tipo_documento_planeado__isnull=True
        )

        total_tickets = tickets_a_actualizar.count()

        if total_tickets == 0:
            self.stdout.write(
                self.style.SUCCESS('No hay tickets que necesiten actualización')
            )
            return

        self.stdout.write(
            f'Se encontraron {total_tickets} tickets para actualizar'
        )

        if dry_run:
            self.stdout.write('MODO DRY RUN - No se harán cambios')
            for ticket in tickets_a_actualizar:
                self.stdout.write(
                    f'  Ticket #{ticket.numero_venta}: tipo_documento_planeado = None → "boleta"'
                )
            return

        # Actualizar los tickets
        with transaction.atomic():
            actualizados = 0
            for ticket in tickets_a_actualizar:
                # Para tickets existentes, asumir que eran para boleta por defecto
                # (esto es una suposición razonable basada en el comportamiento histórico)
                ticket.tipo_documento_planeado = 'boleta'
                ticket.save()
                actualizados += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Se actualizaron {actualizados} tickets exitosamente'
            )
        )



