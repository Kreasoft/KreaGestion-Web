import os
import sys
import django

sys.path.append(r'c:\PROJECTOS-WEB\GestionCloud')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico as DTE
from dte_gdexpress import ClienteGDExpress
from facturacion_electronica.firma_electronica import FirmadorDTE
from facturacion_electronica.pdf417_generator import PDF417Generator

def main(dte_id):
    dte = DTE.objects.filter(id=dte_id).first()
    if not dte:
        print("NOT_FOUND")
        return
    empresa = dte.empresa
    cliente = ClienteGDExpress(
        api_key=empresa.dtebox_auth_key,
        ambiente='CERTIFICACION' if (empresa.dtebox_ambiente or 'T') == 'T' else 'PRODUCCION',
        url_servicio=empresa.dtebox_url
    )
    xml = dte.xml_firmado or dte.xml_dte
    resol_num = int(empresa.resolucion_numero or 0)
    resol_fch = empresa.resolucion_fecha.strftime('%Y-%m-%d') if empresa.resolucion_fecha else '2014-08-22'
    resultado = cliente.enviar_dte(xml_firmado=xml, resolucion_numero=resol_num, resolucion_fecha=resol_fch)
    if resultado.get('success'):
        track_id = resultado.get('track_id', 'DTEBOX-' + str(dte.folio))
        ted = resultado.get('ted') or ''
        dte.estado_sii = 'enviado'
        dte.track_id = track_id
        dte.timbre_electronico = ted
        if ted:
            firmador = FirmadorDTE(empresa)
            dte.datos_pdf417 = firmador.generar_datos_pdf417(ted)
            PDF417Generator.guardar_pdf417_en_dte(dte)
        dte.save()
        print("OK", track_id)
    else:
        print("ERROR", resultado.get('error'), resultado.get('detail', ''))

if __name__ == "__main__":
    dte_id = int(sys.argv[1]) if len(sys.argv) > 1 else 156
    main(dte_id)
