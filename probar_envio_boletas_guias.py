"""
Script para probar el envío de guías de despacho (tipo 52) al SII.
Regenera XML cuando falta (guías con transferencia) y luego envía hasta que funcione.
"""
import os
import django
import time
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from django.utils import timezone
from facturacion_electronica.models import DocumentoTributarioElectronico
from facturacion_electronica.background_sender import get_background_sender
from empresas.models import Empresa


def regenerar_xml_guia(guia, empresa):
    """Regenera xml_dte y xml_firmado para una guía con transferencia (misma lógica que views_dte)."""
    transferencia = getattr(guia, 'transferencias', None)
    if transferencia:
        transferencia = transferencia.first()
    if not transferencia or not guia.caf_utilizado:
        return False, "Sin transferencia o sin CAF"
    try:
        from facturacion_electronica.dte_generator import DTEXMLGenerator
        from facturacion_electronica.firma_electronica import FirmadorDTE
        from facturacion_electronica.pdf417_generator import PDF417Generator
        from facturacion_electronica.dte_service import DTEService

        detalles = transferencia.detalles.all()
        subtotal = sum(detalle.total for detalle in detalles)
        iva = subtotal * Decimal('0.19')
        total = subtotal + iva

        class TransferenciaWrapper:
            def __init__(self, transferencia, subtotal, iva, total, tipo_traslado='5'):
                self.empresa = transferencia.empresa
                self.cliente = None
                self.tipo_documento = '52'
                self.fecha_emision = timezone.now().date()
                self.tipo_traslado = tipo_traslado
                self.tipo_despacho = tipo_traslado
                self.rut_receptor = transferencia.empresa.rut
                self.razon_social_receptor = transferencia.empresa.nombre
                self.giro_receptor = transferencia.empresa.giro
                self.direccion_receptor = transferencia.empresa.direccion
                self.comuna_receptor = transferencia.empresa.comuna
                self.ciudad_receptor = transferencia.empresa.ciudad
                self.monto_neto = subtotal
                self.monto_exento = Decimal('0')
                self.monto_iva = iva
                self.monto_total = total
                self.descuento = Decimal('0')
                self.items = transferencia.detalles

        tipo_traslado = (guia.tipo_traslado or '5').strip() or '5'
        venta_wrapper = TransferenciaWrapper(transferencia, subtotal, iva, total, tipo_traslado=tipo_traslado)
        generator = DTEXMLGenerator(empresa, venta_wrapper, '52', guia.folio, guia.caf_utilizado)
        xml_sin_firmar = generator.generar_xml()

        if not getattr(empresa, 'certificado_digital', None):
            return False, "Empresa sin certificado digital"
        firmador = FirmadorDTE(empresa.certificado_digital.path, empresa.password_certificado)
        xml_firmado = firmador.firmar_xml(xml_sin_firmar)

        ted_xml = None
        if getattr(empresa, 'dtebox_habilitado', False):
            try:
                from facturacion_electronica.dtebox_service import DTEBoxService
                dtebox = DTEBoxService(empresa)
                res_dtebox = dtebox.timbrar_dte(xml_sin_firmar, '52')  # Enviamos sin firmar (GDExpress)
                if res_dtebox.get('success') and res_dtebox.get('ted'):
                    ted_xml = res_dtebox['ted']
            except Exception:
                pass
        if not ted_xml:
            dte_service = DTEService(empresa)
            datos_caf = {}
            try:
                datos_parsed = dte_service._parsear_datos_caf(guia.caf_utilizado)
                datos_caf = {'modulo': datos_parsed.get('M', ''), 'exponente': datos_parsed.get('E', '')}
            except Exception:
                datos_caf = {'modulo': 'ERROR', 'exponente': 'ERROR'}
            caf = guia.caf_utilizado
            dte_data = {
                'rut_emisor': empresa.rut,
                'tipo_dte': '52',
                'folio': guia.folio,
                'fecha_emision': (guia.fecha_emision or timezone.now().date()).strftime('%Y-%m-%d'),
                'rut_receptor': empresa.rut,
                'razon_social_receptor': empresa.nombre,
                'monto_total': int(total),
                'item_1': 'Guía de Despacho Electrónica',
            }
            caf_data = {
                'rut_emisor': empresa.rut,
                'razon_social': empresa.razon_social_sii or empresa.razon_social,
                'tipo_documento': '52',
                'folio_desde': caf.folio_desde,
                'folio_hasta': caf.folio_hasta,
                'fecha_autorizacion': caf.fecha_autorizacion.strftime('%Y-%m-%d'),
                'modulo': datos_caf.get('modulo', ''),
                'exponente': datos_caf.get('exponente', ''),
                'firma': caf.firma_electronica,
            }
            ted_xml = firmador.generar_ted(dte_data, caf_data)

        pdf417_data = firmador.generar_datos_pdf417(ted_xml)
        guia.xml_dte = xml_sin_firmar
        guia.xml_firmado = xml_firmado
        guia.timbre_electronico = ted_xml
        guia.datos_pdf417 = pdf417_data
        guia.estado_sii = 'generado'
        guia.error_envio = ''
        guia.track_id = ''
        guia.save()
        PDF417Generator.guardar_pdf417_en_dte(guia)
        return True, "OK"
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, str(e)


def probar_envio_guias():
    """Prueba el envío de guías de despacho usando el background_sender."""
    
    print("=" * 80)
    print("PRUEBA DE ENVÍO DE GUÍAS DE DESPACHO (Tipo 52)")
    print("=" * 80)
    
    # Obtener empresa
    try:
        empresa = Empresa.objects.first()
        if not empresa:
            print("\n[X] No hay empresas en el sistema")
            return
        
        print(f"\n[OK] Empresa: {empresa.nombre}")
        print(f"  RUT: {empresa.rut}")
        print(f"  DTEBox habilitado: {empresa.dtebox_habilitado}")
        
        if not empresa.dtebox_habilitado:
            print("\n[ADVERTENCIA] DTEBox no esta habilitado para esta empresa")
            print("   El envio se probara pero puede fallar")
    except Exception as e:
        print(f"\n[ERROR] Error obteniendo empresa: {e}")
        return
    
    sender = get_background_sender()
    
    # Obtener guías pendientes (tipo 52)
    print("\n" + "=" * 80)
    print("GUÍAS DE DESPACHO (Tipo 52)")
    print("=" * 80)
    
    guias = list(DocumentoTributarioElectronico.objects.filter(
        tipo_dte='52',
        empresa=empresa
    ).exclude(estado_sii='enviado').order_by('-id')[:5])
    
    # Paso 1: Regenerar XML a guías que no tienen y tienen transferencia
    for guia in guias:
        tiene_xml = bool((guia.xml_dte or '').strip() or (guia.xml_firmado or '').strip())
        if not tiene_xml:
            print(f"\n  Regenerando XML para Guía Folio {guia.folio}...")
            ok, msg = regenerar_xml_guia(guia, empresa)
            if ok:
                print(f"    [OK] XML regenerado")
                guia.refresh_from_db()
            else:
                print(f"    [SKIP] {msg}")
    
    if not guias:
        print("\n[INFO] No hay guias pendientes para probar")
    else:
        print(f"\n[OK] Guías a probar: {len(guias)}")
        
        for guia in guias:
            guia.refresh_from_db()
            print(f"\n  -> Guia Folio {guia.folio}:")
            tiene_xml = bool((guia.xml_dte or '').strip() or (guia.xml_firmado or '').strip())
            print(f"    Estado actual: {guia.estado_sii}")
            print(f"    Tiene XML (sin firmar/firmado): {'Sí' if tiene_xml else 'No'}")
            print(f"    Tiene TED del CAF: {'Sí' if guia.timbre_electronico else 'No'}")
            
            if not tiene_xml:
                print(f"    [SKIP] Sin XML y no se pudo regenerar")
                continue
            
            print(f"    Enviando al SII...")
            resultado = sender.enviar_dte(guia.id, empresa.id)
            
            if resultado:
                print(f"    [OK] Agregada a la cola de envio")
                print(f"    Esperando procesamiento (max 30 segundos)...")
                
                # Esperar y monitorear el estado
                estado_anterior = guia.estado_sii
                for i in range(30):  # Esperar hasta 30 segundos
                    time.sleep(1)
                    guia.refresh_from_db()
                    
                    # Si cambió el estado, mostrar
                    if guia.estado_sii != estado_anterior:
                        print(f"    Estado cambiado: {estado_anterior} -> {guia.estado_sii}")
                        estado_anterior = guia.estado_sii
                    
                    # Si terminó (enviado o pendiente con error), salir
                    if guia.estado_sii in ['enviado', 'pendiente']:
                        break
                
                # Mostrar resultado final
                print(f"\n    === RESULTADO FINAL ===")
                print(f"    Estado final: {guia.estado_sii}")
                if guia.error_envio:
                    print(f"    ERROR COMPLETO:")
                    print(f"    {guia.error_envio}")
                if guia.track_id:
                    print(f"    Track ID: {guia.track_id}")
                if guia.timbre_electronico:
                    print(f"    TED recibido: {'Sí' if guia.timbre_electronico else 'No'}")
                    if guia.timbre_electronico:
                        print(f"    TED (primeros 100 chars): {guia.timbre_electronico[:100]}")
            else:
                print(f"    [ERROR] Error al agregar a la cola")
    
    # Mostrar estadísticas del sender
    print("\n" + "=" * 80)
    print("ESTADÍSTICAS DEL BACKGROUND SENDER")
    print("=" * 80)
    
    stats = sender.get_stats()
    print(f"\n  Enviados: {stats['enviados']}")
    print(f"  Errores: {stats['errores']}")
    print(f"  En cola: {stats['en_cola']}")
    print(f"  Workers activos: {stats['workers_activos']}")
    if stats['ultimo_error']:
        print(f"  Último error: {stats['ultimo_error'][:100]}")
    
    print("\n" + "=" * 80)
    print("RESUMEN FINAL")
    print("=" * 80)
    
    # Revisar estado final: solo "CORREGIDO" cuando está enviado
    print("\n[RESUMEN] Estado final de las guías:")
    
    if guias:
        for guia in guias:
            guia.refresh_from_db()
            if guia.estado_sii == 'enviado':
                estado_icono = "[CORREGIDO]"
                detalle = "enviado al SII"
            elif not ((guia.xml_dte or '').strip() or (guia.xml_firmado or '').strip()):
                estado_icono = "[REGENERAR XML]"
                detalle = "sin XML -> Regenerar desde detalle del DTE"
            elif guia.error_envio:
                estado_icono = "[ERROR]"
                detalle = guia.estado_sii
            else:
                estado_icono = "[PENDIENTE]"
                detalle = guia.estado_sii
            print(f"  {estado_icono} Folio {guia.folio}: {detalle}")
            if guia.error_envio and ((guia.xml_dte or '').strip() or (guia.xml_firmado or '').strip()):
                print(f"       Error: {guia.error_envio[:120]}")
    else:
        print("  (No hay guías pendientes)")
    
    print("\n" + "=" * 80)
    print("PRUEBA COMPLETADA (solo CORREGIDO = enviado al SII)")
    print("=" * 80)

if __name__ == '__main__':
    probar_envio_guias()
