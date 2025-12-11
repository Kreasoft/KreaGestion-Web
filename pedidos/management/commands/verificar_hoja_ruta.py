"""
Comando para verificar datos de hoja de ruta
"""
from django.core.management.base import BaseCommand
from pedidos.models_rutas import HojaRuta
from facturacion_electronica.models import DocumentoTributarioElectronico
from django.db.models import Q


class Command(BaseCommand):
    help = 'Verifica los datos de una hoja de ruta y las facturas disponibles'

    def add_arguments(self, parser):
        parser.add_argument(
            '--hoja-ruta-id',
            type=int,
            help='ID de la hoja de ruta a verificar (por defecto la primera)',
        )

    def handle(self, *args, **options):
        hoja_ruta_id = options.get('hoja_ruta_id')
        
        if hoja_ruta_id:
            try:
                hr = HojaRuta.objects.get(pk=hoja_ruta_id)
            except HojaRuta.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'No existe hoja de ruta con ID {hoja_ruta_id}'))
                return
        else:
            hr = HojaRuta.objects.first()
            if not hr:
                self.stdout.write(self.style.ERROR('No hay hojas de ruta en la base de datos'))
                return

        self.stdout.write("=" * 60)
        self.stdout.write("INFORMACIÓN DE LA HOJA DE RUTA")
        self.stdout.write("=" * 60)
        self.stdout.write(f"ID: {hr.id}")
        self.stdout.write(f"Número: {hr.numero_ruta}")
        self.stdout.write(f"Fecha: {hr.fecha}")
        self.stdout.write(f"Ruta: {hr.ruta.codigo if hr.ruta else None} - {hr.ruta.nombre if hr.ruta else None}")
        self.stdout.write(f"Vehículo: {hr.vehiculo.patente if hr.vehiculo else None}")
        self.stdout.write(f"Chofer: {hr.chofer.nombre if hr.chofer else None}")
        self.stdout.write(f"Facturas asociadas: {hr.facturas.count()}")
        self.stdout.write("")

        self.stdout.write("=" * 60)
        self.stdout.write("CLIENTES DE LA RUTA")
        self.stdout.write("=" * 60)
        if hr.ruta:
            clientes = hr.ruta.clientes.filter(estado='activo')
            self.stdout.write(f"Total clientes activos: {clientes.count()}")
            for c in clientes[:10]:
                self.stdout.write(f"  - {c.nombre} (RUT: {c.rut})")
        else:
            self.stdout.write("No hay ruta asignada")
        self.stdout.write("")

        self.stdout.write("=" * 60)
        self.stdout.write("FACTURAS DEL DÍA")
        self.stdout.write("=" * 60)
        facturas_dia = DocumentoTributarioElectronico.objects.filter(
            fecha_emision=hr.fecha,
            tipo_dte__in=['33', '34']
        )
        self.stdout.write(f"Total facturas del día {hr.fecha}: {facturas_dia.count()}")
        for f in facturas_dia[:10]:
            venta_id = f.venta_id if f.venta_id else None
            cliente_nombre = f.venta.cliente.nombre if f.venta and f.venta.cliente else 'Sin cliente'
            orden_despacho_ids = list(f.orden_despacho.values_list('id', flat=True))
            self.stdout.write(f"  - Folio {f.folio}: {cliente_nombre}")
            self.stdout.write(f"    Venta ID: {venta_id}, Orden Despacho IDs: {orden_despacho_ids}")
        self.stdout.write("")

        self.stdout.write("=" * 60)
        self.stdout.write("FACTURAS DE CLIENTES DE LA RUTA DEL DÍA")
        self.stdout.write("=" * 60)
        if hr.ruta:
            # Buscar por venta directa o por orden_despacho
            facturas_ruta = DocumentoTributarioElectronico.objects.filter(
                fecha_emision=hr.fecha,
                tipo_dte__in=['33', '34'],
            ).filter(
                Q(venta__cliente__ruta=hr.ruta) | Q(orden_despacho__cliente__ruta=hr.ruta)
            ).distinct()
            self.stdout.write(f"Facturas de clientes de la ruta: {facturas_ruta.count()}")
            for f in facturas_ruta[:20]:
                # Intentar obtener cliente de venta directa o de orden_despacho
                cliente_nombre = 'Sin cliente'
                if f.venta and f.venta.cliente:
                    cliente_nombre = f.venta.cliente.nombre
                elif f.orden_despacho.exists():
                    primera_venta = f.orden_despacho.first()
                    if primera_venta and primera_venta.cliente:
                        cliente_nombre = primera_venta.cliente.nombre
                
                vehiculo_dte = f.vehiculo.patente if f.vehiculo else None
                vehiculo_venta = f.venta.vehiculo.patente if f.venta and f.venta.vehiculo else None
                self.stdout.write(f"  - Folio {f.folio}: {cliente_nombre}")
                self.stdout.write(f"    Vehículo DTE: {vehiculo_dte}, Vehículo Venta: {vehiculo_venta}")
        else:
            self.stdout.write("No hay ruta asignada")
        self.stdout.write("")

        self.stdout.write("=" * 60)
        self.stdout.write("FACTURAS YA EN OTRAS HOJAS DE RUTA")
        self.stdout.write("=" * 60)
        facturas_en_otras = HojaRuta.objects.exclude(pk=hr.pk).values_list('facturas__id', flat=True)
        facturas_en_otras_list = list(facturas_en_otras)
        self.stdout.write(f"Facturas en otras hojas: {len(facturas_en_otras_list)}")
        if facturas_en_otras_list:
            self.stdout.write(f"IDs: {facturas_en_otras_list[:10]}")
        self.stdout.write("")

        self.stdout.write("=" * 60)
        self.stdout.write("FACTURAS DISPONIBLES PARA ASOCIAR")
        self.stdout.write("=" * 60)
        if hr.ruta:
            # Buscar por venta directa o por orden_despacho
            facturas_disponibles = DocumentoTributarioElectronico.objects.filter(
                fecha_emision=hr.fecha,
                tipo_dte__in=['33', '34'],
            ).filter(
                Q(venta__cliente__ruta=hr.ruta) | Q(orden_despacho__cliente__ruta=hr.ruta)
            ).exclude(id__in=facturas_en_otras_list).distinct()
            self.stdout.write(f"Facturas disponibles: {facturas_disponibles.count()}")
            for f in facturas_disponibles[:20]:
                # Intentar obtener cliente de venta directa o de orden_despacho
                cliente_nombre = 'Sin cliente'
                if f.venta and f.venta.cliente:
                    cliente_nombre = f.venta.cliente.nombre
                elif f.orden_despacho.exists():
                    primera_venta = f.orden_despacho.first()
                    if primera_venta and primera_venta.cliente:
                        cliente_nombre = primera_venta.cliente.nombre
                self.stdout.write(f"  - Folio {f.folio}: {cliente_nombre} (ID: {f.id})")
        else:
            self.stdout.write("No hay ruta asignada")
        self.stdout.write("")

        self.stdout.write("=" * 60)
        self.stdout.write("VERIFICACIÓN POR VEHÍCULO")
        self.stdout.write("=" * 60)
        if hr.vehiculo:
            facturas_vehiculo = DocumentoTributarioElectronico.objects.filter(
                fecha_emision=hr.fecha,
                tipo_dte__in=['33', '34']
            ).filter(
                Q(vehiculo=hr.vehiculo) | Q(venta__vehiculo=hr.vehiculo) | Q(orden_despacho__vehiculo=hr.vehiculo)
            )
            self.stdout.write(f"Facturas con vehículo {hr.vehiculo.patente}: {facturas_vehiculo.count()}")
            for f in facturas_vehiculo[:10]:
                cliente_nombre = f.venta.cliente.nombre if f.venta and f.venta.cliente else 'Sin cliente'
                if not cliente_nombre or cliente_nombre == 'Sin cliente':
                    if f.orden_despacho.exists():
                        primera_venta = f.orden_despacho.first()
                        cliente_nombre = primera_venta.cliente.nombre if primera_venta and primera_venta.cliente else 'Sin cliente'
                self.stdout.write(f"  - Folio {f.folio}: {cliente_nombre}")
        else:
            self.stdout.write("No hay vehículo asignado")
        self.stdout.write("")

        self.stdout.write("=" * 60)
        self.stdout.write("DETALLE DE VENTAS EN ORDEN_DESPACHO")
        self.stdout.write("=" * 60)
        facturas_dia = DocumentoTributarioElectronico.objects.filter(
            fecha_emision=hr.fecha,
            tipo_dte__in=['33', '34']
        )
        for f in facturas_dia[:5]:
            self.stdout.write(f"Folio {f.folio}:")
            for venta in f.orden_despacho.all():
                cliente_nombre = venta.cliente.nombre if venta.cliente else 'Sin cliente'
                ruta_cliente = venta.cliente.ruta.codigo if venta.cliente and venta.cliente.ruta else None
                vehiculo_venta = venta.vehiculo.patente if venta.vehiculo else None
                self.stdout.write(f"  Venta ID {venta.id}: Cliente={cliente_nombre}, Ruta={ruta_cliente}, Vehículo={vehiculo_venta}")

