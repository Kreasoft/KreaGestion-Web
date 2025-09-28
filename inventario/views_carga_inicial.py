from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
import pandas as pd
import io
import json
from .models import Inventario, Stock
from usuarios.decorators import requiere_empresa
from articulos.models import Articulo
from bodegas.models import Bodega


@login_required
@requiere_empresa
def carga_inicial_inventario(request):
    """
    Vista principal para carga inicial de inventario
    """
    if not request.user.is_superuser:
        messages.error(request, 'Solo los administradores pueden realizar carga inicial de inventario.')
        return redirect('inventario:inventario_list')
    
    context = {
        'title': 'Carga Inicial de Inventario',
        'articulos_count': Articulo.objects.filter(empresa=request.empresa).count(),
        'bodegas': Bodega.objects.filter(empresa=request.empresa, activa=True)
    }
    
    return render(request, 'inventario/carga_inicial.html', context)


@login_required
@requiere_empresa
def exportar_plantilla_excel(request):
    """
    Exporta plantilla Excel con productos para carga inicial
    """
    if not request.user.is_superuser:
        messages.error(request, 'No tiene permisos para esta acción.')
        return redirect('inventario:inventario_list')
    
    # Obtener productos de la empresa
    articulos = Articulo.objects.filter(empresa=request.empresa, activo=True).order_by('codigo')
    
    # Crear DataFrame
    data = []
    for articulo in articulos:
        data.append({
            'CODIGO': articulo.codigo,
            'NOMBRE': articulo.nombre,
            'DESCRIPCION': articulo.descripcion or '',
            'UNIDAD_MEDIDA': articulo.unidad_medida.simbolo if articulo.unidad_medida else '',
            'STOCK_INICIAL': 0,  # Columna para llenar
            'STOCK_MINIMO': articulo.stock_minimo or 0,
            'STOCK_MAXIMO': articulo.stock_maximo or 0,
        })
    
    df = pd.DataFrame(data)
    
    # Crear Excel en memoria
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Inventario Inicial', index=False)
        
        # Obtener la hoja de trabajo para formatear
        worksheet = writer.sheets['Inventario Inicial']
        
        # Ajustar ancho de columnas
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
    
    output.seek(0)
    
    # Crear respuesta HTTP
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="plantilla_inventario_inicial_{request.empresa.nombre}.xlsx"'
    
    return response


@login_required
@requiere_empresa
@csrf_exempt
def importar_inventario_excel(request):
    """
    Importa inventario inicial desde Excel
    """
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'message': 'No tiene permisos para esta acción.'})
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido.'})
    
    try:
        excel_file = request.FILES.get('excel_file')
        bodega_id = request.POST.get('bodega_id')
        
        print(f"DEBUG - FILES: {request.FILES}")
        print(f"DEBUG - POST: {request.POST}")
        print(f"DEBUG - excel_file: {excel_file}")
        print(f"DEBUG - bodega_id: {bodega_id}")
        
        if not excel_file:
            return JsonResponse({'success': False, 'message': 'No se seleccionó archivo.'})
        
        if not bodega_id:
            return JsonResponse({'success': False, 'message': 'Debe seleccionar una bodega.'})
        
        bodega = get_object_or_404(Bodega, id=bodega_id, empresa=request.empresa)
        
        # Leer Excel
        df = pd.read_excel(excel_file)
        
        # Validar columnas requeridas
        required_columns = ['CODIGO', 'STOCK_INICIAL']
        if not all(col in df.columns for col in required_columns):
            return JsonResponse({
                'success': False, 
                'message': f'El archivo debe contener las columnas: {", ".join(required_columns)}'
            })
        
        # Procesar datos
        resultados = {
            'exitosos': 0,
            'errores': 0,
            'detalle_errores': []
        }
        
        with transaction.atomic():
            for index, row in df.iterrows():
                try:
                    codigo = str(row['CODIGO']).strip()
                    stock_inicial = float(row['STOCK_INICIAL']) if pd.notna(row['STOCK_INICIAL']) else 0
                    
                    # Buscar artículo
                    articulo = Articulo.objects.get(
                        codigo=codigo, 
                        empresa=request.empresa, 
                        activo=True
                    )
                    
                    # Crear o actualizar stock
                    stock, created = Stock.objects.get_or_create(
                        empresa=request.empresa,
                        articulo=articulo,
                        bodega=bodega,
                        defaults={'cantidad': stock_inicial}
                    )
                    
                    if not created:
                        stock.cantidad = stock_inicial
                        stock.save()
                    
                    # Crear movimiento de inventario
                    Inventario.objects.create(
                        empresa=request.empresa,
                        articulo=articulo,
                        bodega_destino=bodega,
                        tipo_movimiento='entrada',
                        cantidad=stock_inicial,
                        descripcion='Carga inicial de inventario',
                        estado='completado',
                        creado_por=request.user
                    )
                    
                    resultados['exitosos'] += 1
                    
                except Articulo.DoesNotExist:
                    resultados['errores'] += 1
                    resultados['detalle_errores'].append(f'Fila {index + 2}: Artículo con código "{codigo}" no encontrado')
                except Exception as e:
                    resultados['errores'] += 1
                    resultados['detalle_errores'].append(f'Fila {index + 2}: {str(e)}')
        
        return JsonResponse({
            'success': True,
            'message': f'Procesados: {resultados["exitosos"]} exitosos, {resultados["errores"]} errores',
            'detalle_errores': resultados['detalle_errores'][:10]  # Solo primeros 10 errores
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error al procesar archivo: {str(e)}'})


@login_required
@requiere_empresa
def edicion_manual_inventario(request):
    """
    Vista para edición manual de inventario inicial
    """
    if not request.user.is_superuser:
        messages.error(request, 'Solo los administradores pueden realizar carga inicial de inventario.')
        return redirect('inventario:inventario_list')
    
    bodega_id = request.GET.get('bodega')
    bodegas = Bodega.objects.filter(empresa=request.empresa, activa=True)
    bodega_seleccionada = None
    
    if bodega_id:
        bodega_seleccionada = get_object_or_404(Bodega, id=bodega_id, empresa=request.empresa)
    
    context = {
        'title': 'Edición Manual de Inventario Inicial',
        'bodegas': bodegas,
        'bodega_seleccionada': bodega_seleccionada,
    }
    
    return render(request, 'inventario/edicion_manual_inventario.html', context)


@login_required
@requiere_empresa
def obtener_articulos_para_inventario(request):
    """
    API para obtener artículos con su stock actual
    """
    if not request.user.is_superuser:
        return JsonResponse({'error': 'No tiene permisos'}, status=403)
    
    bodega_id = request.GET.get('bodega_id')
    if not bodega_id:
        return JsonResponse({'error': 'Bodega requerida'}, status=400)
    
    bodega = get_object_or_404(Bodega, id=bodega_id, empresa=request.empresa)
    
    articulos = Articulo.objects.filter(empresa=request.empresa, activo=True).order_by('codigo')
    
    data = []
    for articulo in articulos:
        stock = Stock.objects.filter(articulo=articulo, bodega=bodega).first()
        data.append({
            'id': articulo.id,
            'codigo': articulo.codigo,
            'nombre': articulo.nombre,
            'descripcion': articulo.descripcion or '',
            'unidad_medida': articulo.unidad_medida.simbolo if articulo.unidad_medida else '',
            'cantidad': float(stock.cantidad) if stock else 0,
            'stock_minimo': float(articulo.stock_minimo) if articulo.stock_minimo else 0,
            'stock_maximo': float(articulo.stock_maximo) if articulo.stock_maximo else 0,
        })
    
    return JsonResponse({'articulos': data})


@login_required
@requiere_empresa
@csrf_exempt
def guardar_inventario_manual(request):
    """
    Guarda inventario inicial desde edición manual
    """
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'message': 'No tiene permisos para esta acción.'})
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido.'})
    
    try:
        data = json.loads(request.body)
        bodega_id = data.get('bodega_id')
        inventarios = data.get('inventarios', [])
        
        if not bodega_id:
            return JsonResponse({'success': False, 'message': 'Bodega requerida.'})
        
        bodega = get_object_or_404(Bodega, id=bodega_id, empresa=request.empresa)
        
        resultados = {
            'exitosos': 0,
            'errores': 0,
            'detalle_errores': []
        }
        
        with transaction.atomic():
            for item in inventarios:
                try:
                    articulo_id = item.get('articulo_id')
                    cantidad = float(item.get('cantidad', 0))
                    
                    if cantidad <= 0:
                        continue
                    
                    articulo = get_object_or_404(Articulo, id=articulo_id, empresa=request.empresa)
                    
                    # Crear o actualizar stock
                    stock, created = Stock.objects.get_or_create(
                        empresa=request.empresa,
                        articulo=articulo,
                        bodega=bodega,
                        defaults={'cantidad': cantidad}
                    )
                    
                    if not created:
                        stock.cantidad = cantidad
                        stock.save()
                    
                    # Crear movimiento de inventario
                    Inventario.objects.create(
                        empresa=request.empresa,
                        articulo=articulo,
                        bodega_destino=bodega,
                        tipo_movimiento='entrada',
                        cantidad=cantidad,
                        descripcion='Carga inicial de inventario (manual)',
                        estado='completado',
                        creado_por=request.user
                    )
                    
                    resultados['exitosos'] += 1
                    
                except Exception as e:
                    resultados['errores'] += 1
                    resultados['detalle_errores'].append(f'Error con artículo {articulo_id}: {str(e)}')
        
        return JsonResponse({
            'success': True,
            'message': f'Procesados: {resultados["exitosos"]} exitosos, {resultados["errores"]} errores',
            'detalle_errores': resultados['detalle_errores']
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error al procesar: {str(e)}'})

