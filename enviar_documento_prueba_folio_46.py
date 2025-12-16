#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para enviar un documento de prueba con folio 46 al ambiente de pruebas de DTEBox
"""
import os
import sys
import django
from datetime import date, datetime

# Configurar Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from empresas.models import Empresa
from facturacion_electronica.dtebox_service import DTEBoxService

# Configurar encoding para Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def crear_xml_documento_prueba_folio_46():
    """
    Crea un XML de documento DTE de prueba con folio 46
    Basado en el formato oficial del SII
    """
    from datetime import datetime
    
    # Datos del documento
    folio = 46
    tipo_dte = 33  # Factura Electrónica
    fecha_emision = datetime.now().strftime('%Y-%m-%d')
    
    # Datos del emisor (Kreasoft spa)
    rut_emisor = "77117239-3"
    razon_social_emisor = "SOCIEDAD INFORMATICA KREASOFT SPA"
    giro_emisor = ".COMPUTACION"
    telefono_emisor = "963697225"
    acteco_emisor = "523930"
    direccion_emisor = "VICTOR PLAZA MAYORGA 887"
    comuna_emisor = "EL BOSQUE"
    ciudad_emisor = "SANTIAGO"
    
    # Datos del receptor (cliente de prueba)
    rut_receptor = "78421900-3"
    razon_social_receptor = "CLIENTE DE PRUEBA S.A."
    giro_receptor = "SERVICIOS DE PRUEBA"
    direccion_receptor = "CALLE PRUEBA 123"
    comuna_receptor = "SANTIAGO"
    ciudad_receptor = "SANTIAGO"
    
    # Totales del documento
    monto_neto = 100000
    monto_exento = 0
    tasa_iva = 19
    monto_iva = int(monto_neto * tasa_iva / 100)
    monto_total = monto_neto + monto_iva + monto_exento
    
    # Construir XML del documento (sin EnvioDTE, solo el Documento)
    xml = f'''<?xml version="1.0" encoding="ISO-8859-1"?>
<DTE xmlns="http://www.sii.cl/SiiDte" version="1.0">
<Documento ID="F{folio}T{tipo_dte}">
<Encabezado>
<IdDoc>
<TipoDTE>{tipo_dte}</TipoDTE>
<Folio>{folio}</Folio>
<FchEmis>{fecha_emision}</FchEmis>
<FmaPago>1</FmaPago>
</IdDoc>
<Emisor>
<RUTEmisor>{rut_emisor}</RUTEmisor>
<RznSoc>{razon_social_emisor}</RznSoc>
<GiroEmis>{giro_emisor}</GiroEmis>
<Telefono>{telefono_emisor}</Telefono>
<Acteco>{acteco_emisor}</Acteco>
<DirOrigen>{direccion_emisor}</DirOrigen>
<CmnaOrigen>{comuna_emisor}</CmnaOrigen>
<CiudadOrigen>{ciudad_emisor}</CiudadOrigen>
<CdgVendedor>OFICINA</CdgVendedor>
</Emisor>
<Receptor>
<RUTRecep>{rut_receptor}</RUTRecep>
<RznSocRecep>{razon_social_receptor}</RznSocRecep>
<GiroRecep>{giro_receptor}</GiroRecep>
<Contacto>.</Contacto>
<DirRecep>{direccion_receptor}</DirRecep>
<CmnaRecep>{comuna_receptor}</CmnaRecep>
<CiudadRecep>{ciudad_receptor}</CiudadRecep>
</Receptor>
<Totales>
<MntNeto>{monto_neto}</MntNeto>
<MntExe>{monto_exento}</MntExe>
<TasaIVA>{tasa_iva}</TasaIVA>
<IVA>{monto_iva}</IVA>
<MntTotal>{monto_total}</MntTotal>
</Totales>
</Encabezado>
<Detalle>
<NroLinDet>1</NroLinDet>
<CdgItem>
<TpoCodigo>INT</TpoCodigo>
<VlrCodigo>PRUEBA001</VlrCodigo>
</CdgItem>
<NmbItem>SERVICIO DE PRUEBA</NmbItem>
<DscItem>DOCUMENTO DE PRUEBA CON FOLIO {folio} - AMBIENTE DE PRUEBAS</DscItem>
<QtyItem>1</QtyItem>
<PrcItem>{monto_neto}</PrcItem>
<MontoItem>{monto_neto}</MontoItem>
</Detalle>
<TED version="1.0">
<DD></DD>
<FRMT algoritmo="SHA1withRSA"></FRMT>
</TED>
</Documento>
</DTE>'''
    
    return xml

def print_header(title):
    print("\n" + "=" * 80)
    print(title.center(80))
    print("=" * 80)

def enviar_documento_prueba_folio_46():
    print_header("ENVIAR DOCUMENTO DE PRUEBA - FOLIO 46")
    
    try:
        # Obtener empresa
        empresa = Empresa.objects.get(nombre="Kreasoft spa")
        
        # Configurar DTEBox para ambiente de PRUEBAS (T)
        empresa.dtebox_habilitado = True
        empresa.dtebox_url = "http://200.6.118.43/api/Core.svc/Core"
        empresa.dtebox_auth_key = "0a1c295d-7853-4e2e-ac90-d7d2fd46ecf0"
        empresa.dtebox_ambiente = "T"  # AMBIENTE DE PRUEBAS
        empresa.resolucion_numero = 80
        empresa.resolucion_fecha = date(2014, 8, 22)
        empresa.save()
        
        print(f"\n1. CONFIGURACIÓN:")
        print(f"   Empresa: {empresa.nombre}")
        print(f"   RUT: {empresa.rut}")
        print(f"   URL DTEBox: {empresa.dtebox_url}")
        print(f"   Auth Key: {empresa.dtebox_auth_key[:20]}...")
        print(f"   Ambiente: {empresa.dtebox_ambiente} (PRUEBAS)")
        print(f"   Resolución: N° {empresa.resolucion_numero} del {empresa.resolucion_fecha.strftime('%d-%m-%Y')}")
        
        # Crear XML del documento de prueba
        print(f"\n2. CREANDO XML DEL DOCUMENTO DE PRUEBA...")
        xml_documento = crear_xml_documento_prueba_folio_46()
        print(f"   Folio: 46")
        print(f"   Tipo DTE: 33 (Factura Electrónica)")
        print(f"   Tamaño XML: {len(xml_documento)} caracteres")
        
        # Guardar XML original en archivo
        xml_original_path = "xml_documento_original_folio_46.xml"
        with open(xml_original_path, 'w', encoding='ISO-8859-1') as f:
            f.write(xml_documento)
        print(f"\n   ✅ XML original guardado en: {xml_original_path}")
        
        print(f"\n   XML ORIGINAL COMPLETO:")
        print("=" * 80)
        print(xml_documento)
        print("=" * 80)
        
        # Firmar el documento (requerido para DTEBox)
        print(f"\n3. FIRMANDO DOCUMENTO...")
        xml_firmado = None
        
        # Buscar certificado en la carpeta indicada
        certificado_path = None
        password = '113147'  # Contraseña proporcionada
        
        import os
        import glob
        
        # Buscar en la carpeta del usuario
        carpeta_certificado = r"C:\Users\Usuario\OneDrive\Desktop\CAF-PRUEBAS-KREASOFT"
        
        # Buscar archivos de certificado
        extensiones = ['*.p12', '*.pfx', '*.P12', '*.PFX']
        for ext in extensiones:
            archivos = glob.glob(os.path.join(carpeta_certificado, ext))
            if archivos:
                certificado_path = archivos[0]
                break
        
        # Si no se encuentra, intentar con el certificado de la empresa
        if not certificado_path and empresa.certificado_digital:
            try:
                from django.conf import settings
                if hasattr(empresa.certificado_digital, 'path'):
                    certificado_path = empresa.certificado_digital.path
                else:
                    certificado_path = os.path.join(settings.MEDIA_ROOT, empresa.certificado_digital.name)
                password = empresa.password_certificado or password
            except:
                pass
        
        if certificado_path and os.path.exists(certificado_path):
            try:
                from facturacion_electronica.firma_electronica import FirmadorDTE
                
                print(f"   Certificado encontrado: {certificado_path}")
                print(f"   Firmando documento...")
                
                firmador = FirmadorDTE(certificado_path, password)
                xml_firmado = firmador.firmar_xml(xml_documento)
                
                print(f"   ✅ Documento firmado exitosamente")
                print(f"   Tamaño XML firmado: {len(xml_firmado)} caracteres")
                
                # Guardar XML firmado en archivo
                xml_firmado_path = "xml_documento_firmado_folio_46.xml"
                with open(xml_firmado_path, 'w', encoding='ISO-8859-1') as f:
                    f.write(xml_firmado)
                print(f"   ✅ XML firmado guardado en: {xml_firmado_path}")
                
                print(f"\n   XML FIRMADO COMPLETO:")
                print("=" * 80)
                print(xml_firmado)
                print("=" * 80)
                
            except Exception as e:
                print(f"\n⚠️ ADVERTENCIA: Error al firmar documento: {str(e)}")
                import traceback
                traceback.print_exc()
                print(f"   Intentando enviar documento sin firmar (puede fallar)...")
                xml_firmado = xml_documento
        else:
            print(f"   ⚠️ ADVERTENCIA: No se encontró certificado digital")
            print(f"   Buscado en: {carpeta_certificado}")
            print(f"   Intentando enviar documento sin firmar (puede fallar)...")
            print(f"   NOTA: DTEBox generalmente requiere documentos firmados")
            xml_firmado = xml_documento
        
        # Inicializar servicio DTEBox
        print(f"\n4. INICIALIZANDO SERVICIO DTEBox...")
        servicio = DTEBoxService(empresa)
        print(f"   ✅ Servicio inicializado")
        
        # Enviar documento para timbrar
        print(f"\n5. ENVIANDO DOCUMENTO A DTEBox PARA TIMBRAR...")
        resultado = servicio.timbrar_dte(xml_firmado)
        
        print_header("RESULTADO DEL TIMBRAJE:")
        if resultado['success']:
            print(f"✅ Documento timbrado exitosamente!")
            print(f"\n   TED recibido:")
            if resultado.get('ted'):
                ted_decoded = resultado['ted'].decode('ISO-8859-1') if isinstance(resultado['ted'], bytes) else resultado['ted']
                print(f"   {ted_decoded[:500]}...")
            print(f"\n   Mensaje: {resultado.get('message', 'N/A')}")
        else:
            print(f"❌ Error al timbrar documento:")
            print(f"   {resultado.get('error', 'Error desconocido')}")
            if resultado.get('ted'):
                print(f"\n   TED recibido (puede contener información del error):")
                ted_decoded = resultado['ted'].decode('ISO-8859-1') if isinstance(resultado['ted'], bytes) else resultado['ted']
                print(f"   {ted_decoded[:500]}...")
        
        print("\n" + "=" * 80)
        
    except Empresa.DoesNotExist:
        print("[ERROR] No se encontró la empresa 'Kreasoft spa'")
    except Exception as e:
        print(f"[ERROR] Error inesperado: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    enviar_documento_prueba_folio_46()

