from django.core.management.base import BaseCommand

from tesoreria.services import sincronizar_venta_credito_en_tesoreria
from ventas.models import Venta


class Command(BaseCommand):
    help = 'Sincroniza en Tesorería las facturas ya emitidas con saldo pendiente o cuenta corriente'

    def add_arguments(self, parser):
        parser.add_argument(
            '--folio',
            type=str,
            help='Folio DTE específico a sincronizar, por ejemplo 95',
        )
        parser.add_argument(
            '--numero',
            type=str,
            help='Número de venta específico a sincronizar',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo muestra los documentos a sincronizar sin aplicar cambios',
        )

    def handle(self, *args, **options):
        folio = (options.get('folio') or '').strip()
        numero = (options.get('numero') or '').strip()
        dry_run = bool(options.get('dry_run'))

        ventas = Venta.objects.filter(
            cliente__isnull=False,
            estado='confirmada',
            saldo_pendiente__gt=0,
            tipo_documento__in=['factura', 'factura_electronica'],
        ).select_related('empresa', 'cliente', 'forma_pago', 'usuario_creacion')

        if numero:
            ventas = ventas.filter(numero_venta=numero)

        candidatas = []
        for venta in ventas:
            dte = getattr(venta, 'dte_asociado', None)
            if folio and str(getattr(dte, 'folio', '') or '').strip() != folio:
                continue

            es_credito = bool(getattr(getattr(venta, 'forma_pago', None), 'es_cuenta_corriente', False)) or bool(venta.saldo_pendiente > 0)
            if not es_credito:
                continue

            candidatas.append((venta, dte))

        if not candidatas:
            self.stdout.write(self.style.WARNING('No se encontraron facturas a crédito para sincronizar.'))
            return

        self.stdout.write(f'Se encontraron {len(candidatas)} factura(s) a crédito para sincronizar.\n')

        sincronizadas = 0
        errores = 0

        for venta, dte in candidatas:
            folio_dte = getattr(dte, 'folio', None)
            etiqueta = f'Venta {venta.numero_venta}'
            if folio_dte:
                etiqueta += f' / DTE {getattr(dte, "tipo_dte", "")}-{folio_dte}'

            if dry_run:
                self.stdout.write(f'[DRY] {etiqueta} | Cliente: {venta.cliente.nombre} | Saldo: {venta.saldo_pendiente}')
                continue

            try:
                sincronizar_venta_credito_en_tesoreria(
                    venta,
                    dte=dte,
                    usuario=venta.usuario_creacion,
                    descripcion=f'Regularización retroactiva crédito {etiqueta}',
                )
                self.stdout.write(self.style.SUCCESS(f'[OK] {etiqueta}'))
                sincronizadas += 1
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f'[ERROR] {etiqueta}: {exc}'))
                errores += 1

        if dry_run:
            self.stdout.write(self.style.SUCCESS('\nDRY RUN completado. No se aplicaron cambios.'))
            return

        self.stdout.write(self.style.SUCCESS(f'\nSincronizadas: {sincronizadas}'))
        if errores:
            self.stdout.write(self.style.WARNING(f'Con errores: {errores}'))
