from utilidades.utils import clean_id
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.db.models import Q, Sum, Count, F
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal

from .models import OrdenCompra, ItemOrdenCompra, RecepcionMercancia, ItemRecepcion
from .forms import (
    OrdenCompraForm, ItemOrdenCompraFormSet, RecepcionMercanciaForm, 
    ItemRecepcionFormSet, BusquedaOrdenForm
)
from empresas.models import Empresa
from articulos.models import Articulo
from proveedores.models import Proveedor
from core.decorators import requiere_empresa
import json


def obtener_empresa_usuario(request):
    """Obtener la empresa del usuario con lógica de sesión para superusuarios"""
    if request.user.is_superuser:
        # Para superusuarios, usar empresa de sesión o Kreasoft por defecto
        empresa_id = request.session.get('empresa_activa')
        if empresa_id:
            try:
                empresa = Empresa.objects.get(id=empresa_id)
            except Empresa.DoesNotExist:
                empresa = Empresa.objects.filter(nombre__icontains='Kreasoft').first()
        else:
            empresa = Empresa.objects.filter(nombre__icontains='Kreasoft').first()
        
        if not empresa:
            empresa = Empresa.objects.first()
        
        if not empresa:
            return None, 'No hay empresas configuradas en el sistema.'
            
        # Guardar empresa en sesión
        request.session['empresa_activa'] = empresa.id
        return empresa, None
    else:
        # Para usuarios normales, usar su empresa asociada
        try:
            empresa = request.user.perfil.empresa
            return empresa, None
        except:
            return None, 'Usuario no tiene empresa asociada.'


@login_required
@requiere_empresa
@permission_required('compras.view_ordencompra', raise_exception=True)
def orden_compra_list(request):
    """Lista de órdenes de compra"""
    # Obtener la empresa del usuario
    empresa, error = obtener_empresa_usuario(request)
    if error:
        messages.error(request, error)
        return redirect('dashboard')
    
    # Formulario de búsqueda
    search_form = BusquedaOrdenForm(request.GET)
    
    # Obtener órdenes de compra
    ordenes = OrdenCompra.objects.filter(empresa=empresa)
    
    # Aplicar filtros
    if search_form.is_valid():
        search = search_form.cleaned_data.get('search')
        estado_orden = search_form.cleaned_data.get('estado_orden')
        estado_pago = search_form.cleaned_data.get('estado_pago')
        prioridad = search_form.cleaned_data.get('prioridad')
        fecha_desde = search_form.cleaned_data.get('fecha_desde')
        fecha_hasta = search_form.cleaned_data.get('fecha_hasta')
        
        if search:
            ordenes = ordenes.filter(
                Q(numero_orden__icontains=search) |
                Q(proveedor__nombre__icontains=search) |
                Q(items__articulo__nombre__icontains=search)
            ).distinct()
        
        if estado_orden:
            ordenes = ordenes.filter(estado_orden=estado_orden)
        
        if estado_pago:
            ordenes = ordenes.filter(estado_pago=estado_pago)
        
        if prioridad:
            ordenes = ordenes.filter(prioridad=prioridad)
        
        if fecha_desde:
            ordenes = ordenes.filter(fecha_orden__gte=fecha_desde)
        
        if fecha_hasta:
            ordenes = ordenes.filter(fecha_orden__lte=fecha_hasta)
    
    # Ordenar por fecha de orden descendente
    ordenes = ordenes.order_by('-fecha_orden', '-numero_orden')
    
    # Paginación
    paginator = Paginator(ordenes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Estadísticas
    stats = {
        'total_ordenes': ordenes.count(),
        'pendientes_aprobacion': ordenes.filter(estado_orden='pendiente_aprobacion').count(),
        'en_proceso': ordenes.filter(estado_orden='en_proceso').count(),
        'completamente_recibidas': ordenes.filter(estado_orden='completamente_recibida').count(),
        'valor_total': ordenes.aggregate(total=Sum('total_orden'))['total'] or Decimal('0.00'),
    }
    
    context = {
        'page_obj': page_obj,
        'search_form': search_form,
        'stats': stats,
        'empresa': empresa,
    }
    
    return render(request, 'compras/orden_compra_list.html', context)


@login_required
@requiere_empresa
def orden_compra_detail(request, pk):
    """Detalle de una orden de compra"""
    # Obtener la empresa del usuario
    empresa, error = obtener_empresa_usuario(request)
    if error:
        messages.error(request, error)
        return redirect('dashboard')
    orden = get_object_or_404(OrdenCompra, pk=pk, empresa=empresa)
    
    # Items de la orden
    items = orden.items.all()
    
    # Recepciones de la orden
    recepciones = orden.recepciones.all()
    
    context = {
        'orden': orden,
        'items': items,
        'recepciones': recepciones,
        'empresa': empresa,
    }
    
    return render(request, 'compras/orden_compra_detail.html', context)


@login_required
@requiere_empresa
@permission_required('compras.add_ordencompra', raise_exception=True)
def orden_compra_create(request):
    """Crear nueva orden de compra"""
    # Obtener la empresa del usuario
    empresa, error = obtener_empresa_usuario(request)
    if error:
        messages.error(request, error)
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = OrdenCompraForm(request.POST, empresa=empresa)
        formset = ItemOrdenCompraFormSet(request.POST)
        
        print("=== DEBUG FORMULARIO ===")
        print("Form is valid:", form.is_valid())
        if not form.is_valid():
            print("Form errors:", form.errors)
        print("Formset is valid:", formset.is_valid())
        if not formset.is_valid():
            print("Formset errors:", formset.errors)
        print("POST data:", request.POST)
        
        if form.is_valid() and formset.is_valid():
            try:
                orden = form.save(commit=False)
                orden.empresa = empresa
                orden.creado_por = request.user

                # Generar número de orden usando ConfiguracionEmpresa
                try:
                    from empresas.models import ConfiguracionEmpresa
                    configuracion = ConfiguracionEmpresa.objects.get(empresa=empresa)
                    orden.numero_orden = configuracion.generar_numero_orden_compra()
                except Exception as e:
                    print(f"Error generando número: {e}")
                    # Fallback: usar el del formulario o generar uno simple
                    ultima_orden = OrdenCompra.objects.filter(empresa=empresa).order_by('-id').first()
                    if ultima_orden and '-' in ultima_orden.numero_orden:
                        try:
                            numero = int(ultima_orden.numero_orden.split('-')[-1]) + 1
                        except ValueError:
                            numero = 1
                    else:
                        numero = 1
                    orden.numero_orden = f"OC-{numero:06d}"

                orden.save()
                
                # Guardar items
                formset.instance = orden
                formset.save()
                
                # Calcular totales
                orden.calcular_totales()
                
                messages.success(request, f'Orden de compra {orden.numero_orden} creada exitosamente.')
                return redirect('compras:orden_compra_detail', pk=orden.pk)
            except Exception as e:
                print("Error al guardar:", str(e))
                messages.error(request, f'Error al crear la orden: {str(e)}')
        else:
            messages.error(request, 'Por favor corrige los errores en el formulario.')
    else:
        form = OrdenCompraForm(empresa=empresa)
        formset = ItemOrdenCompraFormSet()
    
    context = {
        'form': form,
        'formset': formset,
        'empresa': empresa,
        'titulo': 'Crear Orden de Compra',
        'articulos_empresa': Articulo.objects.filter(empresa=empresa) if empresa else Articulo.objects.none(),
    }
    
    return render(request, 'compras/orden_compra_form.html', context)


@login_required
@requiere_empresa
@permission_required('compras.change_ordencompra', raise_exception=True)
def orden_compra_update(request, pk):
    """Editar orden de compra"""
    # Obtener la empresa del usuario
    empresa, error = obtener_empresa_usuario(request)
    if error:
        messages.error(request, error)
        return redirect('dashboard')
    orden = get_object_or_404(OrdenCompra, pk=pk, empresa=empresa)
    
    # Verificar que se puede editar - NO se pueden editar órdenes completadas
    if orden.estado_orden == 'completada':
        messages.error(request, 'No se puede editar una orden completada.')
        return redirect('compras:orden_compra_detail', pk=orden.pk)
    
    if request.method == 'POST':
        print("=== DEBUG ORDEN COMPRA UPDATE ===")
        print("POST data recibido:", request.POST)
        
        form = OrdenCompraForm(request.POST, instance=orden, empresa=empresa)
        formset = ItemOrdenCompraFormSet(request.POST, instance=orden)
        
        print("Form is valid:", form.is_valid())
        if not form.is_valid():
            print("Form errors:", form.errors)
        
        print("Formset is valid:", formset.is_valid())
        if not formset.is_valid():
            print("Formset errors:", formset.errors)
            print("Formset non_form_errors:", formset.non_form_errors())
        
        if form.is_valid() and formset.is_valid():
            try:
                orden = form.save()
                print("Orden guardada:", orden.pk)
                
                # Guardar items
                formset.save()
                print("Formset guardado exitosamente")
                
                # Calcular totales
                orden.calcular_totales()
                print("Totales calculados")
                
                messages.success(request, f'Orden de compra {orden.numero_orden} actualizada exitosamente.')
                return redirect('compras:orden_compra_detail', pk=orden.pk)
            except Exception as e:
                print("Error al guardar:", str(e))
                messages.error(request, f'Error al actualizar la orden: {str(e)}')
        else:
            print("Formulario no válido - no se guarda")
            messages.error(request, 'Por favor corrige los errores en el formulario.')
    else:
        form = OrdenCompraForm(instance=orden, empresa=empresa)
        # Inicializar formset con los items existentes
        formset = ItemOrdenCompraFormSet(instance=orden)
        # Asegurar que se carguen todos los items existentes
        if orden.items.exists():
            formset = ItemOrdenCompraFormSet(instance=orden, queryset=orden.items.all())
    
    context = {
        'form': form,
        'formset': formset,
        'orden': orden,
        'empresa': empresa,
        'titulo': 'Editar Orden de Compra',
        'articulos_empresa': Articulo.objects.filter(empresa=empresa) if empresa else Articulo.objects.none(),
    }
    
    return render(request, 'compras/orden_compra_form.html', context)


@login_required
@requiere_empresa
@permission_required('compras.delete_ordencompra', raise_exception=True)
def orden_compra_delete(request, pk):
    """Eliminar orden de compra"""
    # Obtener la empresa del usuario
    empresa, error = obtener_empresa_usuario(request)
    if error:
        return JsonResponse({'success': False, 'message': error})
    
    try:
        orden = get_object_or_404(OrdenCompra, pk=pk, empresa=empresa)
        
        # Verificar que se puede eliminar - NO se pueden eliminar órdenes completadas
        if orden.estado_orden == 'completada':
            return JsonResponse({
                'success': False, 
                'message': 'No se pueden eliminar órdenes completadas.'
            })
        
        if request.method == 'POST':
            numero_orden = orden.numero_orden
            orden.delete()
            return JsonResponse({
                'success': True,
                'message': f'Orden de compra {numero_orden} eliminada exitosamente.'
            })
        
        return JsonResponse({'success': False, 'message': 'Método no permitido'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
@requiere_empresa
def orden_compra_aprobar(request, pk):
    """Aprobar una orden de compra"""
    # Obtener la empresa del usuario
    empresa, error = obtener_empresa_usuario(request)
    if error:
        messages.error(request, error)
        return redirect('dashboard')
    orden = get_object_or_404(OrdenCompra, pk=pk, empresa=empresa)
    
    if orden.puede_aprobar():
        orden.estado_orden = 'aprobada'
        orden.aprobado_por = request.user
        orden.fecha_aprobacion = timezone.now()
        orden.save()
        
        messages.success(request, f'Orden de compra {orden.numero_orden} aprobada exitosamente.')
    else:
        messages.error(request, 'Esta orden no puede ser aprobada.')
    
    return redirect('compras:orden_compra_detail', pk=orden.pk)


@login_required
@requiere_empresa
def get_articulo_info(request):
    """Obtener información de un artículo via AJAX"""
    articulo_id = clean_id(request.GET.get('articulo_id'))
    
    try:
        articulo = Articulo.objects.get(pk=articulo_id)
        data = {
            'nombre': articulo.nombre,
            'descripcion': articulo.descripcion,
            'unidad_medida': articulo.unidad_medida.nombre if articulo.unidad_medida else '',
            'precio_compra': str(articulo.precio_compra) if articulo.precio_compra else '0.00',
            'stock_actual': str(articulo.get_stock_total()),
        }
        return JsonResponse(data)
    except Articulo.DoesNotExist:
        return JsonResponse({'error': 'Artículo no encontrado'}, status=404)


# =============================================================================
# FUNCIONALIDAD DE RECEPCIÓN DESHABILITADA - No se usa por el momento
# =============================================================================
# Las recepciones se reemplazan por el flujo: OC → Documento de Compra
# El Documento de Compra actualiza stock automáticamente y marca OC como completada
# =============================================================================

# @login_required
# @requiere_empresa
# def recepcion_create(request, orden_id):
#     """Crear recepción de mercancía"""
#     # Obtener la empresa del usuario
#     empresa, error = obtener_empresa_usuario(request)
#     if error:
#         messages.error(request, error)
#         return redirect('dashboard')
#     orden = get_object_or_404(OrdenCompra, pk=orden_id, empresa=empresa)
#     
#     if not orden.puede_recibir():
#         messages.error(request, 'Esta orden no puede recibir mercancías.')
#         return redirect('compras:orden_compra_detail', pk=orden.pk)
#     
#     if request.method == 'POST':
#         form = RecepcionMercanciaForm(request.POST, orden_compra=orden)
#         formset = ItemRecepcionFormSet(request.POST)
#         
#         if form.is_valid() and formset.is_valid():
#             recepcion = form.save(commit=False)
#             recepcion.orden_compra = orden
#             recepcion.recibido_por = request.user
#             recepcion.save()
#             
#             # Guardar items
#             formset.instance = recepcion
#             formset.save()
#             
#             messages.success(request, f'Recepción {recepcion.numero_recepcion} creada exitosamente.')
#             return redirect('compras:orden_compra_detail', pk=orden.pk)
#     else:
#         form = RecepcionMercanciaForm(orden_compra=orden)
#         formset = ItemRecepcionFormSet()
#         
#         # Pre-poblar el formset con items de la orden
#         formset.extra = len(orden.items.filter(cantidad_recibida__lt=F('cantidad_solicitada')))
#     
#     context = {
#         'form': form,
#         'formset': formset,
#         'orden': orden,
#         'empresa': empresa,
#         'titulo': 'Crear Recepción de Mercancía',
#         'items_orden': orden.items.filter(cantidad_recibida__lt=F('cantidad_solicitada')),
#     }
#     
#     return render(request, 'compras/recepcion_form.html', context)


# @login_required
# @requiere_empresa
# def recepcion_detail(request, pk):
#     """Detalle de una recepción"""
#     # Obtener la empresa del usuario
#     empresa, error = obtener_empresa_usuario(request)
#     if error:
#         messages.error(request, error)
#         return redirect('dashboard')
#     recepcion = get_object_or_404(RecepcionMercancia, pk=pk, orden_compra__empresa=empresa)
#     
#     items = recepcion.items.all()
#     
#     context = {
#         'recepcion': recepcion,
#         'items': items,
#         'empresa': empresa,
#     }
#     
#     return render(request, 'compras/recepcion_detail.html', context)


@login_required
def proveedor_create_ajax(request):
    """Vista AJAX para crear un nuevo proveedor desde el formulario de documento de compra"""
    if request.method == 'POST':
        try:
            # Obtener la empresa del usuario
            empresa, error = obtener_empresa_usuario(request)
            if error:
                return JsonResponse({
                    'success': False,
                    'message': error
                }, status=400)
            
            # Parsear datos JSON
            data = json.loads(request.body)
            
            # Validar campos obligatorios
            rut = data.get('rut', '').strip()
            razon_social = data.get('razon_social', '').strip()
            
            if not rut or not razon_social:
                return JsonResponse({
                    'success': False,
                    'message': 'RUT y Razón Social son obligatorios'
                }, status=400)
            
            # Verificar si el proveedor ya existe
            if Proveedor.objects.filter(empresa=empresa, rut=rut).exists():
                return JsonResponse({
                    'success': False,
                    'message': f'Ya existe un proveedor con el RUT {rut} en esta empresa'
                }, status=400)
            
            # Crear el proveedor
            proveedor = Proveedor.objects.create(
                empresa=empresa,
                nombre=data.get('nombre_fantasia', razon_social),
                razon_social=razon_social,
                rut=rut,
                giro=data.get('giro', 'Sin especificar'),
                direccion=data.get('direccion', 'Sin especificar'),
                comuna=data.get('comuna', 'Sin especificar'),
                ciudad=data.get('ciudad', 'Sin especificar'),
                region=data.get('region', 'Sin especificar'),
                telefono=data.get('telefono', ''),
                email=data.get('email', ''),
                tipo_proveedor='productos',
                estado='activo',
                creado_por=request.user
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Proveedor creado exitosamente',
                'proveedor': {
                    'id': proveedor.id,
                    'rut': proveedor.rut,
                    'razon_social': proveedor.razon_social,
                    'nombre': proveedor.nombre
                }
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Error al procesar los datos JSON'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error al crear el proveedor: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'message': 'Método no permitido'
    }, status=405)
