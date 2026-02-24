import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
import django
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico

print("VERIFICANDO FOLIO 261 DESPUÉS DE REGENERACIÓN")
print("="*60)

dte = DocumentoTributarioElectronico.objects.filter(tipo_dte='39', folio=261).first()

if dte:
    print(f"DTE ID: {dte.id}")
    print(f"Estado SII: {dte.estado_sii}")
    print(f"Error envío: {dte.error_envio[:80] if dte.error_envio else 'Ninguno'}")
    print(f"Track ID: {dte.track_id or 'N/A'}")
    print()
    
    if dte.xml_firmado:
        xml = dte.xml_firmado[:2000]
        tiene_rzn_soc_emisor = 'RznSocEmisor' in xml
        tiene_tasa_iva = 'TasaIVA' in xml
        
        print(f"XML firmado: {len(dte.xml_firmado)} caracteres")
        print(f"RznSocEmisor (correcto): {'SÍ' if tiene_rzn_soc_emisor else 'NO'}")
        print(f"TasaIVA (prohibido): {'SÍ (MAL)' if tiene_tasa_iva else 'NO (BIEN)'}")
        
        if tiene_rzn_soc_emisor and not tiene_tasa_iva:
            print("\n✅ XML REGENERADO CORRECTAMENTE")
            print("Listo para enviar a GDExpress")
        else:
            print("\n❌ XML aún tiene errores de esquema")
    else:
        print("No tiene XML firmado")
else:
    print("No encontrado")
