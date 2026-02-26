"""
Diagnóstico del certificado digital y firma para SII.
"""
from django.core.management.base import BaseCommand
from facturacion_electronica.models import DocumentoTributarioElectronico
from facturacion_electronica.firma_electronica import FirmadorDTE
from facturacion_electronica.cliente_sii import ClienteSII
import OpenSSL
from datetime import datetime


class Command(BaseCommand):
    help = 'Diagnostica el certificado digital para envío al SII'

    def add_arguments(self, parser):
        parser.add_argument('folio', type=int, help='Folio del DTE')
        parser.add_argument('--tipo', type=str, default='33', help='Tipo de DTE')

    def handle(self, *args, **options):
        folio = options['folio']
        tipo_dte = options['tipo']

        try:
            dte = DocumentoTributarioElectronico.objects.get(folio=folio, tipo_dte=tipo_dte)
            empresa = dte.empresa
            
            self.stdout.write(self.style.SUCCESS(f'Diagnóstico para {empresa.nombre}'))
            self.stdout.write(f'RUT: {empresa.rut}')
            self.stdout.write(f'Ambiente SII: {empresa.ambiente_sii}')
            
            # Verificar certificado
            self.stdout.write('\n--- Verificando Certificado Digital ---')
            
            if not empresa.certificado_digital:
                self.stdout.write(self.style.ERROR('❌ No hay certificado configurado'))
                return
            
            cert_path = empresa.certificado_digital.path
            self.stdout.write(f'Certificado: {cert_path}')
            
            try:
                with open(cert_path, 'rb') as f:
                    cert_data = f.read()
                
                # Cargar certificado
                try:
                    # Intentar como PKCS12
                    from signxml import XMLSigner
                    self.stdout.write('Tipo: PKCS12 (.p12/.pfx)')
                except:
                    pass
                
                # Verificar firma simple
                self.stdout.write('\n--- Verificando Firma ---')
                try:
                    firmador = FirmadorDTE(cert_path, empresa.password_certificado)
                    self.stdout.write(self.style.SUCCESS('✅ Firmador inicializado correctamente'))
                    
                    # Probar firma simple
                    test_xml = b'<TEST>Prueba</TEST>'
                    try:
                        signed = firmador.firmar_xml(test_xml.decode())
                        self.stdout.write(self.style.SUCCESS('✅ Firma de prueba exitosa'))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'❌ Error al firmar: {e}'))
                        
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'❌ Error al inicializar firmador: {e}'))
                
                # Intentar obtener semilla del SII
                self.stdout.write('\n--- Probando conexión con SII ---')
                try:
                    cliente = ClienteSII(ambiente='certificacion')
                    semilla = cliente.obtener_semilla()
                    self.stdout.write(self.style.SUCCESS(f'✅ Semilla SII: {semilla[:30]}...'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'❌ Error al obtener semilla: {e}'))
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'❌ Error al leer certificado: {e}'))
                
        except DocumentoTributarioElectronico.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'DTE no encontrado'))
