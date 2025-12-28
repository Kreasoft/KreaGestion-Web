#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de diagnóstico para determinar el motivo exacto del error 500
"""
import os
import sys
import django
import base64
import xml.etree.ElementTree as ET
import requests

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

# XML real proporcionado anteriormente
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
<Signature xmlns="http://www.w3.org/2000/09/xmldsig#">
<SignedInfo>
<CanonicalizationMethod Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"/>
<SignatureMethod Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha1"/>
<Reference URI="#F3233T33">
<Transforms>
<Transform Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"/>
</Transforms>
<DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"/>
<DigestValue>ZRD6zrCCj/cScNz+uOtp3gCBFDQ=</DigestValue>
</Reference>
</SignedInfo>
<SignatureValue> Rx70brlvHeh/vpHf+w8Vo3mA+R1QvyOidk1dMzCNjb1/ACUswRP5GnC6CAnBshQT B1yYLNQnEA7oCmdQutqz8f9uy0CQJ+IrsRwTu8pQyrpEyTx59XXJ+1gz5nUTWee7 pIvxh2v3GX9jVRVjW4sdqFGxfXE6UYH0ucdnHXBYKEzCy4rH5NJRJsk5iYmszrrx fRiCiHd9tXT0y60R3o0EnTp8KRqPK+E3YlY4iXgekKoIiMro7rtww9e23xSy9AOG 9fFR+lA/6WWIubFXidq84RseMhvWbLYsEXQC2eJ4iNT5deg/m6S2uNxBuH/0ou/f hKvQCZDnrTUOEf87qtUqgQ== </SignatureValue>
<KeyInfo>
<KeyValue>
<RSAKeyValue>
<Modulus> nMxFllg/ae7Awo2T+2/6mMFfebVoTC4vBfqV5feMkAQ4YevKqh2nhBtjB4HKhMd4 GEVn3O57BTRkjEdQIGy/lVQBgBdZzaTW8e0YDqIXZQSh9qKRQqL9tQ7nhNl8Cq1e BMJqLInQVvlC0UYmvUEFe3t6/ws4QwdhRMK5WxNpb/r2WAeymQD0k9+jKnRda6zh gwyCMNrOifWAwG6vMNGwr+NZA2FHV9/6ecs6jfmKaVfDALjG4u9PW4ZH+GDrEWB8 fwWsWj6e4umicxnbLIqWWwUxxM5PacSSahvpdk22oDjJWK1xuAFZkO/2mhKlnRaS hh27GZgMRd9TxigV4QI/3Q== </Modulus>
<Exponent>Aw==</Exponent>
</RSAKeyValue>
</KeyValue>
<X509Data>
<X509Certificate> MIIGEDCCBPigAwIBAgIIS9+A8qleqEEwDQYJKoZIhvcNAQELBQAwgboxHjAcBgkq hkiG9w0BCQEWD3NvcG9ydGVAaWRvay5jbDEiMCAGA1UEAwwZSURPSyBGSVJNQSBF TEVDVFJPTklDQSBWNDEXMBUGA1UECwwOUlVULTc2NjEwNzE4LTQxIDAeBgNVBAsM F0F1dG9yaWRhZCBDZXJ0aWZpY2Fkb3JhMRkwFwYDVQQKDBBCUE8gQWR2aXNvcnMg U3BBMREwDwYDVQQHDAhTYW50aWFnbzELMAkGA1UEBhMCQ0wwHhcNMjQwMTE4MjEy NzE2WhcNMjYwMTE3MjEyNzE2WjB7MScwJQYDVQQDDB5SSUNBUkRPIEFOVE9OSU8g R09OWkFMRVogR0FFVEUxITAfBgkqhkiG9w0BCQEWEmtyZWFzb2Z0QGdtYWlsLmNv bTETMBEGA1UEBRMKMTEzMTQ3NTUtNTELMAkGA1UEBhMCQ0wxCzAJBgNVBAcMAlJN MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAnMxFllg/ae7Awo2T+2/6 mMFfebVoTC4vBfqV5feMkAQ4YevKqh2nhBtjB4HKhMd4GEVn3O57BTRkjEdQIGy/ lVQBgBdZzaTW8e0YDqIXZQSh9qKRQqL9tQ7nhNl8Cq1eBMJqLInQVvlC0UYmvUEF e3t6/ws4QwdhRMK5WxNpb/r2WAeymQD0k9+jKnRda6zhgwyCMNrOifWAwG6vMNGw r+NZA2FHV9/6ecs6jfmKaVfDALjG4u9PW4ZH+GDrEWB8fwWsWj6e4umicxnbLIqW WwUxxM5PacSSahvpdk22oDjJWK1xuAFZkO/2mhKlnRaShh27GZgMRd9TxigV4QI/ 3QIDAQABo4ICVjCCAlIwCQYDVR0TBAIwADAfBgNVHSMEGDAWgBS73UrbfxA3iHRn RbLKuRKE4MZ4FjCBmAYDVR0gBIGQMIGNMIGKBgorBgEEAYOMHgEEMHwwLAYIKwYB BQUHAgEWIGh0dHBzOi8vcHNjLmlkb2suY2wvb3Blbi9jcHMucGRmMEwGCCsGAQUF BwICMEAePgBDAGUAcgB0AGkAZgBpAGMAYQBkAG8AIABwAGEAcgBhACAAdQBzAG8A IABUAHIAaQBiAHUAdABhAHIAaQBuMIIBEQYDVR0fBIIBCDCCAQQwggEAoDmgN4Y1 aHR0cHM6Ly9wc2MuaWRvay5jbC9vcGVuL0lET0tfRklSTUFfRUxFQ1RST05JQ0Ff NC5jcmyigcKkgb8wgbwxHjAcBgkqhkiG9w0BCQEWD3NvcG9ydGVAaWRvay5jbDEk MCIGA1UEAwwbSURPSyBGSVJNQSBFTEVDVFJPTklDQSAyMDIyMRcwFQYDVQQLDA5S VVQtNzY2MTA3MTgtNDEgMB4GA1UECwwXQXV0b3JpZGFkIENlcnRpZmljYWRvcmEx GTAXBgNVBAoMEEJQTyBBZHZpc29ycyBTcEExETAPBgNVBAcMCFNhbnRpYWdvMQsw CQYDVQQGEwJDTDAdBgNVHQ4EFgQUR1ca1G+NYS4s9jhYXYQDS5D/nDowCwYDVR0P BAQDAgSQMCMGA1UdEgQcMBqgGAYIKwYBBAHBAQKgDBYKNzY2MTA3MTgtNDAjBgNV HREEHDAaoBgGCCsGAQQBwQEBoAwWCjExMzE0NzU1LTUwDQYJKoZIhvcNAQELBQAD ggEBAG1cRq5yYhudo5t+mxvGDH8TbNrWyu7Tbvw8HFqBdQGnfJJu/Q04PGIjZzCz AFpYlT7FEGj6CKm0lsxkdbgTEficazP/XClwu7L6LprhB4HmGywJf9p40NOP/S8r 4NgQqzI9uRLrrnHzSB9pYmP9rTsqXNTXN/GC8faj0pdgSmwwotKcT95CVMHoVTuI irvbOiD7/lAy/znLRKDSDHiiNgCz80+/hkkDYmXuqIgteurC0NZ6NIzC5W3p2SC7 PQt9euX1gmx7a3mmz6aEgJbHjxvFx5+8uCsSEwQXqrXu3hz3mqeeA804bwU9rMIG Cg1jxEvGSraeRRX9btsOAWEZ0hk= </X509Certificate>
</X509Data>
</KeyInfo>
</Signature>
</DTE>
</SetDTE>
<Signature xmlns="http://www.w3.org/2000/09/xmldsig#">
<SignedInfo>
<CanonicalizationMethod Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"/>
<SignatureMethod Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha1"/>
<Reference URI="#IDe7179f61e6ec4e38bef475d79ccccce1">
<Transforms>
<Transform Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"/>
</Transforms>
<DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"/>
<DigestValue>noaoOAowlyXcXRrYNrj3KnfP8X0=</DigestValue>
</Reference>
</SignedInfo>
<SignatureValue> Klgl7PBR7HlU9/0RonVo5Yk7wEqsKmxU5mmhlR2+KblypIh9ES0tOTmxlS1Oid/r Q8INYSw6ZyRV3NoGgT3antTz69hDxYkFJ6+h9hZK/d1YP67OP5xTR+m6zCxl0qQA gRCDPj0Ek9JEdZXIfrA9J8ElPBKgXbdpHzAKSD45SIPm5hyjwyuRE1neuqOvWWCk n2gha6YdzcwZlV7e2qPvwb6id607Tb7ywRX+oI4ZDDdLlSqqr/UEyYhXLSg27/WV ISUQCVTU11mW7ZAPpN+hyI9YzCrbhFW1vyaLyydMx/INYofFl6lUP+pPu/SxaxQq TgOiD21IDy6EuXpr+1F3ew== </SignatureValue>
<KeyInfo>
<KeyValue>
<RSAKeyValue>
<Modulus> mZyNOZGHPazOujYza5bj8qjBUwShdlmdABF+CJO5S1iGAMBXoyb+UTc5tqKaqLQr hxOJxZSZwpuMVbc2cJ+JtDwXsEj2asqB9GXjHGUH4HhJu7PI7qWw2YivtQm2p4R3 hsd+un1QECsfAyL8DQ4v8ulm7URFuOimYA8YK2ML8EmiBJ2AzXu9MTxIUBUkhxsv A3tffFuDudOtIK12FpHSM0jseAFvZJY7HSfV/oybdeUDeKX10rrgnIrsOHfwZQ9E TQ3lzbTZms1WCu40cG30aMn1o8c0TLMdfNPT8f2PULshH4TuykwHli4MVk8LD2TR 4hDdNt6JK2BUQJT2VeL8Fw== </Modulus>
<Exponent>AQAB</Exponent>
</RSAKeyValue>
</KeyValue>
<X509Data>
<X509Certificate> MIIGEDCCBPigAwIBAgIINo2mVCGpjRYwDQYJKoZIhvcNAQELBQAwgboxHjAcBgkq hkiG9w0BCQEWD3NvcG9ydGVAaWRvay5jbDEiMCAGA1UEAwwZSURPSyBGSVJNQSBF TEVDVFJPTklDQSBWMjEXMBUGA1UECwwOUlVULTc2NjEwNzE4LTQxIDAeBgNVBAsM F0F1dG9yaWRhZCBDZXJ0aWZpY2Fkb3JhMRkwFwYDVQQKDBBCUE8gQWR2aXNvcnMg U3BBMREwDwYDVQQHDAhTYW50aWFnbzELMAkGA1UEBhMCQ0wwHhcNMjIwNTIzMjI0 OTM1WhcNMjUwNTIyMjI0OTM1WjB9MSgwJgYDVQQDDB9DUklTVElBTiBVTUlTRVMg Uk9KU0FTIEdVVElFUlJFWjEiMCAGA1UECQEWEmNyb2phc0BnZGV4cHJlc3MuY2wx EzARBgNVBAUTCjEwOTc0Mzc3LTExCzAJBgNVBAYTAkNMMSwwKgYDVQQHDANSTTCC ASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAJmcjTmRhz2szro2M2uW4/Kow VMEoXZZnQARfgiTuUtYhgDAV6Mm/lE3ObaioqitCuHE4nFlJnCm4xVtzZwn4m0PBew SPZqyoH0ZeMcZQfgeEm7s8jupbDZiK+1CbanhHeGx366fVAQKx8DIvwNDi/y6WbtRE W46KZgDxgrYwvwSaIEnYDNe70xPEhQFSSHGy8De198W4O5060grXYWkdIzSOx4AW9k ljsdJ9X+jJt15QN4pfXSuuCciuw4d/BlD0RNDeXNtNmazVYK7jRwbfRoyfWjxzVMsx18 09Px/Y9QuyEfhO7KTAeWLgxWTwsPZNHiEN023okrYFRAlPZV4vwXAgMBAAGjggJUMIIC UDAJBgNVHRMEAjAAMB8GA1UdIwQYMBaAFPBsM7+sl5NYeqHgzp7s6N77ZT76MIGYBgNV HSAEgZAwgY0wgYoGCisGAQQBg4weAQQwfDAsBggrBgEFBQcCARYgaHR0cHM6Ly9wc2Mu aWRvay5jbC9vcGVuL2Nwcy5wZGYwTAYIKwYBBQUHAgIwQB4+AEMAZQByAHQAYQBpAGY AawBhAGQAbwAgAHAAYQByAGEAIAB1AHMAbyAgAFQAcgBpAGIAdQB0AGEAcgBpAG8wggEP BgNVHR8EggEGMIIBAjCB/6A6oDiGNmh0dHBzOi8vcHNjLmlkb2suY2wvb3Blbi9JRE9L X0ZJUk1BX1YyLmNybKKBwKSBvTCBujEeMBwGCSqGSIb3DQEJAQYPc29wb3J0ZUBpZG9r LmNsMSIwIAYDVQQDDBlJRE9LIEZJUk1BIEVMRUNUUk9OSUNBIFYyMRcwFQYDVQQLDA5S VVQtNzY2MTA3MTgtNDEgMB4GA1UECwwXQXV0b3JpZGFkIENlcnRpZmljYWRvcmExGTAX BgNVBAoMEEJQTyBBZHZpc29ycyBTcEExETAPBgNVBAcMCFNhbnRpYWdvMQswCQYDVQQG EwJDTDAdBgNVHQ4EFgQUnR78AetPsNDqFh+h8AeExJY4aOgwCwYDVR0PBAQDAgSQMCMG A1UdEgQcMBqgGAYIKwYBBAHBAQKgDBYKNzY2MTA3MTgtNDAjBgNVHREEHDAaoBgGCCsGA QQBwQEBoAwWCjEwOTc0Mzc3LTUwDQYJKoZIhvcNAQELBQADggEBAA6KTv23rQSdvQrJMy1j xE/+gYgMDsPqx6VcSRrsDVl+tUjf4Bld1zBLmBakdtMPiyNhQ0kaOgEjo3QU8kQ/SV6fWysn mwwAutagLJvX5cix9YPrhAnGxe31kdR7nj8h/xMTetxxgmOQ/+sKwM6GDPCyzVMZ0JuXr9rn 3ozViDx0+Lu1tegCE0CMZgLilynwZXrtR5bjbJH01QrxErY8GoFIY7BO8Iah/iBS0SfClWYaE H6JOjcGUSIwDapa3Th0+GYEUgSektb8aHqyl2XEDJtAem4PSWmsdOBZZaXA07eUVxI20qq4F eKdl38Mit/WiFQvQ0chqv6iEPJZqx/3FVIU= </X509Certificate>
</X509Data>
</KeyInfo>
</Signature>
</EnvioDTE>"""

def print_header(title):
    print("\n" + "=" * 80)
    print(title.center(80))
    print("=" * 80)

def diagnosticar_error_500():
    """
    Diagnostica el error 500 analizando el request completo
    """
    print_header("DIAGNÓSTICO DEL ERROR 500")
    
    try:
        # Obtener empresa
        empresa = Empresa.objects.filter(dtebox_habilitado=True).first()
        if not empresa:
            empresa = Empresa.objects.first()
        
        # Configurar DTEBox
        empresa.dtebox_habilitado = True
        empresa.dtebox_url = "http://200.6.118.43/api/Core.svc/Core"
        empresa.dtebox_auth_key = "0a1c295d-7853-4e2e-ac90-d7d2fd46ecf0"
        empresa.dtebox_ambiente = "P"
        empresa.resolucion_numero = 80
        from datetime import date
        empresa.resolucion_fecha = date(2014, 8, 22)
        empresa.save()
        
        print(f"\n1. DATOS DE CONFIGURACIÓN:")
        print(f"   Empresa: {empresa.nombre}")
        print(f"   RUT: {empresa.rut}")
        print(f"   URL DTEBox: {empresa.dtebox_url}")
        print(f"   Auth Key: {empresa.dtebox_auth_key[:20]}...")
        print(f"   Ambiente: {empresa.dtebox_ambiente}")
        print(f"   Resolución: N° {empresa.resolucion_numero} del {empresa.resolucion_fecha.strftime('%d-%m-%Y')}")
        
        print(f"\n2. ANÁLISIS DEL XML ORIGINAL:")
        print(f"   Tamaño: {len(XML_REAL)} caracteres")
        print(f"   Primeros 200 caracteres:")
        print(f"   {XML_REAL[:200]}...")
        print(f"   ¿Contiene EnvioDTE?: {'EnvioDTE' in XML_REAL}")
        print(f"   ¿Contiene TED?: {'<TED' in XML_REAL}")
        print(f"   ¿Contiene Signature?: {'<Signature' in XML_REAL}")
        
        # Codificar XML en Base64
        try:
            xml_bytes = XML_REAL.encode('ISO-8859-1')
            encoding_usado = 'ISO-8859-1'
        except UnicodeEncodeError:
            xml_bytes = XML_REAL.encode('UTF-8')
            encoding_usado = 'UTF-8'
        
        documento_base64 = base64.b64encode(xml_bytes).decode('utf-8')
        
        print(f"\n3. CODIFICACIÓN BASE64:")
        print(f"   Encoding usado: {encoding_usado}")
        print(f"   Tamaño Base64: {len(documento_base64)} caracteres")
        print(f"   Primeros 100 caracteres Base64:")
        print(f"   {documento_base64[:100]}...")
        
        # Construir request XML
        resolution_date = empresa.resolucion_fecha.strftime('%Y-%m-%d')
        resolution_number = empresa.resolucion_numero
        
        root = ET.Element("SendDocumentAsXMLRequest")
        root.set("xmlns", "http://gdexpress.cl/api")
        ET.SubElement(root, "Environment").text = str(empresa.dtebox_ambiente)
        ET.SubElement(root, "Content").text = documento_base64
        ET.SubElement(root, "ResolutionDate").text = resolution_date
        ET.SubElement(root, "ResolutionNumber").text = str(int(resolution_number))
        
        # PDF417 (opcionales - vacíos)
        ET.SubElement(root, "PDF417Columns")
        ET.SubElement(root, "PDF417Level")
        ET.SubElement(root, "PDF417Type")
        ET.SubElement(root, "TED")  # Vacío para reenvío
        
        xml_request_str = ET.tostring(root, encoding='unicode', method='xml')
        xml_request = xml_request_str.encode('utf-8')
        
        print(f"\n4. REQUEST XML CONSTRUIDO:")
        print(f"   Tamaño: {len(xml_request)} bytes")
        print(f"   XML completo:")
        print(xml_request_str)
        
        # Headers
        headers_xml = {
            'AuthKey': empresa.dtebox_auth_key,
            'Content-Type': 'application/xml',
            'Accept': 'application/xml'
        }
        
        print(f"\n5. HEADERS:")
        for key, value in headers_xml.items():
            if key == 'AuthKey':
                print(f"   {key}: {value[:20]}...")
            else:
                print(f"   {key}: {value}")
        
        # URL
        url = "http://200.6.118.43/api/core.svc/core/SendDocumentAsXML"
        print(f"\n6. URL:")
        print(f"   {url}")
        
        # Realizar solicitud
        print(f"\n7. ENVIANDO REQUEST...")
        response = requests.post(
            url,
            data=xml_request,
            headers=headers_xml,
            timeout=30,
            verify=False
        )
        
        print(f"\n8. RESPUESTA DEL SERVIDOR:")
        print(f"   Status Code: {response.status_code}")
        print(f"   Content-Type: {response.headers.get('Content-Type', 'N/A')}")
        print(f"   Content-Length: {len(response.content)} bytes")
        print(f"\n   Respuesta completa:")
        print(f"   {response.text}")
        
        # Intentar parsear el error SOAP
        if response.status_code == 500:
            print(f"\n9. ANÁLISIS DEL ERROR SOAP:")
            try:
                root_error = ET.fromstring(response.text)
                # Buscar detalles del error
                fault_code = root_error.find('.//{http://schemas.microsoft.com/ws/2005/05/envelope/none}Code/{http://schemas.microsoft.com/ws/2005/05/envelope/none}Value')
                fault_subcode = root_error.find('.//{http://schemas.microsoft.com/ws/2005/05/envelope/none}Subcode/{http://schemas.microsoft.com/ws/2005/05/envelope/none}Value')
                fault_reason = root_error.find('.//{http://schemas.microsoft.com/ws/2005/05/envelope/none}Reason/{http://schemas.microsoft.com/ws/2005/05/envelope/none}Text')
                
                if fault_code is not None:
                    print(f"   Código de error: {fault_code.text}")
                if fault_subcode is not None:
                    print(f"   Subcódigo: {fault_subcode.text}")
                if fault_reason is not None:
                    print(f"   Razón: {fault_reason.text}")
            except Exception as e:
                print(f"   No se pudo parsear el error SOAP: {e}")
        
        print(f"\n10. POSIBLES CAUSAS DEL ERROR 500:")
        print(f"   a) El documento ya está timbrado y DTEBox no permite reenviarlo")
        print(f"   b) El formato del XML request no es el esperado")
        print(f"   c) El XML completo (EnvioDTE) no es válido para reenvío")
        print(f"   d) DTEBox espera solo el elemento <Documento> sin el wrapper <EnvioDTE>")
        print(f"   e) El campo TED debe estar vacío pero el servidor lo está validando")
        print(f"   f) Problema interno del servidor DTEBox")
        
        print(f"\n11. RECOMENDACIONES:")
        print(f"   - Intentar enviar solo el elemento <Documento> sin <EnvioDTE>")
        print(f"   - Verificar si DTEBox tiene un endpoint diferente para reenvío")
        print(f"   - Consultar la documentación de DTEBox sobre reenvío de documentos")
        print(f"   - Verificar si el documento puede ser reenviado (puede estar bloqueado)")
        
    except Exception as e:
        print(f"\n[ERROR] Error inesperado: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    diagnosticar_error_500()






