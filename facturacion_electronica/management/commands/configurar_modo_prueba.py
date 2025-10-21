"""
Comando para configurar el modo de reutilización de folios para pruebas
Esto permite reutilizar los mismos folios múltiples veces en ambiente de certificación
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from empresas.models import Empresa


class Command(BaseCommand):
    help = 'Configura el modo de reutilización de folios para pruebas de facturación electrónica'

    def add_arguments(self, parser):
        parser.add_argument(
            '--empresa',
            type=int,
            help='ID de empresa específica (opcional, usa la primera empresa por defecto)'
        )
        parser.add_argument(
            '--habilitar',
            action='store_true',
            help='Habilitar el modo de reutilización de folios'
        )
        parser.add_argument(
            '--deshabilitar',
            action='store_true',
            help='Deshabilitar el modo de reutilización de folios'
        )
        parser.add_argument(
            '--estado',
            action='store_true',
            help='Mostrar el estado actual del modo de reutilización'
        )

    def handle(self, *args, **options):
        # Si solo quiere ver el estado
        if options['estado']:
            self.mostrar_estado()
            return

        # Si no especifica habilitar o deshabilitar, mostrar ayuda
        if not options['habilitar'] and not options['deshabilitar']:
            self.stdout.write(self.style.WARNING('Debe especificar --habilitar o --deshabilitar'))
            return

        # Obtener empresa
        if options['empresa']:
            try:
                empresa = Empresa.objects.get(id=options['empresa'])
            except Empresa.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Empresa con ID {options["empresa"]} no encontrada'))
                return
        else:
            empresa = Empresa.objects.first()
            if not empresa:
                self.stdout.write(self.style.ERROR('No se encontraron empresas en el sistema'))
                return

        # Configurar el modo
        if options['habilitar']:
            self.habilitar_modo_prueba(empresa)
        elif options['deshabilitar']:
            self.deshabilitar_modo_prueba(empresa)

    def mostrar_estado(self):
        """Muestra el estado actual del modo de reutilización"""
        empresas = Empresa.objects.all()

        if not empresas:
            self.stdout.write(self.style.WARNING('No hay empresas configuradas'))
            return

        self.stdout.write(self.style.SUCCESS('Estado del Modo de Reutilización de Folios:'))
        self.stdout.write('-' * 50)

        for empresa in empresas:
            modo_prueba = empresa.modo_reutilizacion_folios
            ambiente = empresa.get_ambiente_sii_display()

            self.stdout.write(f"\nEmpresa: {empresa.nombre}")
            self.stdout.write(f"   Ambiente SII: {ambiente}")
            self.stdout.write(f"   Reutilización de folios: {'HABILITADO' if modo_prueba else 'DESHABILITADO'}")

            if modo_prueba:
                self.stdout.write(self.style.WARNING("   ADVERTENCIA: Los folios se reutilizarán automáticamente"))

    def habilitar_modo_prueba(self, empresa):
        """Habilita el modo de reutilización de folios"""
        empresa.modo_reutilizacion_folios = True
        empresa.save()

        self.stdout.write(self.style.SUCCESS(f"Modo de reutilización de folios HABILITADO para: {empresa.nombre}"))
        self.stdout.write(self.style.WARNING("Ahora puede generar múltiples documentos con los mismos folios"))
        self.stdout.write(self.style.WARNING("   Solo funciona en ambiente de certificación"))
        self.stdout.write(self.style.WARNING("   Recuerde deshabilitar antes de pasar a producción"))

    def deshabilitar_modo_prueba(self, empresa):
        """Deshabilita el modo de reutilización de folios"""
        empresa.modo_reutilizacion_folios = False
        empresa.save()

        self.stdout.write(self.style.SUCCESS(f"Modo de reutilización de folios DESHABILITADO para: {empresa.nombre}"))
        self.stdout.write(self.style.SUCCESS("Ahora cada documento consumirá un folio único"))
