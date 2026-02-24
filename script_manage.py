# Copiar y pegar este contenido en: python manage.py shell
# O ejecutar con: python manage.py shell < script_manage.py

from facturacion_electronica.dtebox_service import DTEBoxService
from facturacion_electronica.dte_generator import DTEXMLGenerator
from facturacion_electronica.models import DocumentoTributarioElectronico
from core.models import Empresa

print('=' * 80)
print('REENVIO DE BOLETA FOLIO 258')
print('=' * 80)

dte = DocumentoTributarioElectronico.objects.filter(tipo_dte='39', folio=258).first()

if not dte:
    print('ERROR: No se encontro la boleta folio 258')
    boletas = DocumentoTributarioElectronico.objects.filter(tipo_dte='39').order_by('-folio')[:5]
    print('\nBoletas disponibles:')
    for b in boletas:
        print(f'  - Folio {b.folio}, Estado: {b.estado_sii}')
else:
    print(f'\nBoleta encontrada:')
    print(f'  Folio: {dte.folio}')
    print(f'  Estado SII: {dte.estado_sii}')
    print(f'  Empresa: {dte.empresa.nombre}')
    
    empresa = dte.empresa
    
    if not empresa.dtebox_habilitado:
        print(f'\nERROR: DTEBox no esta habilitado para {empresa.nombre}')
    else:
        print(f'\nDTEBox configurado:')
        print(f'  URL: {empresa.dtebox_url}')
        print(f'  Ambiente: {empresa.dtebox_ambiente}')
        
        print(f'\nRegenerando XML con formato correcto...')
        
        try:
            generator = DTEXMLGenerator(dte, empresa)
            xml_nuevo = generator.generar_xml_desde_dte()
            
            print(f'XML regenerado exitosamente')
            print(f'Longitud: {len(xml_nuevo)} caracteres')
            print(f'\nPrimeros 800 caracteres:')
            print('-' * 80)
            print(xml_nuevo[:800])
            print('-' * 80)
            
            dte.xml_firmado = xml_nuevo
            dte.save()
            print('\nXML guardado en el DTE')
            
            print(f'\nEnviando a DTEBox...')
            
            service = DTEBoxService(empresa)
            resultado = service.timbrar_dte(dte.xml_firmado, '39')
            
            print(f'\nResultado del envio:')
            print(f'  Success: {resultado.get("success")}')
            print(f'  Estado: {resultado.get("estado")}')
            print(f'  Error: {resultado.get("error")}')
            print(f'  Track ID: {resultado.get("track_id")}')
            
            if resultado.get('success'):
                print(f'\nBOLETA FOLIO 258 ENVIADA EXITOSAMENTE!')
                dte.estado_sii = 'enviado'
                dte.track_id = resultado.get('track_id')
                if resultado.get('ted'):
                    dte.timbre_electronico = resultado.get('ted')
                dte.save()
                print('DTE actualizado en la base de datos')
            else:
                print(f'\nERROR EN ENVIO: {resultado.get("error")}')
                
        except Exception as e:
            print(f'\nEXCEPCION: {type(e).__name__}: {e}')
            import traceback
            traceback.print_exc()

# Para salir del shell automaticamente
exit()
