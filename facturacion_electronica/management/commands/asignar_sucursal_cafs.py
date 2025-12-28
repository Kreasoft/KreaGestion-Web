"""
Management command para asignar sucursal casa matriz a CAFs sin sucursal
"""
from django.core.management.base import BaseCommand
from facturacion_electronica.models import ArchivoCAF
from empresas.models import Sucursal


class Command(BaseCommand):
    help = 'Asigna la sucursal casa matriz a todos los CAFs que no tienen sucursal asignada'

    def handle(self, *args, **options):
        # Obtener CAFs sin sucursal
        cafs_sin_sucursal = ArchivoCAF.objects.filter(sucursal__isnull=True)
        total = cafs_sin_sucursal.count()
        
        if total == 0:
            self.stdout.write(self.style.SUCCESS('✓ Todos los CAFs ya tienen sucursal asignada'))
            return
        
        self.stdout.write(f'\nEncontr ados {total} CAFs sin sucursal')
        self.stdout.write('Asignando sucursal casa matriz...\n')
        
        actualizados = 0
        errores = 0
        
        for caf in cafs_sin_sucursal:
            try:
                # Buscar la sucursal casa matriz de la empresa del CAF
                sucursal_matriz = Sucursal.objects.filter(
                    empresa=caf.empresa,
                    es_principal=True
                ).first()
                
                if not sucursal_matriz:
                    # Si no existe casa matriz, tomar la primera sucursal
                    sucursal_matriz = Sucursal.objects.filter(empresa=caf.empresa).first()
                
                if sucursal_matriz:
                    caf.sucursal = sucursal_matriz
                    caf.save(update_fields=['sucursal'])
                    actualizados += 1
                    self.stdout.write(
                        f'  ✓ CAF {caf.id} ({caf.get_tipo_documento_display()} {caf.folio_desde}-{caf.folio_hasta}) '
                        f'→ {sucursal_matriz.nombre}'
                    )
                else:
                    errores += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f'  ✗ CAF {caf.id}: No se encontró sucursal para empresa {caf.empresa.nombre}'
                        )
                    )
            except Exception as e:
                errores += 1
                self.stdout.write(
                    self.style.ERROR(f'  ✗ Error en CAF {caf.id}: {str(e)}')
                )
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS(f'✓ CAFs actualizados: {actualizados}'))
        if errores > 0:
            self.stdout.write(self.style.ERROR(f'✗ Errores: {errores}'))
        self.stdout.write('='*60 + '\n')
