import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from ventas.models import Venta, EstacionTrabajo

print("\n" + "="*80)
print("VERIFICAR TICKET Y ESTACION")
print("="*80 + "\n")

# Buscar el último vale creado
ultimo_vale = Venta.objects.filter(tipo_documento='vale').order_by('-id').first()

if not ultimo_vale:
    print("No se encontró ningún vale")
else:
    print(f"Último vale:")
    print(f"  ID: {ultimo_vale.id}")
    print(f"  Número: {ultimo_vale.numero_venta}")
    print(f"  Tipo documento: {ultimo_vale.tipo_documento}")
    print(f"  Tipo documento planeado: {ultimo_vale.tipo_documento_planeado}")
    print(f"  Estación: {ultimo_vale.estacion_trabajo}")
    print()
    
    if ultimo_vale.estacion_trabajo:
        estacion = ultimo_vale.estacion_trabajo
        print(f"Configuración de la estación:")
        print(f"  ID: {estacion.id}")
        print(f"  Nombre: {estacion.nombre}")
        print(f"  cierre_directo: {estacion.cierre_directo}")
        print(f"  enviar_sii_directo: {estacion.enviar_sii_directo}")
    else:
        print("⚠️ El vale NO tiene estación asociada")

print("\n" + "="*80)
print("TODAS LAS ESTACIONES:")
print("="*80 + "\n")

estaciones = EstacionTrabajo.objects.all()
for est in estaciones:
    print(f"ID {est.id}: {est.nombre}")
    print(f"  cierre_directo: {est.cierre_directo}")
    print(f"  enviar_sii_directo: {est.enviar_sii_directo}")
    print()

print("="*80)


