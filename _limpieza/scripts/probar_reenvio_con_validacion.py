#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para probar el método reenviar_documento con validación de documento timbrado
"""
import os
import sys
import django
from datetime import date

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

# XML real con TED timbrado
XML_REAL = """<EnvioDTE xmlns="http://www.sii.cl/SiiDte" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="1.0" xsi:schemaLocation="http://www.sii.cl/SiiDte EnvioDTE_v10.xsd">
<SetDTE ID="IDe7179f61e6ec4e38bef475d79ccccce1">
<Caratula version="1.0">
<RutEmisor>77117239-3</RutEmisor>
<RutEnvia>10974377-1</RutEnvia>
<RutReceptor>78421900-3</RutReceptor>
<FchResol>2014-08-22</FchResol>
<NroResol>80</NroResol>
<TmstFirmaEnv>2025-12-01T13:23:58</TmstFirmaEnv>
<SubTotDTE>
<TpoDTE>33</TpoDTE>
<NroDTE>1</NroDTE>
</SubTotDTE>
</Caratula>
<DTE xmlns:xs="http://www.w3.org/2001/XMLSchema-instance" xmlns:ds="http://www.w3.org/2000/09/xmldsig#" xmlns="http://www.sii.cl/SiiDte" version="1.0">
<Documento ID="F3233T33">
<Encabezado>
<IdDoc>
<TipoDTE>33</TipoDTE>
<Folio>3233</Folio>
<FchEmis>2025-12-01</FchEmis>
<FmaPago>1</FmaPago>
</IdDoc>
<Emisor>
<RUTEmisor>77117239-3</RUTEmisor>
<RznSoc>SOCIEDAD INFORMATICA KREASOFT SPA</RznSoc>
<GiroEmis>.COMPUTACION</GiroEmis>
<Telefono>963697225</Telefono>
<Acteco>523930</Acteco>
<DirOrigen>VICTOR PLAZA MAYORGA 887</DirOrigen>
<CmnaOrigen>EL BOSQUE</CmnaOrigen>
<CiudadOrigen>SANTIAGO</CiudadOrigen>
<CdgVendedor>OFICINA</CdgVendedor>
</Emisor>
<Receptor>
<RUTRecep>78421900-3</RUTRecep>
<RznSocRecep>JPF CINE S.A.</RznSocRecep>
<GiroRecep>PRODUCCIONES AUDIOVISUALES.</GiroRecep>
<Contacto>.</Contacto>
<DirRecep>CALLE NUEVA 1757.</DirRecep>
<CmnaRecep>HUECHURABA.</CmnaRecep>
<CiudadRecep>SANTIAGO.</CiudadRecep>
</Receptor>
<Totales>
<MntNeto>186327</MntNeto>
<MntExe>0</MntExe>
<TasaIVA>19</TasaIVA>
<IVA>35402</IVA>
<MntTotal>221729</MntTotal>
</Totales>
</Encabezado>
<Detalle>
<NroLinDet>1</NroLinDet>
<CdgItem>
<TpoCodigo>INT</TpoCodigo>
<VlrCodigo>SER001</VlrCodigo>
</CdgItem>
<NmbItem>SERVICIO MENSUAL</NmbItem>
<DscItem>SERVICIO DE MANTENCION SISTEMAS D I C I E M B R E - 2025 </DscItem>
<QtyItem>1</QtyItem>
<PrcItem>186327</PrcItem>
<MontoItem>186327</MontoItem>
</Detalle>
<TED version="1.0">
<DD>
<RE>77117239-3</RE>
<TD>33</TD>
<F>3233</F>
<FE>2025-12-01</FE>
<RR>78421900-3</RR>
<RSR>JPF CINE S.A.</RSR>
<MNT>221729</MNT>
<IT1>SERVICIO MENSUAL</IT1>
<CAF version="1.0">
<DA>
<RE>77117239-3</RE>
<RS>SOCIEDAD INFORMÁTICA KREASOFT SPA</RS>
<TD>33</TD>
<RNG>
<D>3228</D>
<H>3284</H>
</RNG>
<FA>2025-11-03</FA>
<RSAPK>
<M>sSOwWVw3ztxfiEpKMJjgBcGj+4wrzPQOqWr/d1uJaooIZdm+++7gGCuLGbKLuPWDEfJxS70Al2T1NUHhUtObDw==</M>
<E>Aw==</E>
</RSAPK>
<IDK>300</IDK>
</DA>
<FRMA algoritmo="SHA1withRSA">cetfrzBaZejYuxS20E/xhW2+4S06FIscWnjJvLI5TMBNodgcUMG7UXy9cefJ+WS2busql0Xs47PknD3AA6pFAg==</FRMA>
</CAF>
<TSTED>2025-12-01T13:23:53</TSTED>
</DD>
<FRMT algoritmo="SHA1withRSA">Y9yDCVWfhkpT3AlxV+eoYxD9V9XoRcl2vtwSDwwhIqKKHqu548PchsrS5F7+IRks0ocFOOuI7rB0wrEf6vGyBg==</FRMT>
</TED>
<TmstFirma>2025-12-01T13:23:54</TmstFirma>
</Documento>
</DTE>
</SetDTE>
</EnvioDTE>"""

def print_header(title):
    print("\n" + "=" * 80)
    print(title.center(80))
    print("=" * 80)

def probar_reenvio_con_validacion():
    print_header("PROBAR REENVÍO CON VALIDACIÓN DE DOCUMENTO TIMBRADO")
    
    try:
        empresa = Empresa.objects.get(nombre="Kreasoft spa")
        
        # Configurar DTEBox
        empresa.dtebox_habilitado = True
        empresa.dtebox_url = "http://200.6.118.43/api/Core.svc/Core"
        empresa.dtebox_auth_key = "0a1c295d-7853-4e2e-ac90-d7d2fd46ecf0"
        empresa.dtebox_ambiente = "P"
        empresa.resolucion_numero = 80
        empresa.resolucion_fecha = date(2014, 8, 22)
        empresa.save()
        
        print(f"\nEmpresa: {empresa.nombre}")
        print(f"RUT: {empresa.rut}")
        print(f"URL DTEBox: {empresa.dtebox_url}")
        print(f"Ambiente: {empresa.dtebox_ambiente}")
        
        # Inicializar servicio
        servicio = DTEBoxService(empresa)
        
        # Primero verificar el estado del documento
        print(f"\n1. VERIFICANDO ESTADO DEL DOCUMENTO...")
        verificacion = servicio._verificar_documento_timbrado(XML_REAL)
        print(f"   Estado: {verificacion['tipo']}")
        print(f"   Mensaje: {verificacion['mensaje']}")
        print(f"   ¿Está timbrado?: {'Sí' if verificacion['timbrado'] else 'No'}")
        
        # Intentar reenviar
        print(f"\n2. INTENTANDO REENVIAR DOCUMENTO...")
        resultado = servicio.reenviar_documento(XML_REAL)
        
        print_header("RESULTADO DEL REENVÍO:")
        if resultado['success']:
            print(f"✅ {resultado['message']}")
        else:
            print(f"❌ Error: {resultado['error']}")
        
        print("\n" + "=" * 80)
        
    except Empresa.DoesNotExist:
        print("[ERROR] No se encontró la empresa 'Kreasoft spa'")
    except Exception as e:
        print(f"[ERROR] Error inesperado: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    probar_reenvio_con_validacion()







