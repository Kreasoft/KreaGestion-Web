"""
Comando para actualizar saldos pendientes de ventas existentes
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from ventas.models import Venta
from decimal import Decimal


class Command(BaseCommand):
    help = 'Actualiza los campos monto_pagado y saldo_pendiente de ventas existentes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--empresa',
            type=int,
            help='ID de empresa específica (opcional)'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Actualizando saldos pendientes de ventas...'))

        # Filtrar ventas
        ventas = Venta.objects.filter(estado='confirmada')

        if options['empresa']:
            ventas = ventas.filter(empresa_id=options['empresa'])

        total_actualizadas = 0

        with transaction.atomic():
            for venta in ventas:
                venta_anterior = venta.monto_pagado
                saldo_anterior = venta.saldo_pendiente

                # Si tiene forma de pago
                if venta.forma_pago:
                    if venta.forma_pago.es_cuenta_corriente:
                        # En cuenta corriente, mantener monto pagado actual y calcular saldo
                        venta.saldo_pendiente = venta.total - venta.monto_pagado
                    else:
                        # Si no es cuenta corriente, monto pagado debe ser igual al total
                        venta.monto_pagado = venta.total
                        venta.saldo_pendiente = Decimal('0.00')
                else:
                    # Sin forma de pago, asumir pago completo
                    venta.monto_pagado = venta.total
                    venta.saldo_pendiente = Decimal('0.00')

                # Solo guardar si hubo cambios
                if (venta.monto_pagado != venta_anterior or
                    venta.saldo_pendiente != saldo_anterior):
                    venta.save()
                    total_actualizadas += 1

                    self.stdout.write(
                        self.style.SUCCESS(
                            f'OK Venta {venta.numero_venta}: '
                            f'Pagado ${venta.monto_pagado} -> Saldo ${venta.saldo_pendiente}'
                        )
                    )

        self.stdout.write(self.style.SUCCESS(f'Total de ventas actualizadas: {total_actualizadas}'))
