"""
Comando para generar una factura de prueba
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from empresas.models import Empresa
from clientes.models import Cliente
from articulos.models import Articulo
from ventas.models import Venta, VentaDetalle, FormaPago, Vendedor
from caja.models import Caja, AperturaCaja, MovimientoCaja, VentaProcesada
from facturacion_electronica.dte_service import DTEService
from decimal import Decimal
import random
from django.utils import timezone


class Command(BaseCommand):
    help = 'Genera una factura de prueba con DTE'

    def add_arguments(self, parser):
        parser.add_argument(
            '--empresa-id',
            type=int,
            default=3,
            help='ID de la empresa (default: 3 = Kreasoft spa)'
        )
        parser.add_argument(
            '--tipo',
            type=str,
            default='factura',
            choices=['factura', 'boleta', 'guia'],
            help='Tipo de documento a generar (default: factura)'
        )

    def handle(self, *args, **options):
        empresa_id = options['empresa_id']
        tipo_doc = options['tipo']
        
        tipo_display = {
            'factura': 'FACTURA',
            'boleta': 'BOLETA',
            'guia': 'GUÍA DE DESPACHO'
        }
        
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS(f"GENERANDO {tipo_display[tipo_doc]} DE PRUEBA"))
        self.stdout.write("=" * 80)
        
        try:
            # 1. Obtener empresa
            empresa = Empresa.objects.get(id=empresa_id)
            self.stdout.write(f"\n1. Empresa: {empresa.nombre}")
            
            # 2. Obtener usuario
            usuario = User.objects.first()
            self.stdout.write(f"   Usuario: {usuario.username}")
            
            # 3. Obtener cliente
            cliente = Cliente.objects.filter(empresa=empresa).first()
            if not cliente:
                self.stdout.write(self.style.ERROR("   ERROR: No hay clientes"))
                return
            self.stdout.write(f"   Cliente: {cliente.nombre}")
            
            # 4. Obtener artículos
            articulos = list(Articulo.objects.filter(empresa=empresa, activo=True)[:2])
            if not articulos:
                self.stdout.write(self.style.ERROR("   ERROR: No hay artículos"))
                return
            self.stdout.write(f"   Artículos: {len(articulos)}")
            
            # 5. Obtener forma de pago
            forma_pago = FormaPago.objects.filter(empresa=empresa, activo=True).first()
            if not forma_pago:
                self.stdout.write(self.style.ERROR("   ERROR: No hay formas de pago"))
                return
            self.stdout.write(f"   Forma de Pago: {forma_pago.nombre}")
            
            # 6. Obtener vendedor
            vendedor = Vendedor.objects.filter(empresa=empresa, activo=True).first()
            
            # 7. Obtener caja activa
            caja = Caja.objects.filter(empresa=empresa, activo=True).first()
            if not caja:
                self.stdout.write(self.style.ERROR("   ERROR: No hay cajas activas"))
                return
            self.stdout.write(f"   Caja: {caja.nombre}")
            
            # 8. Obtener apertura de caja
            apertura = AperturaCaja.objects.filter(
                caja=caja,
                fecha_cierre__isnull=True
            ).first()
            if not apertura:
                self.stdout.write(self.style.ERROR("   ERROR: No hay apertura de caja"))
                return
            self.stdout.write(f"   Apertura: {apertura.id}")
            
            # 9. Crear venta
            numero_venta = random.randint(100000, 999999)
            self.stdout.write(f"\n2. Creando venta #{numero_venta}...")
            
            venta = Venta.objects.create(
                empresa=empresa,
                numero_venta=numero_venta,
                tipo_documento=tipo_doc,
                cliente=cliente,
                forma_pago=forma_pago,
                vendedor=vendedor,
                usuario_creacion=usuario,
                subtotal=Decimal('0'),
                descuento=Decimal('0'),
                iva=Decimal('0'),
                total=Decimal('0'),
                monto_pagado=Decimal('0'),
                saldo_pendiente=Decimal('0'),
                fecha=timezone.now().date()
            )
            
            # 10. Agregar detalles
            self.stdout.write("   Agregando detalles...")
            subtotal = Decimal('0')
            for articulo in articulos:
                cantidad = 2
                precio = Decimal(str(articulo.precio_venta))
                total_item = precio * cantidad
                
                VentaDetalle.objects.create(
                    venta=venta,
                    articulo=articulo,
                    cantidad=cantidad,
                    precio_unitario=precio,
                    precio_total=total_item
                )
                subtotal += total_item
                self.stdout.write(f"     - {articulo.nombre}: {cantidad} x ${precio} = ${total_item}")
            
            # 11. Actualizar totales
            iva = (subtotal * Decimal('0.19')).quantize(Decimal('1'))
            total = subtotal + iva
            
            venta.subtotal = subtotal
            venta.iva = iva
            venta.total = total
            venta.monto_pagado = total
            venta.saldo_pendiente = Decimal('0')
            venta.save()
            
            self.stdout.write(f"\n   Subtotal: ${subtotal}")
            self.stdout.write(f"   IVA (19%): ${iva}")
            self.stdout.write(f"   Total: ${total}")
            
            # 12. Crear movimiento de caja
            self.stdout.write("\n3. Registrando movimiento de caja...")
            movimiento = MovimientoCaja.objects.create(
                apertura_caja=apertura,
                venta=venta,
                tipo='venta',
                monto=total,
                forma_pago=forma_pago,
                descripcion=f'Venta #{numero_venta}',
                usuario=usuario
            )
            self.stdout.write(f"   Movimiento ID: {movimiento.id}")
            
            # 13. GENERAR DTE
            tipo_dte_map = {
                'factura': '33',  # Factura Electrónica
                'boleta': '39',   # Boleta Electrónica
                'guia': '52',     # Guía de Despacho Electrónica
            }
            tipo_dte = tipo_dte_map[tipo_doc]
            
            self.stdout.write(f"\n4. GENERANDO DTE ({tipo_display[tipo_doc]} ELECTRÓNICA)...")
            self.stdout.write("=" * 80)
            
            dte_service = DTEService(empresa)
            dte = dte_service.generar_dte_desde_venta(venta, tipo_dte)
            
            if dte and dte.id:
                self.stdout.write("\n" + "=" * 80)
                self.stdout.write(self.style.SUCCESS("DTE GENERADO EXITOSAMENTE"))
                self.stdout.write("=" * 80)
                self.stdout.write(f"   ID: {dte.id}")
                self.stdout.write(f"   Tipo: {dte.get_tipo_dte_display()}")
                self.stdout.write(f"   Folio: {dte.folio}")
                self.stdout.write(f"   Fecha Emisión: {dte.fecha_emision}")
                self.stdout.write(f"   RUT Receptor: {dte.rut_receptor}")
                self.stdout.write(f"   Razón Social: {dte.razon_social_receptor}")
                self.stdout.write(f"   Monto Neto: ${dte.monto_neto}")
                self.stdout.write(f"   IVA: ${dte.monto_iva}")
                self.stdout.write(f"   Total: ${dte.monto_total}")
                self.stdout.write(f"   Estado SII: {dte.estado_sii}")
                self.stdout.write(f"   Timbre PDF417: {'SÍ' if dte.timbre_pdf417 else 'NO'}")
                if dte.timbre_pdf417:
                    self.stdout.write(f"   URL Timbre: {dte.timbre_pdf417.url}")
                
                # Generar URL para ver el documento
                self.stdout.write("\n" + "=" * 80)
                self.stdout.write(self.style.SUCCESS(f"PARA VER LA {tipo_display[tipo_doc]}:"))
                self.stdout.write("=" * 80)
                self.stdout.write(f"   URL: http://localhost:8000/ventas/ventas/{venta.id}/html/")
                self.stdout.write(f"   Venta ID: {venta.id}")
                self.stdout.write(f"   DTE ID: {dte.id}")
                
            else:
                self.stdout.write(self.style.ERROR("\n   ERROR: No se pudo generar el DTE"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\nERROR: {str(e)}"))
            import traceback
            traceback.print_exc()

