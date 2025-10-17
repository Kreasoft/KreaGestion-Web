from articulos.models import HomologacionCodigo

print('=' * 50)
print('VERIFICANDO HOMOLOGACIONES EN LA BASE DE DATOS')
print('=' * 50)

total = HomologacionCodigo.objects.count()
print(f'\nTotal de homologaciones: {total}')

if total > 0:
    print('\nLista de homologaciones:')
    print('-' * 50)
    for h in HomologacionCodigo.objects.all():
        print(f'ID: {h.id}')
        print(f'  Artículo: {h.articulo.codigo} - {h.articulo.nombre}')
        print(f'  Proveedor: {h.proveedor.nombre}')
        print(f'  Código Proveedor: {h.codigo_proveedor}')
        print(f'  Precio: ${h.precio_compra:,}')
        print(f'  Principal: {"Sí" if h.es_principal else "No"}')
        print(f'  Activo: {"Sí" if h.activo else "No"}')
        print('-' * 50)
else:
    print('\n❌ No hay homologaciones en la base de datos')
