from ventas.models import Venta
from facturacion_electronica.models import DocumentoTributarioElectronico, ArchivoCAF

print('\n' + '='*80)
print('ESTADO ACTUAL DE GUÍAS DE DESPACHO')
print('='*80)

# CAF
caf = ArchivoCAF.objects.filter(tipo_documento='52', estado='activo').first()
if caf:
    print(f'\nCAF Guías:')
    print(f'  Rango: {caf.folio_desde} - {caf.folio_hasta}')
    print(f'  Folio actual: {caf.folio_actual}')
    print(f'  Disponibles: {caf.folio_hasta - caf.folio_actual + 1}')

# Ventas tipo guía
print(f'\nVentas tipo guía en base de datos:')
guias_venta = Venta.objects.filter(tipo_documento='guia').order_by('numero_venta')
print(f'  Total: {guias_venta.count()}')

# DTEs tipo 52
print(f'\nDTEs tipo 52 (Guías) en base de datos:')
try:
    dtes_guia = list(DocumentoTributarioElectronico.objects.filter(tipo_documento='52').values_list('folio', flat=True).order_by('folio'))
    print(f'  Total DTEs: {len(dtes_guia)}')
    
    if dtes_guia:
        print(f'  Folios usados: {dtes_guia}')
        ultimo_folio = max(dtes_guia)
        siguiente_disponible = ultimo_folio + 1
        print(f'\n  Último folio usado: {ultimo_folio}')
        print(f'  Siguiente disponible: {siguiente_disponible}')
        
        print('\n' + '='*80)
        print('RECOMENDACIÓN:')
        print('='*80)
        print(f'Ajustar folio_actual a: {siguiente_disponible}')
        print(f'(En el mantenedor de CAF, usa el botón "Ajustar Folio")')
    else:
        print('\n  No hay DTEs de guías emitidos')
        print('\n' + '='*80)
        print('RECOMENDACIÓN:')
        print('='*80)
        print(f'Ajustar folio_actual a: {caf.folio_desde} (inicio del rango)')
except Exception as e:
    print(f'  Error al consultar DTEs: {e}')

print('='*80 + '\n')
