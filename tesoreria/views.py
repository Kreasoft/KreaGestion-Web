from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from decimal import Decimal

from .models import CuentaCorrienteProveedor, MovimientoCuentaCorriente
from documentos.models import DocumentoCompra
from proveedores.models import Proveedor
from empresas.models import Empresa
from .decorators import requiere_empresa


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
    
    proveedor = get_object_or_404(Proveedor, pk=proveedor_id, empresa=empresa)
    
    # Obtener documentos del proveedor
    documentos = DocumentoCompra.objects.filter(
        empresa=empresa,
        proveedor=proveedor,
        en_cuenta_corriente=True
    ).order_by('fecha_vencimiento')
    
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
@permission_required('tesoreria.view_cuentacorriente', raise_exception=True)
def cuenta_corriente_cliente_list(request):
    """Lista de cuentas corrientes de clientes (placeholder)"""
    # Obtener la empresa del usuario
    if request.user.is_superuser:
        empresa = Empresa.objects.first()
        if not empresa:
            messages.error(request, 'No hay empresas configuradas en el sistema.')
            return redirect('dashboard')
    else:
        try:
            empresa = request.user.perfil.empresa
        except:
            messages.error(request, 'Usuario no tiene empresa asociada.')
            return redirect('dashboard')
    
    # Por ahora mostrar una página simple que indica que está en desarrollo
    context = {
        'empresa': empresa,
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
            empresa_id = request.POST.get('empresa_id')
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