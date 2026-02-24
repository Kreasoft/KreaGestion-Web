import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico
from empresas.models import Empresa
from libreria_dte_gdexpress.dte_gdexpress.gdexpress.cliente import ClienteGDExpress

# Obtener empresa activa
empresa = Empresa.objects.filter(activa=True).first()
if not empresa:
    print("❌ No hay empresa activa")
    exit(1)

print("=" * 60)
print("DIAGNÓSTICO FOLIOS 260 y 261")
print("=" * 60)
print(f"Empresa: {empresa.nombre}")
print(f"RUT Emisor: {empresa.rut}")
print()

# Buscar DTEs locales con folios 260 y 261
folios = ['260', '261']
for folio in folios:
    print(f"\n--- FOLIO {folio} ---")
    
    # Buscar en BD local
    dtes = DocumentoTributarioElectronico.objects.filter(
        tipo_dte='39',
        folio=folio,
        empresa=empresa
    ).order_by('-fecha_creacion')
    
    if dtes.exists():
        dte = dtes.first()
        print(f"✓ Encontrado en BD local:")
        print(f"  - ID: {dte.id}")
        print(f"  - Estado: {dte.estado}")
        print(f"  - Track ID: {dte.track_id or 'N/A'}")
        print(f"  - Fecha creación: {dte.fecha_creacion}")
        print(f"  - XML generado: {'Sí' if dte.xml_generado else 'No'}")
        print(f"  - XML firmado: {'Sí' if dte.xml_firmado else 'No'}")
        print(f"  - Tiene TED: {'Sí' if dte.ted else 'No'}")
        print(f"  - Error envío: {dte.error_envio or 'Ninguno'}")
    else:
        print(f"✗ No existe en BD local")
        continue
    
    # Intentar consultar en GDExpress por Track ID
    if dte.track_id and dte.track_id.startswith('DTEBOX-'):
        print(f"\n  Consultando GDExpress por Track ID: {dte.track_id}")
        try:
            cliente = ClienteGDExpress(
                api_key=empresa.dtebox_auth_key,
                ambiente=empresa.dtebox_ambiente or 'CERTIFICACION',
                url_servicio=empresa.dtebox_url
            )
            
            # Extraer timestamp del track_id (formato: DTEBOX-YYYYMMDDHHMMSS)
            track_id_clean = dte.track_id.replace('DTEBOX-', '')
            resultado = cliente.consultar_estado(track_id_clean)
            
            if resultado.get('success'):
                print(f"  ✓ Estado en GDExpress: {resultado.get('estado')}")
                print(f"  ✓ Glosa: {resultado.get('glosa')}")
            else:
                print(f"  ✗ No encontrado en GDExpress: {resultado.get('error')}")
                
        except Exception as e:
            print(f"  ✗ Error consultando GDExpress: {e}")

# Buscar documentos emitidos en GDExpress de los últimos 7 días
print("\n" + "=" * 60)
print("DOCUMENTOS EN GDExpress (últimos 7 días)")
print("=" * 60)

try:
    cliente = ClienteGDExpress(
        api_key=empresa.dtebox_auth_key,
        ambiente=empresa.dtebox_ambiente or 'CERTIFICACION',
        url_servicio=empresa.dtebox_url
    )
    
    # Buscar documentos emitidos por esta empresa (usando PaginatedSearch con query)
    # Nota: Para documentos emitidos, necesitamos usar un endpoint diferente
    # o consultar por RUT emisor en los documentos recibidos de otra empresa
    
    print("Consultando documentos...")
    # Intentar consulta de estado directa para folios 260 y 261
    # Esto requiere que sepamos el Track ID real de GDExpress
    
    print("\nPara verificar documentos EMITIDOS por tu empresa en GDExpress,")
    print("necesitas acceder a la aplicación VB6 de GDExpress o usar el portal web.")
    print(f"\nURL de acceso: http://200.6.118.43")
    print(f"RUT: {empresa.rut}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("RECOMENDACIÓN")
print("=" * 60)
print("""
Si los folios 260 y 261 NO aparecen en GDExpress pero el sistema
local dice que ya fueron enviados, puedes:

1. VERIFICAR EN GDExpress DIRECTAMENTE:
   - Accede a http://200.6.118.43 con tu usuario de GDExpress
   - Ve a "Documentos Emitidos" y busca folios 260 y 261

2. SI NO ESTÁN EN GDExpress:
   - El DTE local tiene un estado incorrecto
   - Puedes regenerarlos usando el comando:
     python manage.py regenerar_dte_completo <id_dte>

3. SI ESTÁN EN GDExpress PERO CON OTRO TRACK ID:
   - Actualiza el track_id en la BD local manualmente

4. REENVÍO MANUAL:
   - Si el documento NO está en GDExpress, puedes intentar reenviarlo
   - Primero verifica que el XML esté correcto
""")
