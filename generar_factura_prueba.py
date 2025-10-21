#!/usr/bin/env python
"""
Script para generar una factura de prueba y verificar que todo funciona
"""
import os
import sys
import django
from decimal import Decimal

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_cloud.settings')
django.setup()

from django.contrib.auth.models import User
from empresas.models import Empresa
from clientes.models import Cliente
from articulos.models import Articulo
from ventas.models import Venta, VentaDetalle, FormaPago, Vendedor
from caja.models import Caja, AperturaCaja, MovimientoCaja, VentaProcesada
from facturacion_electronica.dte_service import DTEService
import random
from django.utils import timezone

def main():
    print("=" * 80)
    print("GENERANDO FACTURA DE PRUEBA")
    print("=" * 80)
    
    try:
        # 1. Obtener empresa KREASOFT
        empresa = Empresa.objects.get(nombre__icontains='kreasoft')
        print(f"\n1. Empresa: {empresa.nombre}")
        
        # 2. Obtener usuario
        usuario = User.objects.first()
        print(f"   Usuario: {usuario.username}")
        
        # 3. Obtener cliente
        cliente = Cliente.objects.filter(empresa=empresa).first()
        if not cliente:
            print("   ERROR: No hay clientes")
            return
        print(f"   Cliente: {cliente.nombre}")
        
        # 4. Obtener artículos
        articulos = list(Articulo.objects.filter(empresa=empresa, activo=True)[:2])
        if not articulos:
            print("   ERROR: No hay artículos")
            return
        print(f"   Artículos: {len(articulos)}")
        
        # 5. Obtener forma de pago
        forma_pago = FormaPago.objects.filter(empresa=empresa, activo=True).first()
        if not forma_pago:
            print("   ERROR: No hay formas de pago")
            return
        print(f"   Forma de Pago: {forma_pago.nombre}")
        
        # 6. Obtener vendedor
        vendedor = Vendedor.objects.filter(empresa=empresa, activo=True).first()
        
        # 7. Obtener caja activa
        caja = Caja.objects.filter(empresa=empresa, activa=True).first()
        if not caja:
            print("   ERROR: No hay cajas activas")
            return
        print(f"   Caja: {caja.nombre}")
        
        # 8. Obtener apertura de caja
        apertura = AperturaCaja.objects.filter(
            caja=caja,
            fecha_cierre__isnull=True
        ).first()
        if not apertura:
            print("   ERROR: No hay apertura de caja")
            return
        print(f"   Apertura: {apertura.id}")
        
        # 9. Crear venta
        numero_venta = random.randint(100000, 999999)
        print(f"\n2. Creando venta #{numero_venta}...")
        
        venta = Venta.objects.create(
            empresa=empresa,
            numero_venta=numero_venta,
            tipo_documento='factura',
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
        print("   Agregando detalles...")
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
                precio_total=total_item,
                descuento=Decimal('0')
            )
            subtotal += total_item
            print(f"     - {articulo.nombre}: {cantidad} x ${precio} = ${total_item}")
        
        # 11. Actualizar totales
        iva = (subtotal * Decimal('0.19')).quantize(Decimal('1'))
        total = subtotal + iva
        
        venta.subtotal = subtotal
        venta.iva = iva
        venta.total = total
        venta.monto_pagado = total
        venta.saldo_pendiente = Decimal('0')
        venta.save()
        
        print(f"\n   Subtotal: ${subtotal}")
        print(f"   IVA (19%): ${iva}")
        print(f"   Total: ${total}")
        
        # 12. Crear movimiento de caja
        print("\n3. Registrando movimiento de caja...")
        movimiento = MovimientoCaja.objects.create(
            apertura_caja=apertura,
            tipo_movimiento='venta',
            monto=total,
            forma_pago=forma_pago,
            concepto=f'Venta #{numero_venta}',
            usuario=usuario
        )
        print(f"   Movimiento ID: {movimiento.id}")
        
        # 13. Crear VentaProcesada
        print("\n4. Creando VentaProcesada...")
        venta_procesada = VentaProcesada.objects.create(
            ticket=None,
            venta_final=venta,
            apertura_caja=apertura,
            usuario=usuario,
            monto_total=total,
            forma_pago_principal=forma_pago,
            procesada=True
        )
        print(f"   VentaProcesada ID: {venta_procesada.id}")
        
        # 14. GENERAR DTE
        print("\n5. GENERANDO DTE (FACTURA ELECTRÓNICA)...")
        print("=" * 80)
        
        dte_service = DTEService(empresa)
        dte = dte_service.generar_dte_desde_venta(venta, '33')  # 33 = Factura Electrónica
        
        if dte and dte.id:
            print("\n" + "=" * 80)
            print("DTE GENERADO EXITOSAMENTE")
            print("=" * 80)
            print(f"   ID: {dte.id}")
            print(f"   Tipo: {dte.get_tipo_dte_display()}")
            print(f"   Folio: {dte.folio}")
            print(f"   Fecha Emisión: {dte.fecha_emision}")
            print(f"   RUT Receptor: {dte.rut_receptor}")
            print(f"   Razón Social: {dte.razon_social_receptor}")
            print(f"   Monto Neto: ${dte.monto_neto}")
            print(f"   IVA: ${dte.monto_iva}")
            print(f"   Total: ${dte.monto_total}")
            print(f"   Estado SII: {dte.estado_sii}")
            print(f"   Timbre PDF417: {'SÍ' if dte.timbre_pdf417 else 'NO'}")
            if dte.timbre_pdf417:
                print(f"   URL Timbre: {dte.timbre_pdf417.url}")
            
            # Asignar DTE a VentaProcesada
            venta_procesada.dte_generado = dte
            venta_procesada.save()
            print(f"\n   DTE asignado a VentaProcesada")
            
            # Generar URL para ver la factura
            print("\n" + "=" * 80)
            print("PARA VER LA FACTURA:")
            print("=" * 80)
            print(f"   URL: http://localhost:8000/ventas/venta/{venta.id}/html/")
            print(f"   Venta ID: {venta.id}")
            print(f"   DTE ID: {dte.id}")
            
        else:
            print("\n   ERROR: No se pudo generar el DTE")
            
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()

