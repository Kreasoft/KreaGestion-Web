"""
Diagnóstico del certificado digital
"""
from django.core.management.base import BaseCommand
from facturacion_electronica.models import DocumentoTributarioElectronico
from facturacion_electronica.firma_electronica import FirmadorDTE


class Command(BaseCommand):
    help = 'Verifica el certificado digital'

    def add_arguments(self, parser):
        parser.add_argument('folio', type=int, help='Folio del DTE')
        parser.add_argument('--tipo', type=str, default='33', help='Tipo de DTE')

    def handle(self, *args, **options):
        folio = options['folio']
        tipo_dte = options['tipo']

        try:
            dte = DocumentoTributarioElectronico.objects.get(folio=folio, tipo_dte=tipo_dte)
            empresa = dte.empresa
            
            self.stdout.write('=== INFORMACIÓN DEL CERTIFICADO ===')
            self.stdout.write(f'Ruta: {empresa.certificado_digital.path}')
            
            try:
                firmador = FirmadorDTE(empresa.certificado_digital.path, empresa.password_certificado)
                info = firmador.obtener_info_certificado()
                
                self.stdout.write(f'Subject: {info["subject"]}')
                self.stdout.write(f'Issuer: {info["issuer"]}')
                self.stdout.write(f'Válido desde: {info["not_valid_before"]}')
                self.stdout.write(f'Válido hasta: {info["not_valid_after"]}')
                
                if info['is_valid']:
                    from datetime import datetime, timezone
                    dias = (info['not_valid_after'] - datetime.now(timezone.utc)).days
                    self.stdout.write(self.style.SUCCESS(f'✅ Certificado vigente ({dias} días restantes)'))
                else:
                    self.stdout.write(self.style.ERROR('❌ Certificado EXPIRADO'))
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error al cargar certificado: {e}'))
                
        except DocumentoTributarioElectronico.DoesNotExist:
            self.stdout.write(self.style.ERROR('DTE no encontrado'))
