"""
Comando para crear sucursales principales y bodegas para empresas existentes
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from empresas.models import Empresa, Sucursal
from inventario.models import Bodega


class Command(BaseCommand):
    help = 'Crea sucursales principales y bodegas para empresas que no las tienen'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Iniciando creación de sucursales principales...'))
        
        empresas_sin_sucursal = []
        empresas_procesadas = 0
        
        # Buscar empresas sin sucursal principal
        for empresa in Empresa.objects.all():
            if not empresa.sucursales.filter(es_principal=True).exists():
                empresas_sin_sucursal.append(empresa)
        
        if not empresas_sin_sucursal:
            self.stdout.write(self.style.SUCCESS('✓ Todas las empresas ya tienen sucursal principal'))
            return
        
        self.stdout.write(f'Encontradas {len(empresas_sin_sucursal)} empresas sin sucursal principal')
        
        # Procesar cada empresa
        for empresa in empresas_sin_sucursal:
            try:
                with transaction.atomic():
                    self.stdout.write(f'\nProcesando: {empresa.nombre}')
                    
                    # Crear sucursal principal
                    sucursal = Sucursal.objects.create(
                        empresa=empresa,
                        codigo='001',
                        nombre='Casa Matriz',
                        direccion=empresa.direccion,
                        comuna=empresa.comuna,
                        ciudad=empresa.ciudad,
                        region=empresa.region,
                        telefono=empresa.telefono,
                        email=empresa.email,
                        es_principal=True,
                        estado='activa'
                    )
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Sucursal creada: {sucursal.nombre}'))
                    
                    # Crear bodega principal
                    bodega = Bodega.objects.create(
                        empresa=empresa,
                        sucursal=sucursal,
                        nombre='Bodega Principal',
                        codigo='BOD-001',
                        descripcion='Bodega principal de la casa matriz',
                        direccion=empresa.direccion,
                        es_principal=True,
                        activo=True
                    )
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Bodega creada: {bodega.nombre}'))
                    
                    empresas_procesadas += 1
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✗ Error procesando {empresa.nombre}: {str(e)}'))
        
        self.stdout.write(self.style.SUCCESS(f'\n✓ Proceso completado: {empresas_procesadas}/{len(empresas_sin_sucursal)} empresas procesadas'))
