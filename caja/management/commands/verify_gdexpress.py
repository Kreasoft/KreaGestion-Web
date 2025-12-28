import os
from django.core.management.base import BaseCommand
from django.conf import settings
from dte_gdexpress import GeneradorFactura, Firmador, ClienteGDExpress, GestorCAF
from dte_gdexpress.utils import validar_rut

class Command(BaseCommand):
    help = 'Verifica la instalación de DTE GDExpress'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("=== Iniciando Pruebas de Instalación DTE GDExpress ==="))
        
        # 1. Test RUT
        self.stdout.write("\n[1] Probando validación de RUT...")
        rut_prueba = '77117239-3'
        es_valido = validar_rut(rut_prueba)
        self.stdout.write(f"RUT {rut_prueba} es válido: {es_valido}")
        
        if es_valido:
            self.stdout.write(self.style.SUCCESS("✅ Validación de RUT OK"))
        else:
            self.stdout.write(self.style.ERROR("❌ Validación de RUT falló"))

        # 2. Test Configuración
        self.stdout.write("\n[2] Verificando Configuración...")
        try:
            config_dte = getattr(settings, 'DTE_GDEXPRESS', None)
            if config_dte:
                self.stdout.write(self.style.SUCCESS(f"✅ Configuración encontrada in settings.py"))
                self.stdout.write(f"   Ambiente: {config_dte.get('AMBIENTE')}")
                self.stdout.write(f"   URL Servicio: {config_dte.get('URL_SERVICIO')}")
                
                # Verificar directorios
                caf_dir = config_dte.get('CAF_DIRECTORY')
                cert_path = config_dte.get('CERTIFICADO_PATH')
                
                if os.path.exists(caf_dir):
                    self.stdout.write(self.style.SUCCESS(f"✅ Directorio CAF existe: {caf_dir}"))
                else:
                    self.stdout.write(self.style.WARNING(f"⚠️ Directorio CAF no existe: {caf_dir}"))
                    
                # Verificar carpetas creadas
                cert_dir = os.path.dirname(cert_path)
                if os.path.exists(cert_dir):
                     self.stdout.write(self.style.SUCCESS(f"✅ Directorio Certificados existe: {cert_dir}"))
                else:
                     self.stdout.write(self.style.WARNING(f"⚠️ Directorio Certificados no existe: {cert_dir}"))

            else:
                self.stdout.write(self.style.ERROR("❌ Configuración DTE_GDEXPRESS no encontrada en settings.py"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error al leer configuración: {e}"))

        # 3. Test Importación de Clases
        self.stdout.write("\n[3] Verificando importación de clases principales...")
        try:
            self.stdout.write(self.style.SUCCESS(f"✅ GeneradorFactura: {GeneradorFactura}"))
            self.stdout.write(self.style.SUCCESS(f"✅ Firmador: {Firmador}"))
            self.stdout.write(self.style.SUCCESS(f"✅ ClienteGDExpress: {ClienteGDExpress}"))
            self.stdout.write(self.style.SUCCESS(f"✅ GestorCAF: {GestorCAF}"))
        except NameError as e:
            self.stdout.write(self.style.ERROR(f"❌ Error de importación: {e}"))

        self.stdout.write(self.style.SUCCESS("\n=== Pruebas Finalizadas ==="))
