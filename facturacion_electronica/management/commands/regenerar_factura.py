"""
Comando para regenerar XML de una factura específica y reenviarla a DTEBox.
Según documentación GDExpress: Enviar DTE como XML completo en Base64.
"""
from django.core.management.base import BaseCommand
from facturacion_electronica.models import DocumentoTributarioElectronico
from facturacion_electronica.dte_service import DTEService
import urllib.request
import urllib.error
import base64
import json


class Command(BaseCommand):
    help = 'Regenera XML de una factura y la reenvía a DTEBox'

    def add_arguments(self, parser):
        parser.add_argument('folio', type=int, help='Folio de la factura a regenerar')
        parser.add_argument(
            '--enviar',
            action='store_true',
            help='Enviar automáticamente a DTEBox después de regenerar',
        )

    def handle(self, *args, **options):
        folio = options['folio']
        enviar = options['enviar']

        try:
            dte = DocumentoTributarioElectronico.objects.get(folio=folio, tipo_dte='33')
            self.stdout.write(self.style.SUCCESS(f'Factura {folio} encontrada (ID: {dte.id})'))
            
            # Regenerar XML
            self.stdout.write('Regenerando XML...')
            service = DTEService(dte.empresa)
            service.procesar_dte_existente(dte)
            dte.refresh_from_db()
            self.stdout.write(self.style.SUCCESS(f'XML regenerado ({len(dte.xml_dte or "")} bytes)'))
            
            if enviar:
                self.stdout.write('Enviando a DTEBox según documentación GDExpress...')
                emp = dte.empresa
                
                # Preparar XML DTE completo (sin firma, como indica GDExpress)
                xml_dte = dte.xml_dte or ''
                
                # Codificar a Base64 (como muestra la documentación)
                xml_bytes = xml_dte.encode('ISO-8859-1', errors='replace')
                content_b64 = base64.b64encode(xml_bytes).decode('ascii')
                
                # URL según documentación GDExpress
                url_base = emp.dtebox_url.strip().rstrip('/')
                url_envio = f"{url_base}/api/Core.svc/core/SendDocumentAsXML"
                
                self.stdout.write(f'URL: {url_envio}')
                self.stdout.write(f'XML DTE ({len(xml_dte)} bytes) -> Base64 ({len(content_b64)} chars)')
                
                # XML Request según documentación GDExpress (campos PDF417 vacíos)
                xml_request = f'''<?xml version="1.0" encoding="utf-8"?>
<SendDocumentAsXMLRequest xmlns="http://gdexpress.cl/api">
  <Environment>T</Environment>
  <Content>{content_b64}</Content>
  <ResolutionDate>2014-08-22</ResolutionDate>
  <ResolutionNumber>0</ResolutionNumber>
  <PDF417Columns></PDF417Columns>
  <PDF417Level></PDF417Level>
  <PDF417Type></PDF417Type>
  <TED></TED>
</SendDocumentAsXMLRequest>'''
                
                headers = {
                    'AuthKey': emp.dtebox_auth_key,
                    'Content-Type': 'application/xml',
                    'Accept': 'application/xml'
                }
                
                self.stdout.write('\n--- Enviando a DTEBox (XML) ---')
                req = urllib.request.Request(url_envio, data=xml_request.encode('utf-8'), headers=headers, method='POST')
                
                try:
                    with urllib.request.urlopen(req, timeout=60) as response:
                        resp_body = response.read().decode('utf-8', errors='ignore')
                        self.stdout.write(self.style.SUCCESS(f'✅ Respuesta HTTP {response.status}'))
                        self.stdout.write(f'Body: {resp_body[:500]}')
                        
                        # Verificar resultado
                        if '<Result>0</Result>' in resp_body:
                            self.stdout.write(self.style.SUCCESS('✅ DTE enviado exitosamente (Result=0)'))
                        else:
                            self.stdout.write(self.style.WARNING('⚠️ Resultado no exitoso'))
                            
                except urllib.error.HTTPError as e:
                    error_body = e.read().decode('utf-8', errors='ignore')
                    self.stdout.write(self.style.ERROR(f'❌ HTTP Error {e.code}:'))
                    self.stdout.write(self.style.ERROR(error_body[:1500]))
                    
                    # Reintentar con JSON
                    self.stdout.write('\n--- Reintentando con formato JSON ---')
                    try:
                        payload_json = {
                            "Environment": "T",
                            "Content": content_b64,
                            "ResolutionDate": "2014-08-22",
                            "ResolutionNumber": "0",
                            "PDF417Columns": "",
                            "PDF417Level": "",
                            "PDF417Type": "",
                            "TED": ""
                        }
                        
                        headers_json = {
                            'AuthKey': emp.dtebox_auth_key,
                            'Content-Type': 'application/json',
                            'Accept': 'application/json'
                        }
                        
                        req_json = urllib.request.Request(url_envio, data=json.dumps(payload_json).encode('utf-8'), headers=headers_json, method='POST')
                        
                        with urllib.request.urlopen(req_json, timeout=60) as response:
                            resp_json = response.read().decode('utf-8', errors='ignore')
                            self.stdout.write(self.style.SUCCESS(f'✅ JSON Respuesta HTTP {response.status}'))
                            self.stdout.write(f'Body: {resp_json[:500]}')
                    except Exception as e2:
                        self.stdout.write(self.style.ERROR(f'❌ JSON también falló: {str(e2)}'))
                        
            else:
                self.stdout.write(self.style.WARNING('Para enviar a DTEBox, agrega --enviar al comando'))
                
        except DocumentoTributarioElectronico.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Factura {folio} no encontrada'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
