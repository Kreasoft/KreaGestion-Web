import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
import django
django.setup()

from facturacion_electronica.models import ArchivoCAF
from empresas.models import Empresa

empresa = Empresa.objects.get(id=1)
caf = ArchivoCAF.objects.filter(empresa=empresa, tipo_documento='39', oculto=False).first()

folio = caf.folio_actual + 1

# Generar XML de boleta
xml_boleta = f'''<?xml version="1.0" encoding="ISO-8859-1"?>
<DTE version="1.0">
  <Documento ID="B{folio}">
    <Encabezado>
      <IdDoc>
        <TipoDTE>39</TipoDTE>
        <Folio>{folio}</Folio>
        <FchEmis>2025-12-30</FchEmis>
        <FmaPago>1</FmaPago>
      </IdDoc>
      <Emisor>
        <RUTEmisor>77117239-3</RUTEmisor>
        <RznSoc>Sociedad Informatica Kreasoft SpA</RznSoc>
        <GiroEmis>Desarrollo de Software</GiroEmis>
        <Acteco>523930</Acteco>
        <DirOrigen>Victor Plaza Mayorga 887</DirOrigen>
        <CmnaOrigen>El Bosque</CmnaOrigen>
        <CiudadOrigen>Santiago</CiudadOrigen>
      </Emisor>
      <Receptor>
        <RUTRecep>66666666-6</RUTRecep>
        <RznSocRecep>Cliente Generico</RznSocRecep>
        <GiroRecep>Sin Giro</GiroRecep>
        <DirRecep>Sin Direccion</DirRecep>
        <CmnaRecep>SANTIAGO</CmnaRecep>
        <CiudadRecep>SANTIAGO</CiudadRecep>
      </Receptor>
      <Totales>
        <MntNeto>1000</MntNeto>
        <MntExe>0</MntExe>
        <TasaIVA>19</TasaIVA>
        <IVA>190</IVA>
        <MntTotal>1190</MntTotal>
      </Totales>
    </Encabezado>
    <Detalle>
      <NroLinDet>1</NroLinDet>
      <NmbItem>Producto de Prueba</NmbItem>
      <DscItem>Producto de Prueba</DscItem>
      <QtyItem>1</QtyItem>
      <UnmdItem>UN</UnmdItem>
      <PrcItem>1000</PrcItem>
      <MontoItem>1000</MontoItem>
    </Detalle>
  </Documento>
</DTE>'''

# Guardar en archivo
ruta = 'C:/PROJECTOS-WEB/GestionCloud/logs/dtebox_debug/boleta_para_gdexpress.xml'
os.makedirs(os.path.dirname(ruta), exist_ok=True)

with open(ruta, 'w', encoding='ISO-8859-1') as f:
    f.write(xml_boleta)

print(f'Archivo guardado en: {ruta}')
print(f'Folio usado: {folio}')


