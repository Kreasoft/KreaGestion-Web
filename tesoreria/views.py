from utilidades.utils import clean_id
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.template.loader import render_to_string
from django.utils import timezone
import json
from decimal import Decimal

from .models import CuentaCorrienteProveedor, MovimientoCuentaCorriente
from documentos.models import DocumentoCompra
from proveedores.models import Proveedor
from empresas.models import Empresa
from bodegas.models import Bodega
from core.decorators import requiere_empresa


@login_required
@requiere_empresa
def cuenta_corriente_proveedor_list(request):
    """Lista de cuentas corrientes de proveedores"""
    # Obtener la empresa del usuario
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
            messages.error(request, 'No hay empresas configuradas en el sistema.')
            return redirect('dashboard')
            
        # Guardar empresa en sesión
        request.session['empresa_activa'] = empresa.id
    else:
        try:
            empresa = request.user.perfil.empresa
        except:
            messages.error(request, 'Usuario no tiene empresa asociada.')
            return redirect('dashboard')
    
    # Filtros
    search = request.GET.get('search', '')
    estado_pago = request.GET.get('estado_pago', '')
    
    # Obtener documentos pendientes de pago por defecto
    documentos_query = DocumentoCompra.objects.filter(
        empresa=empresa,
        en_cuenta_corriente=True
    ).select_related('proveedor')
    
    # Aplicar filtros
    if search:
        documentos_query = documentos_query.filter(
            Q(numero_documento__icontains=search) |
            Q(proveedor__nombre__icontains=search) |
            Q(proveedor__rut__icontains=search)
        )
    
    if estado_pago:
        documentos_query = documentos_query.filter(estado_pago=estado_pago)
    
    # Agregar información de pagos a cada documento
    for documento in documentos_query:
        documento.pagos = documento.historial_pagos.all().order_by('-fecha_pago')
    
    # Paginación
    paginator = Paginator(documentos_query, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Estadísticas
    stats = {
        'total_documentos': documentos_query.count(),
        'total_pendiente': documentos_query.filter(estado_pago='credito').aggregate(Sum('saldo_pendiente'))['saldo_pendiente__sum'] or 0,
        'total_vencido': documentos_query.filter(estado_pago='vencida').aggregate(Sum('saldo_pendiente'))['saldo_pendiente__sum'] or 0,
        'total_parcial': documentos_query.filter(estado_pago='parcial').aggregate(Sum('saldo_pendiente'))['saldo_pendiente__sum'] or 0,
    }
    
    context = {
        'page_obj': page_obj,
        'stats': stats,
        'search': search,
        'estado_pago': estado_pago,
        'empresa': empresa,
        'today': timezone.now().date(),
    }
    
    return render(request, 'tesoreria/cuenta_corriente_proveedor_list.html', context)


@login_required
@requiere_empresa
def cuenta_corriente_proveedor_detail(request, proveedor_id):
    """Detalle de cuenta corriente de un proveedor específico"""
    # Obtener la empresa del usuario
    if request.user.is_superuser:
        empresa = Empresa.objects.first()
    else:
        try:
            empresa = request.user.perfil.empresa
        except:
            messages.error(request, 'Usuario no tiene empresa asociada.')
            return redirect('dashboard')
    
    # Obtener documentos del proveedor de la empresa activa
    documentos = DocumentoCompra.objects.filter(
        empresa=empresa,
        proveedor_id=proveedor_id,
        en_cuenta_corriente=True
    ).select_related('proveedor').order_by('fecha_vencimiento')
    
    # Si no hay documentos, el proveedor no es válido para esta empresa
    if not documentos.exists():
        messages.error(request, 'No se encontraron documentos para este proveedor en la empresa actual.')
        return redirect('tesoreria:cuenta_corriente_proveedor_list')
    
    proveedor = documentos.first().proveedor
    
    # Estadísticas
    stats = {
        'total_documentos': documentos.count(),
        'total_pendiente': documentos.filter(estado_pago='credito').aggregate(Sum('saldo_pendiente'))['saldo_pendiente__sum'] or 0,
        'total_vencido': documentos.filter(estado_pago='vencida').aggregate(Sum('saldo_pendiente'))['saldo_pendiente__sum'] or 0,
        'total_parcial': documentos.filter(estado_pago='parcial').aggregate(Sum('saldo_pendiente'))['saldo_pendiente__sum'] or 0,
    }
    
    context = {
        'proveedor': proveedor,
        'documentos': documentos,
        'stats': stats,
        'empresa': empresa,
    }
    
    return render(request, 'tesoreria/cuenta_corriente_proveedor_detail.html', context)


@login_required
@requiere_empresa
def cuenta_corriente_cliente_list(request):
    """Lista de cuentas corrientes de clientes"""
    # La empresa ya está configurada por el decorador @requiere_empresa
    empresa = request.empresa
    
    # Obtener MOVIMIENTOS individuales de cuenta corriente (cada factura)
    from .models import DocumentoCliente, CuentaCorrienteCliente, MovimientoCuentaCorrienteCliente
    from clientes.models import Cliente
    from ventas.models import Venta
    
    # Filtros
    search = request.GET.get('search', '')
    estado_pago = request.GET.get('estado_pago', '')
    
    # Mostrar movimientos DEBE (facturas a crédito) individuales
    from django.db.models import Sum, Q, Case, When, Value, CharField
    
    # Obtener todos los movimientos de tipo 'debe' de la empresa
    movimientos_query = MovimientoCuentaCorrienteCliente.objects.filter(
        cuenta_corriente__empresa=empresa,
        tipo_movimiento='debe'
    ).select_related('cuenta_corriente', 'cuenta_corriente__cliente', 'venta').order_by('-fecha_movimiento')
    
    # Anotar cada movimiento con el total pagado
    from decimal import Decimal
    
    movimientos_list = []
    for mov in movimientos_query:
        # Calcular total pagado para esta factura
        total_pagado_result = MovimientoCuentaCorrienteCliente.objects.filter(
            cuenta_corriente=mov.cuenta_corriente,
            venta=mov.venta,
            tipo_movimiento='haber'
        ).aggregate(total=Sum('monto'))['total']
        
        # Convertir a Decimal para evitar problemas de tipo
        total_pagado = Decimal(str(total_pagado_result)) if total_pagado_result else Decimal('0')
        monto_factura = Decimal(str(mov.monto))
        
        # Determinar estado
        if total_pagado >= monto_factura:
            mov.estado_pago = 'pagado'
        elif total_pagado > 0:
            mov.estado_pago = 'parcial'
        else:
            mov.estado_pago = 'pendiente'
        
        # Convertir a enteros para evitar problemas de formato
        mov.monto_display = int(monto_factura)
        mov.total_pagado = int(total_pagado)
        mov.saldo_pendiente_factura = int(monto_factura - total_pagado)
        movimientos_list.append(mov)
    
    # Convertir de vuelta a queryset-like para paginación
    class MovimientosList(list):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
        
        def filter(self, **kwargs):
            result = list(self)
            if 'estado' in kwargs:
                estado = kwargs['estado']
                result = [m for m in result if m.estado_pago == estado]
            return MovimientosList(result)
        
        def aggregate(self, **kwargs):
            if 'monto__sum' in kwargs:
                return {'monto__sum': sum(m.monto for m in self)}
            return {}
        
        def count(self):
            return len(self)
    
    movimientos_query = MovimientosList(movimientos_list)
    
    # Aplicar filtro de búsqueda
    if search:
        filtered_list = []
        for mov in movimientos_query:
            if (search.lower() in mov.cuenta_corriente.cliente.nombre.lower() or
                search.lower() in mov.cuenta_corriente.cliente.rut.lower() or
                (mov.venta and search in mov.venta.numero_venta)):
                filtered_list.append(mov)
        movimientos_query = MovimientosList(filtered_list)
    
    # Filtrar por estado de pago
    if estado_pago:
        movimientos_query = MovimientosList([m for m in movimientos_query if m.estado_pago == estado_pago])
    
    # Paginación
    from django.core.paginator import Paginator
    paginator = Paginator(list(movimientos_query), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Estadísticas
    stats = {
        'total_documentos': len(movimientos_list),
        'total_pendiente': sum(m.saldo_pendiente_factura for m in movimientos_list if m.estado_pago == 'pendiente'),
        'total_pagado': sum(m.total_pagado for m in movimientos_list if m.estado_pago == 'pagado'),
        'total_parcial': sum(m.saldo_pendiente_factura for m in movimientos_list if m.estado_pago == 'parcial'),
    }
    
    context = {
        'empresa': empresa,
        'page_obj': page_obj,
        'stats': stats,
        'search': search,
        'estado_pago': estado_pago,
        'today': timezone.now().date(),
    }
    
    return render(request, 'tesoreria/cuenta_corriente_cliente_list.html', context)


@csrf_exempt
@login_required
def registrar_pago(request):
    """Registrar un pago con múltiples formas de pago mediante AJAX"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    try:
        data = json.loads(request.body)
        
        documento_id = data.get('documento_id')
        formas_pago = data.get('formas_pago', [])
        observaciones = data.get('observaciones', '')
        
        documento = get_object_or_404(DocumentoCompra, pk=documento_id)
        
        # Validar que hay formas de pago
        if not formas_pago:
            return JsonResponse({'error': 'Debe especificar al menos una forma de pago'}, status=400)
        
        # Calcular monto total - manejar tanto números como strings
        monto_total = sum(Decimal(str(forma['monto'])) for forma in formas_pago)
        
        # Validar monto
        if monto_total <= 0:
            return JsonResponse({'error': 'El monto debe ser mayor a 0'}, status=400)
        
        if monto_total > documento.saldo_pendiente:
            return JsonResponse({'error': 'El monto excede el saldo pendiente'}, status=400)
        
        # Registrar el pago - asegurar que monto_pagado sea Decimal
        if documento.monto_pagado is None:
            documento.monto_pagado = Decimal('0')
        else:
            documento.monto_pagado = Decimal(str(documento.monto_pagado))
        
        documento.monto_pagado += monto_total
        documento.calcular_totales()
        documento.save()  # Guardar el documento actualizado
        
        # Crear registro de pago principal
        from documentos.models import HistorialPagoDocumento, FormaPagoPago
        from django.utils import timezone
        
        pago = HistorialPagoDocumento.objects.create(
            documento_compra=documento,
            fecha_pago=timezone.now(),
            monto_total_pagado=monto_total,
            observaciones=observaciones,
            registrado_por=request.user
        )
        
        # Crear las formas de pago específicas
        for forma_data in formas_pago:
            from ventas.models import FormaPago
            
            # Obtener la forma de pago del sistema
            try:
                forma_pago_obj = FormaPago.objects.get(
                    id=forma_data.get('forma_pago_id'),
                    empresa=documento.empresa,
                    activo=True
                )
            except FormaPago.DoesNotExist:
                return JsonResponse({'error': 'Forma de pago no válida'}, status=400)
            
            forma_pago = FormaPagoPago.objects.create(
                pago=pago,
                forma_pago=forma_pago_obj,
                monto=Decimal(str(forma_data['monto'])),
                numero_cheque=forma_data.get('numero_cheque', ''),
                banco_cheque=forma_data.get('banco_cheque', ''),
                numero_transferencia=forma_data.get('numero_transferencia', ''),
                banco_transferencia=forma_data.get('banco_transferencia', ''),
                numero_tarjeta=forma_data.get('numero_tarjeta', ''),
                codigo_autorizacion=forma_data.get('codigo_autorizacion', ''),
                observaciones=forma_data.get('observaciones', '')
            )
            
            # Si es cheque, manejar fecha de vencimiento
            if forma_pago_obj.requiere_cheque and forma_data.get('fecha_vencimiento_cheque'):
                from datetime import datetime
                try:
                    fecha_vencimiento = datetime.strptime(forma_data['fecha_vencimiento_cheque'], '%Y-%m-%d').date()
                    forma_pago.fecha_vencimiento_cheque = fecha_vencimiento
                    forma_pago.save()
                except ValueError:
                    pass  # Ignorar fecha inválida
        
        return JsonResponse({
            'success': True,
            'message': f'Pago registrado exitosamente por ${monto_total:,.0f}',
            'saldo_pendiente': str(documento.saldo_pendiente),
            'estado_pago': documento.get_estado_pago_display()
        })
        
    except Exception as e:
        return JsonResponse({'error': f'Error al procesar el pago: {str(e)}'}, status=500)


@login_required
def obtener_formas_pago(request):
    """Obtener formas de pago disponibles para la empresa"""
    try:
        # Obtener la empresa del usuario
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
        else:
            empresa = request.user.perfil.empresa
        
        from ventas.models import FormaPago
        
        # Para Kreasoft, usar solo las formas de pago originales (excluyendo CREDITO y duplicados)
        if empresa and 'kreasoft' in empresa.nombre.lower():
            formas_pago = FormaPago.objects.filter(
                empresa=empresa,
                activo=True,
                id__in=[1, 2, 3, 4]  # Solo las formas de pago originales, excluyendo CREDITO (ID 5)
            ).order_by('id')
        else:
            # Para otras empresas, usar todas las formas de pago activas
            formas_pago = FormaPago.objects.filter(
                empresa=empresa,
                activo=True
            ).order_by('nombre')
        
        data = [{
            'id': fp.id,
            'codigo': fp.codigo,
            'nombre': fp.nombre,
            'requiere_cheque': fp.requiere_cheque,
            'es_cuenta_corriente': fp.es_cuenta_corriente
        } for fp in formas_pago]
        
        return JsonResponse({'formas_pago': data})
        
    except Exception as e:
        return JsonResponse({'error': f'Error al obtener formas de pago: {str(e)}'}, status=500)


@login_required
def cambiar_empresa_activa(request):
    """Cambiar la empresa activa para superusuarios"""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    if request.method == 'POST':
        try:
            empresa_id = clean_id(request.POST.get('empresa_id'))
            if not empresa_id:
                return JsonResponse({'error': 'ID de empresa requerido'}, status=400)
            
            empresa = Empresa.objects.get(id=empresa_id)
            request.session['empresa_activa'] = empresa.id
            
            return JsonResponse({
                'success': True,
                'message': f'Empresa cambiada a: {empresa.nombre}',
                'empresa': {
                    'id': empresa.id,
                    'nombre': empresa.nombre
                }
            })
            
        except Empresa.DoesNotExist:
            return JsonResponse({'error': 'Empresa no encontrada'}, status=404)
        except Exception as e:
            return JsonResponse({'error': f'Error al cambiar empresa: {str(e)}'}, status=500)
    
    # GET: Obtener lista de empresas disponibles
    empresas = Empresa.objects.all().order_by('nombre')
    empresas_data = [{
        'id': emp.id,
        'nombre': emp.nombre,
        'rut': emp.rut,
        'activa': request.session.get('empresa_activa') == emp.id
    } for emp in empresas]
    
    return JsonResponse({'empresas': empresas_data})


@login_required
def historial_pagos_documento(request, documento_id):
    """Obtener historial de pagos de un documento"""
    try:
        from documentos.models import HistorialPagoDocumento
        
        documento = get_object_or_404(DocumentoCompra, pk=documento_id)
        pagos = documento.historial_pagos.all().order_by('-fecha_pago')
        
        pagos_data = []
        total_pagado = 0
        
        for pago in pagos:
            formas = []
            for fp in pago.formas_pago.all():
                formas.append(fp.forma_pago.nombre)
            
            pagos_data.append({
                'fecha': pago.fecha_pago.strftime('%d/%m/%Y'),
                'monto': str(pago.monto_total_pagado),
                'forma_pago': ', '.join(formas) if formas else 'N/A'
            })
            total_pagado += float(pago.monto_total_pagado)
        
        return JsonResponse({
            'pagos': pagos_data,
            'total_pagado': total_pagado
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def detalle_pago(request, pago_id):
    """Ver detalle de un pago específico"""
    try:
        from documentos.models import HistorialPagoDocumento
        
        pago = get_object_or_404(HistorialPagoDocumento, pk=pago_id)
        
        # Verificar permisos
        if not request.user.is_superuser:
            try:
                if request.user.perfil.empresa != pago.documento_compra.empresa:
                    return JsonResponse({'error': 'No tienes permisos para ver este pago'}, status=403)
            except:
                return JsonResponse({'error': 'Usuario no tiene empresa asociada'}, status=403)
        
        # Obtener formas de pago del pago
        formas_pago = pago.formas_pago.all()
        
        data = {
            'pago': {
                'id': pago.id,
                'fecha_pago': pago.fecha_pago.strftime('%d/%m/%Y %H:%M'),
                'monto_total_pagado': str(pago.monto_total_pagado),
                'observaciones': pago.observaciones,
                'registrado_por': pago.registrado_por.get_full_name() or pago.registrado_por.username
            },
            'documento': {
                'numero_documento': pago.documento_compra.numero_documento,
                'proveedor': pago.documento_compra.proveedor.nombre,
                'total_documento': str(pago.documento_compra.total_documento),
                'saldo_pendiente': str(pago.documento_compra.saldo_pendiente)
            },
            'formas_pago': [{
                'id': fp.id,
                'forma_pago': fp.forma_pago.nombre,
                'codigo': fp.forma_pago.codigo,
                'monto': str(fp.monto),
                'numero_cheque': fp.numero_cheque,
                'banco_cheque': fp.banco_cheque,
                'fecha_vencimiento_cheque': fp.fecha_vencimiento_cheque.strftime('%d/%m/%Y') if fp.fecha_vencimiento_cheque else None,
                'numero_transferencia': fp.numero_transferencia,
                'banco_transferencia': fp.banco_transferencia,
                'numero_tarjeta': fp.numero_tarjeta,
                'codigo_autorizacion': fp.codigo_autorizacion,
                'observaciones': fp.observaciones
            } for fp in formas_pago]
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({'error': f'Error al obtener detalle del pago: {str(e)}'}, status=500)


@login_required
def editar_pago(request, pago_id):
    """Editar un pago existente"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    try:
        from documentos.models import HistorialPagoDocumento, FormaPagoPago
        from ventas.models import FormaPago
        
        pago = get_object_or_404(HistorialPagoDocumento, pk=pago_id)
        
        # Verificar permisos
        if not request.user.is_superuser:
            try:
                if request.user.perfil.empresa != pago.documento_compra.empresa:
                    return JsonResponse({'error': 'No tienes permisos para editar este pago'}, status=403)
            except:
                return JsonResponse({'error': 'Usuario no tiene empresa asociada'}, status=403)
        
        data = json.loads(request.body)
        formas_pago = data.get('formas_pago', [])
        observaciones = data.get('observaciones', '')
        
        if not formas_pago:
            return JsonResponse({'error': 'Debe especificar al menos una forma de pago'}, status=400)
        
        # Calcular nuevo monto total
        nuevo_monto_total = sum(Decimal(str(forma['monto'])) for forma in formas_pago)
        
        if nuevo_monto_total <= 0:
            return JsonResponse({'error': 'El monto debe ser mayor a 0'}, status=400)
        
        # Revertir el pago anterior del documento
        documento = pago.documento_compra
        documento.monto_pagado -= pago.monto_total_pagado
        documento.calcular_totales()
        documento.save()
        
        # Eliminar formas de pago anteriores
        pago.formas_pago.all().delete()
        
        # Actualizar el pago principal
        pago.monto_total_pagado = nuevo_monto_total
        pago.observaciones = observaciones
        pago.save()
        
        # Crear las nuevas formas de pago
        for forma_data in formas_pago:
            forma_pago_obj = FormaPago.objects.get(
                id=forma_data.get('forma_pago_id'),
                empresa=documento.empresa,
                activo=True
            )
            
            forma_pago = FormaPagoPago.objects.create(
                pago=pago,
                forma_pago=forma_pago_obj,
                monto=Decimal(str(forma_data['monto'])),
                numero_cheque=forma_data.get('numero_cheque', ''),
                banco_cheque=forma_data.get('banco_cheque', ''),
                numero_transferencia=forma_data.get('numero_transferencia', ''),
                banco_transferencia=forma_data.get('banco_transferencia', ''),
                numero_tarjeta=forma_data.get('numero_tarjeta', ''),
                codigo_autorizacion=forma_data.get('codigo_autorizacion', ''),
                observaciones=forma_data.get('observaciones', '')
            )
            
            # Manejar fecha de vencimiento de cheque
            if forma_pago_obj.requiere_cheque and forma_data.get('fecha_vencimiento_cheque'):
                try:
                    from datetime import datetime
                    fecha_vencimiento = datetime.strptime(forma_data['fecha_vencimiento_cheque'], '%Y-%m-%d').date()
                    forma_pago.fecha_vencimiento_cheque = fecha_vencimiento
                    forma_pago.save()
                except ValueError:
                    pass
        
        # Aplicar el nuevo pago al documento
        documento.monto_pagado += nuevo_monto_total
        documento.calcular_totales()
        documento.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Pago actualizado exitosamente por ${nuevo_monto_total:,.0f}',
            'saldo_pendiente': str(documento.saldo_pendiente),
            'estado_pago': documento.get_estado_pago_display()
        })
        
    except Exception as e:
        return JsonResponse({'error': f'Error al actualizar el pago: {str(e)}'}, status=500)


# ==================== CRUD DOCUMENTOS PENDIENTES ====================

@login_required
@requiere_empresa
def documento_pendiente_proveedor_list(request):
    """Lista de documentos pendientes de proveedores"""
    empresa = request.empresa if hasattr(request, 'empresa') else request.user.perfil.empresa
    
    documentos = DocumentoCompra.objects.filter(
        empresa=empresa,
        en_cuenta_corriente=True
    ).select_related('proveedor').order_by('-fecha_emision')
    
    # Filtros
    search = request.GET.get('search', '')
    if search:
        documentos = documentos.filter(
            Q(numero_documento__icontains=search) |
            Q(proveedor__nombre__icontains=search)
        )
    
    paginator = Paginator(documentos, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    
    context = {
        'page_obj': page_obj,
        'search': search,
    }
    return render(request, 'tesoreria/documento_pendiente_proveedor_list.html', context)


@login_required
def documento_pendiente_proveedor_create(request):
    """Crear documento pendiente de proveedor (modal)"""
    empresa = request.empresa if hasattr(request, 'empresa') else request.user.perfil.empresa
    
    if request.method == 'POST':
        try:
            proveedor_id = request.POST.get('proveedor')
            proveedor = get_object_or_404(Proveedor, pk=proveedor_id, empresa=empresa)
            total = int(request.POST.get('total', 0))
            
            documento = DocumentoCompra.objects.create(
                empresa=empresa,
                proveedor=proveedor,
                bodega=Bodega.objects.filter(empresa=empresa).first(),
                tipo_documento=request.POST.get('tipo_documento'),
                numero_documento=request.POST.get('numero_documento'),
                fecha_emision=request.POST.get('fecha_emision'),
                fecha_vencimiento=request.POST.get('fecha_vencimiento'),
                total_documento=total,
                saldo_pendiente=Decimal(total),
                en_cuenta_corriente=True,
                estado_pago='credito',
                observaciones=request.POST.get('observaciones', ''),
                creado_por=request.user
            )
            
            return JsonResponse({'success': True, 'message': f'Documento {documento.numero_documento} creado exitosamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})
    
    proveedores = Proveedor.objects.filter(empresa=empresa, estado='activo')
    context = {'proveedores': proveedores}
    return HttpResponse(render_to_string('tesoreria/includes/documento_form_modal.html', context, request=request))


@login_required
def documento_pendiente_proveedor_edit(request, pk):
    """Editar documento pendiente de proveedor (modal)"""
    empresa = request.empresa if hasattr(request, 'empresa') else request.user.perfil.empresa
    documento = get_object_or_404(DocumentoCompra, pk=pk, empresa=empresa)
    
    if request.method == 'POST':
        try:
            proveedor_id = request.POST.get('proveedor')
            proveedor = get_object_or_404(Proveedor, pk=proveedor_id, empresa=empresa)
            total = int(request.POST.get('total', 0))
            
            documento.proveedor = proveedor
            documento.tipo_documento = request.POST.get('tipo_documento')
            documento.numero_documento = request.POST.get('numero_documento')
            documento.fecha_emision = request.POST.get('fecha_emision')
            documento.fecha_vencimiento = request.POST.get('fecha_vencimiento')
            documento.total_documento = total
            documento.saldo_pendiente = Decimal(total) - documento.monto_pagado
            documento.observaciones = request.POST.get('observaciones', '')
            documento.save()
            
            return JsonResponse({'success': True, 'message': f'Documento {documento.numero_documento} actualizado exitosamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})
    
    proveedores = Proveedor.objects.filter(empresa=empresa, estado='activo')
    context = {'documento': documento, 'proveedores': proveedores}
    return HttpResponse(render_to_string('tesoreria/includes/documento_form_modal.html', context, request=request))


@login_required
@requiere_empresa
def documento_pendiente_proveedor_delete(request, pk):
    """Eliminar documento pendiente de proveedor"""
    empresa = request.empresa if hasattr(request, 'empresa') else request.user.perfil.empresa
    documento = get_object_or_404(DocumentoCompra, pk=pk, empresa=empresa)
    
    if request.method == 'POST':
        numero = documento.numero_documento
        documento.delete()
        return JsonResponse({'success': True, 'message': f'Documento {numero} eliminado exitosamente.'})
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'})


# ==================== CRUD DOCUMENTOS PENDIENTES CLIENTES ====================

@login_required
def obtener_clientes(request):
    """Obtener lista de clientes activos de la empresa"""
    try:
        # Obtener empresa del usuario
        if request.user.is_superuser:
            empresa_id = request.session.get('empresa_activa')
            if empresa_id:
                try:
                    empresa = Empresa.objects.get(id=empresa_id)
                except Empresa.DoesNotExist:
                    empresa = Empresa.objects.first()
            else:
                empresa = Empresa.objects.first()
        else:
            try:
                empresa = request.user.perfil.empresa
            except:
                return JsonResponse({'error': 'Usuario no tiene empresa asociada'}, status=400)
        
        if not empresa:
            return JsonResponse({'error': 'No se encontró empresa'}, status=400)
        
        from clientes.models import Cliente
        clientes = Cliente.objects.filter(empresa=empresa).order_by('nombre')
        
        clientes_data = [{
            'id': cliente.id,
            'nombre': cliente.nombre,
            'rut': cliente.rut or ''
        } for cliente in clientes]
        
        return JsonResponse({'clientes': clientes_data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def crear_documento_cliente(request):
    """Crear documento pendiente de cliente"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'})
    
    try:
        # Obtener empresa del usuario
        if request.user.is_superuser:
            empresa_id = request.session.get('empresa_activa')
            if empresa_id:
                try:
                    empresa = Empresa.objects.get(id=empresa_id)
                except Empresa.DoesNotExist:
                    empresa = Empresa.objects.first()
            else:
                empresa = Empresa.objects.first()
        else:
            try:
                empresa = request.user.perfil.empresa
            except:
                return JsonResponse({'success': False, 'message': 'Usuario no tiene empresa asociada'})
        
        if not empresa:
            return JsonResponse({'success': False, 'message': 'No se encontró empresa'})
        
        from clientes.models import Cliente
        from .models import DocumentoCliente
        
        data = json.loads(request.body)
        
        cliente_id = data.get('cliente')
        cliente = get_object_or_404(Cliente, pk=cliente_id, empresa=empresa)
        
        total = int(data.get('total', 0))
        
        # Crear documento de cliente en cuenta corriente
        documento = DocumentoCliente.objects.create(
            empresa=empresa,
            cliente=cliente,
            tipo_documento=data.get('tipo_documento', 'factura'),
            numero_documento=data.get('numero_documento'),
            fecha_emision=data.get('fecha_emision'),
            fecha_vencimiento=data.get('fecha_vencimiento') or None,
            total=total,
            saldo_pendiente=Decimal(total),
            estado_pago='pendiente',
            observaciones=data.get('observaciones', ''),
            creado_por=request.user
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Documento {documento.numero_documento} creado exitosamente.'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al crear documento: {str(e)}'
        })


@login_required
def historial_pagos_documento_cliente(request, documento_id):
    """Obtener historial de pagos de un documento de cliente"""
    try:
        from .models import DocumentoCliente, PagoDocumentoCliente
        
        documento = get_object_or_404(DocumentoCliente, pk=documento_id)
        pagos = documento.pagos.all().order_by('-fecha_pago')
        
        pagos_data = []
        for pago in pagos:
            pagos_data.append({
                'fecha': pago.fecha_pago.strftime('%d/%m/%Y %H:%M'),
                'monto': float(pago.monto),
                'forma_pago': pago.forma_pago,
                'observaciones': pago.observaciones
            })
        
        return JsonResponse({
            'pagos': pagos_data,
            'total_pagado': float(documento.monto_pagado)
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def registrar_pago_cliente(request):
    """Registrar un pago de cliente con múltiples formas de pago"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'})
    
    try:
        from .models import DocumentoCliente
        
        data = json.loads(request.body)
        
        documento_id = data.get('documento_id')
        formas_pago = data.get('formas_pago', [])
        observaciones = data.get('observaciones', '')
        
        documento = get_object_or_404(DocumentoCliente, pk=documento_id)
        
        # Validar que hay formas de pago
        if not formas_pago:
            return JsonResponse({'success': False, 'message': 'Debe especificar al menos una forma de pago'})
        
        # Calcular monto total
        monto_total = sum(Decimal(str(forma['monto'])) for forma in formas_pago)
        
        # Validar monto
        if monto_total <= 0:
            return JsonResponse({'success': False, 'message': 'El monto debe ser mayor a 0'})
        
        if monto_total > documento.saldo_pendiente:
            return JsonResponse({'success': False, 'message': 'El monto excede el saldo pendiente'})
        
        # Registrar cada forma de pago
        from .models import PagoDocumentoCliente
        
        for forma in formas_pago:
            PagoDocumentoCliente.objects.create(
                documento=documento,
                monto=Decimal(str(forma['monto'])),
                forma_pago=forma['forma_pago'],
                observaciones=observaciones,
                registrado_por=request.user
            )
        
        # Actualizar documento
        documento.monto_pagado += monto_total
        documento.saldo_pendiente -= monto_total
        
        # Actualizar estado
        if documento.saldo_pendiente <= 0:
            documento.estado_pago = 'pagado'
        elif documento.monto_pagado > 0:
            documento.estado_pago = 'parcial'
        
        documento.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Pago registrado exitosamente por ${int(monto_total):,}'.replace(',', '.')
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al procesar el pago: {str(e)}'
        })


@login_required
def obtener_documento_cliente(request, pk):
    """Obtener datos de un documento de cliente"""
    try:
        from .models import DocumentoCliente
        
        # Obtener empresa
        if request.user.is_superuser:
            empresa_id = request.session.get('empresa_activa')
            empresa = Empresa.objects.get(id=empresa_id) if empresa_id else Empresa.objects.first()
        else:
            empresa = request.user.perfil.empresa
        
        documento = get_object_or_404(DocumentoCliente, pk=pk, empresa=empresa)
        
        return JsonResponse({
            'success': True,
            'documento': {
                'id': documento.id,
                'cliente_id': documento.cliente.id,
                'tipo_documento': documento.tipo_documento,
                'numero_documento': documento.numero_documento,
                'fecha_emision': documento.fecha_emision.strftime('%Y-%m-%d'),
                'fecha_vencimiento': documento.fecha_vencimiento.strftime('%Y-%m-%d') if documento.fecha_vencimiento else '',
                'total': int(documento.total),
                'observaciones': documento.observaciones
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al obtener documento: {str(e)}'
        })


@login_required
def editar_documento_cliente(request, pk):
    """Editar documento de cliente"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'})
    
    try:
        from .models import DocumentoCliente
        from clientes.models import Cliente
        
        # Obtener empresa
        if request.user.is_superuser:
            empresa_id = request.session.get('empresa_activa')
            empresa = Empresa.objects.get(id=empresa_id) if empresa_id else Empresa.objects.first()
        else:
            empresa = request.user.perfil.empresa
        
        documento = get_object_or_404(DocumentoCliente, pk=pk, empresa=empresa)
        
        data = json.loads(request.body)
        
        cliente_id = data.get('cliente')
        cliente = get_object_or_404(Cliente, pk=cliente_id, empresa=empresa)
        
        total = int(data.get('total', 0))
        
        # Actualizar documento
        documento.cliente = cliente
        documento.tipo_documento = data.get('tipo_documento')
        documento.numero_documento = data.get('numero_documento')
        documento.fecha_emision = data.get('fecha_emision')
        documento.fecha_vencimiento = data.get('fecha_vencimiento') or None
        documento.total = total
        documento.saldo_pendiente = Decimal(total) - documento.monto_pagado
        documento.observaciones = data.get('observaciones', '')
        documento.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Documento {documento.numero_documento} actualizado exitosamente.'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al actualizar documento: {str(e)}'
        })


@login_required
def eliminar_documento_cliente(request, pk):
    """Eliminar documento de cliente"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'})
    
    try:
        from .models import DocumentoCliente
        
        # Obtener empresa
        if request.user.is_superuser:
            empresa_id = request.session.get('empresa_activa')
            empresa = Empresa.objects.get(id=empresa_id) if empresa_id else Empresa.objects.first()
        else:
            empresa = request.user.perfil.empresa
        
        documento = get_object_or_404(DocumentoCliente, pk=pk, empresa=empresa)
        numero = documento.numero_documento
        documento.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Documento {numero} eliminado exitosamente.'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al eliminar documento: {str(e)}'
        })


@csrf_exempt
@login_required
@requiere_empresa
def registrar_pago_movimiento(request):
    """Registrar pago de un movimiento de cuenta corriente (factura a crédito)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)
    
    try:
        from decimal import Decimal
        import json
        from .models import MovimientoCuentaCorrienteCliente
        from ventas.models import FormaPago
        from django.db import models, transaction
        
        data = json.loads(request.body)
        movimiento_id = data.get('movimiento_id')
        formas_pago = data.get('formas_pago', [])
        observaciones = data.get('observaciones', '')
        
        # Validaciones
        if not movimiento_id:
            return JsonResponse({'success': False, 'message': 'ID de movimiento requerido'}, status=400)
        
        if not formas_pago:
            return JsonResponse({'success': False, 'message': 'Debe especificar al menos una forma de pago'}, status=400)
        
        # Obtener el movimiento
        movimiento = get_object_or_404(
            MovimientoCuentaCorrienteCliente,
            pk=movimiento_id,
            cuenta_corriente__empresa=request.empresa
        )
        
        # Calcular monto total del pago
        monto_total_pago = sum(Decimal(str(fp['monto'])) for fp in formas_pago)
        
        # Validar que el monto no exceda el monto del movimiento
        if monto_total_pago > movimiento.monto:
            return JsonResponse({
                'success': False,
                'message': f'El monto total ({monto_total_pago}) excede el monto de la factura ({movimiento.monto})'
            }, status=400)
        
        # Registrar el pago como un movimiento HABER (abono)
        with transaction.atomic():
            cuenta = movimiento.cuenta_corriente
            saldo_anterior = cuenta.saldo_pendiente
            
            # Crear movimiento de pago (HABER)
            movimiento_pago = MovimientoCuentaCorrienteCliente.objects.create(
                cuenta_corriente=cuenta,
                venta=movimiento.venta,  # Relacionar con la misma venta
                tipo_movimiento='haber',  # Pago recibido
                monto=monto_total_pago,
                saldo_anterior=saldo_anterior,
                saldo_nuevo=saldo_anterior - monto_total_pago,
                estado='confirmado',
                observaciones=f"Pago de factura #{movimiento.venta.numero_venta if movimiento.venta else 'N/A'}. {observaciones}",
                registrado_por=request.user
            )
            
            # Registrar en DocumentoCliente y PagoDocumentoCliente
            if movimiento.venta:
                from .models import DocumentoCliente, PagoDocumentoCliente
                
                print(f"DEBUG PAGO: Buscando documento para factura {movimiento.venta.numero_venta}")
                print(f"DEBUG PAGO: Empresa: {request.empresa.nombre}")
                
                try:
                    documento = DocumentoCliente.objects.get(
                        empresa=request.empresa,
                        numero_documento=movimiento.venta.numero_venta
                    )
                    
                    print(f"✓ Documento encontrado: ID={documento.id}, Número={documento.numero_documento}")
                    
                    # Registrar cada forma de pago
                    for forma in formas_pago:
                        # Obtener el nombre de la forma de pago
                        forma_pago_nombre = forma.get('forma_pago', None)
                        if not forma_pago_nombre and 'forma_pago_id' in forma:
                            # Si viene el ID, obtener el nombre
                            try:
                                forma_pago_obj = FormaPago.objects.get(id=forma['forma_pago_id'])
                                forma_pago_nombre = forma_pago_obj.nombre
                            except FormaPago.DoesNotExist:
                                forma_pago_nombre = 'No especificado'
                        
                        pago_creado = PagoDocumentoCliente.objects.create(
                            documento=documento,
                            monto=Decimal(str(forma['monto'])),
                            forma_pago=forma_pago_nombre or 'No especificado',
                            observaciones=observaciones,
                            registrado_por=request.user
                        )
                        print(f"✓ Pago creado: ID={pago_creado.id}, Monto=${pago_creado.monto}, Forma={pago_creado.forma_pago}")
                    
                    # Actualizar documento
                    documento.monto_pagado += monto_total_pago
                    documento.saldo_pendiente -= monto_total_pago
                    
                    if documento.saldo_pendiente <= 0:
                        documento.estado_pago = 'pagado'
                    elif documento.monto_pagado > 0:
                        documento.estado_pago = 'parcial'
                    
                    documento.save()
                    print(f"✓ Documento actualizado: Pagado=${documento.monto_pagado}, Saldo=${documento.saldo_pendiente}")
                    
                except DocumentoCliente.DoesNotExist:
                    print(f"⚠ ERROR: No se encontró documento para factura {movimiento.venta.numero_venta}")
                    print(f"⚠ Buscando con: empresa={request.empresa.id}, numero_documento={movimiento.venta.numero_venta}")
                    # Listar documentos existentes para debug
                    docs = DocumentoCliente.objects.filter(empresa=request.empresa).values_list('numero_documento', flat=True)
                    print(f"⚠ Documentos existentes: {list(docs)[:10]}")
            
            # Actualizar saldo de la cuenta corriente
            cuenta.saldo_pendiente -= monto_total_pago
            cuenta.save()
            
            # Si el movimiento original está completamente pagado, marcarlo como anulado
            # (porque ya fue pagado)
            total_pagado = MovimientoCuentaCorrienteCliente.objects.filter(
                cuenta_corriente=cuenta,
                venta=movimiento.venta,
                tipo_movimiento='haber'
            ).aggregate(total=models.Sum('monto'))['total'] or Decimal('0')
            
            if total_pagado >= movimiento.monto:
                # Marcar como completamente pagado agregando observación
                movimiento.observaciones += f"\n[PAGADO] Total pagado: ${total_pagado}"
                movimiento.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Pago de ${monto_total_pago:,.0f} registrado exitosamente'
        })
        
    except Exception as e:
        import traceback
        print(f"Error al registrar pago: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'message': f'Error al registrar pago: {str(e)}'
        }, status=500)


@login_required
@requiere_empresa
def historial_pagos_movimiento(request, movimiento_id):
    """Obtener historial de pagos de un movimiento de cuenta corriente"""
    try:
        from .models import MovimientoCuentaCorrienteCliente
        from django.db.models import Sum
        
        # Obtener el movimiento original (debe)
        movimiento = get_object_or_404(
            MovimientoCuentaCorrienteCliente,
            pk=movimiento_id,
            cuenta_corriente__empresa=request.empresa,
            tipo_movimiento='debe'
        )
        
        # Buscar si existe un documento asociado a esta venta
        from .models import DocumentoCliente, PagoDocumentoCliente
        
        try:
            # Buscar documento por número de factura
            if movimiento.venta:
                print(f"DEBUG: Buscando documento para factura {movimiento.venta.numero_venta}")
                documento = DocumentoCliente.objects.filter(
                    empresa=request.empresa,
                    numero_documento=movimiento.venta.numero_venta
                ).first()
                
                if documento:
                    print(f"DEBUG: Documento encontrado: {documento.id}")
                    # Usar pagos del nuevo sistema
                    pagos_nuevos = documento.pagos.all().order_by('-fecha_pago')
                    print(f"DEBUG: Pagos encontrados en nuevo sistema: {pagos_nuevos.count()}")
                    
                    pagos_data = []
                    for pago in pagos_nuevos:
                        print(f"DEBUG: Pago - Monto: {pago.monto}, Forma: {pago.forma_pago}")
                        pagos_data.append({
                            'id': pago.pk,
                            'fecha': pago.fecha_pago.strftime('%d/%m/%Y %H:%M'),
                            'monto': float(pago.monto),
                            'forma_pago': pago.forma_pago,
                            'observaciones': pago.observaciones,
                            'registrado_por': pago.registrado_por.get_full_name() or pago.registrado_por.username
                        })
                    total_pagado = sum(float(p.monto) for p in pagos_nuevos)
                else:
                    print(f"DEBUG: No se encontró documento para factura {movimiento.venta.numero_venta}")
                    # Usar movimientos antiguos
                    pagos = MovimientoCuentaCorrienteCliente.objects.filter(
                        cuenta_corriente=movimiento.cuenta_corriente,
                        venta=movimiento.venta,
                        tipo_movimiento='haber'
                    ).order_by('-fecha_movimiento')
                    
                    pagos_data = []
                    for pago in pagos:
                        pagos_data.append({
                            'id': pago.pk,
                            'fecha': pago.fecha_movimiento.strftime('%d/%m/%Y %H:%M'),
                            'monto': float(pago.monto),
                            'forma_pago': 'No especificado',
                            'observaciones': pago.observaciones,
                            'registrado_por': pago.registrado_por.get_full_name() or pago.registrado_por.username
                        })
                    
                    from django.db.models import Sum
                    total_pagado = float(pagos.aggregate(total=Sum('monto'))['total'] or 0)
            else:
                pagos_data = []
                total_pagado = 0
        except Exception as e:
            print(f"Error buscando pagos: {e}")
            pagos_data = []
            total_pagado = 0
        
        return JsonResponse({
            'success': True,
            'pagos': pagos_data,
            'total_pagado': float(total_pagado),
            'monto_factura': float(movimiento.monto),
            'saldo_pendiente': float(Decimal(str(movimiento.monto)) - Decimal(str(total_pagado)))
        })
        
    except Exception as e:
        import traceback
        print(f"Error al obtener historial: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'message': f'Error al obtener historial: {str(e)}'
        }, status=500)