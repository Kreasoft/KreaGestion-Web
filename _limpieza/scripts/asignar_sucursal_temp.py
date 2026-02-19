from facturacion_electronica.models import ArchivoCAF
from empresas.models import Sucursal

# Buscar CAFs sin sucursal
cafs_sin_sucursal = ArchivoCAF.objects.filter(sucursal__isnull=True)
print(f'CAFs sin sucursal: {cafs_sin_sucursal.count()}')

# Obtener empresas únicas
empresas_ids = cafs_sin_sucursal.values_list('empresa_id', flat=True).distinct()

# Para cada empresa, asignar la casa matriz
for empresa_id in empresas_ids:
    # Buscar casa matriz
    sucursal = Sucursal.objects.filter(
        empresa_id=empresa_id, 
        es_principal=True
    ).first()
    
    # Si no hay casa matriz, tomar primera sucursal
    if not sucursal:
        sucursal = Sucursal.objects.filter(empresa_id=empresa_id).first()
    
    if sucursal:
        # Actualizar CAFs
        count = ArchivoCAF.objects.filter(
            empresa_id=empresa_id, 
            sucursal__isnull=True
        ).update(sucursal=sucursal)
        print(f'✓ {count} CAFs asignados a {sucursal.nombre}')
    else:
        print(f'✗ No se encontró sucursal para empresa ID {empresa_id}')

print('\nProceso completado')
