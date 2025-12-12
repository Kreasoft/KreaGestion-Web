from utilidades.utils import clean_id
"""
Vistas para el módulo de empresas
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.http import JsonResponse
from core.decorators import requiere_empresa, solo_superusuario
from usuarios.decorators import filtrar_por_empresa
from .models import Empresa, Sucursal, ConfiguracionEmpresa
from .forms import EmpresaForm, SucursalForm, ConfiguracionEmpresaForm, FacturacionElectronicaForm


@requiere_empresa
def home(request):
	"""
	Página principal - redirige según el tipo de usuario
	"""
	if request.user.is_superuser:
		# Superusuario ve lista de todas las empresas
		empresas = Empresa.objects.all()
		if not empresas.exists():
			# Si no hay empresas, redirigir a crear una
			messages.info(request, 'No hay empresas registradas. Debe crear una empresa primero.')
			return redirect('empresas:empresa_create')
		return render(request, 'empresas/admin_dashboard.html', {'empresas': empresas})
	else:
		# Usuario normal ve dashboard de su empresa
		empresa = request.empresa
		
		# Si no hay empresa asignada, redirigir a crear una
		if not empresa:
			messages.error(request, 'No tiene acceso a ninguna empresa. Contacte al administrador.')
			return redirect('logout')
		
		# Obtener sucursal activa (principal o primera disponible)
		sucursal_activa = empresa.sucursales.filter(es_principal=True).first()
		if not sucursal_activa:
			sucursal_activa = empresa.sucursales.first()
		
		# Importar modelos de productos para estadísticas
		from django.db.models import Sum, Q, F
		from datetime import datetime
		
		# Estadísticas de productos (temporalmente deshabilitado)
		total_productos = 0
		productos_con_stock = 0
		productos_stock_bajo = 0
		productos_sin_stock = 0
		productos_activos = 0
		total_categorias = 0
		total_unidades_medida = 0
		
		# Valor total del inventario (temporalmente deshabilitado)
		valor_total_inventario = 0
		productos_recientes = []
		productos_stock_bajo_list = []
		
		# Fecha y hora actual
		fecha_actual = datetime.now()
		hora_actual = datetime.now()
		
		context = {
			'empresa': empresa,
			'sucursal_activa': sucursal_activa,
			'total_productos': total_productos,
			'productos_con_stock': productos_con_stock,
			'productos_stock_bajo': productos_stock_bajo,
			'productos_sin_stock': productos_sin_stock,
			'productos_activos': productos_activos,
			'total_categorias': total_categorias,
			'total_unidades_medida': total_unidades_medida,
			'valor_total_inventario': valor_total_inventario,
			'productos_recientes': productos_recientes,
			'productos_stock_bajo_list': productos_stock_bajo_list,
			'fecha_actual': fecha_actual,
			'hora_actual': hora_actual,
		}
		
		return render(request, 'empresas/empresa_dashboard.html', context)


@solo_superusuario
@permission_required('empresas.view_empresa', raise_exception=True)
def empresa_list(request):
	"""Lista todas las empresas - solo superusuario"""
	empresas = Empresa.objects.all()
	return render(request, 'empresas/empresa_list.html', {'empresas': empresas})


@solo_superusuario
@permission_required('empresas.add_empresa', raise_exception=True)
def empresa_create(request):
	"""Crea una nueva empresa - solo superusuario"""
	import logging
	from utilidades.error_handling import validar_y_mostrar_errores, manejar_error_guardado
	
	logger = logging.getLogger(__name__)
	
	if request.method == 'POST':
		# Crear una copia mutable del POST para poder corregir valores
		post_data = request.POST.copy()
		
		# CORRECCIONES AUTOMÁTICAS ANTES DE VALIDAR
		# Corregir regimen_tributario si viene con valor inválido
		if 'regimen_tributario' in post_data:
			valor_regimen = post_data['regimen_tributario'].lower()
			mapeo_correcciones = {
				'general': '19',
				'iva': '19',
				'19%': '19',
			}
			if valor_regimen in mapeo_correcciones:
				post_data['regimen_tributario'] = mapeo_correcciones[valor_regimen]
				messages.info(request, f'💡 Se corrigió automáticamente "Régimen Tributario" de "{request.POST.get("regimen_tributario")}" a "19% IVA"')
		
		# Aplicar valores por defecto para campos vacíos de ConfiguracionEmpresa
		valores_defecto_config = {
			'prefijo_ajustes': 'AJU',
			'siguiente_ajuste': '1',
			'formato_ajustes': '{prefijo}-{000}',  # Formato corto (15 caracteres, límite es 20)
			'prefijo_orden_compra': 'OC',
			'siguiente_orden_compra': '1',
			'formato_orden_compra': '{prefijo}-{000}',  # Formato corto (15 caracteres, límite es 20)
			'frecuencia_respaldo': 'diario',
		}
		for campo, valor_defecto in valores_defecto_config.items():
			if campo not in post_data or not post_data[campo]:
				post_data[campo] = valor_defecto
		
		# Aplicar valores por defecto para campos vacíos de Empresa
		if 'regimen_tributario' not in post_data or not post_data['regimen_tributario']:
			post_data['regimen_tributario'] = '19'
		if 'ambiente_sii' not in post_data or not post_data['ambiente_sii']:
			post_data['ambiente_sii'] = 'certificacion'
		if 'estado' not in post_data or not post_data['estado']:
			post_data['estado'] = 'activa'
		if 'max_descuento_lineal' not in post_data or not post_data['max_descuento_lineal']:
			post_data['max_descuento_lineal'] = '0'
		if 'max_descuento_total' not in post_data or not post_data['max_descuento_total']:
			post_data['max_descuento_total'] = '0'
		if 'alerta_folios_minimos' not in post_data or not post_data['alerta_folios_minimos']:
			post_data['alerta_folios_minimos'] = '10'
		# Campo giro ahora es opcional, pero si está vacío, usar valor por defecto
		if 'giro' not in post_data or not post_data['giro'] or not post_data['giro'].strip():
			post_data['giro'] = ''  # Vacío es válido ahora
		
		form = EmpresaForm(post_data, request.FILES)
		config_form = ConfiguracionEmpresaForm(post_data)
		fe_form = FacturacionElectronicaForm(post_data, request.FILES)

		logger.info("=== INICIO VALIDACIÓN EMPRESA ===")
		logger.info(f"Form empresa válido: {form.is_valid()}")
		logger.info(f"Form config válido: {config_form.is_valid()}")
		logger.info(f"Form FE válido: {fe_form.is_valid()}")

		# Validar todos los formularios y mostrar errores claros
		todos_validos = validar_y_mostrar_errores(
			request,
			('Formulario de Empresa', form),
			('Configuración', config_form),
			('Facturación Electrónica', fe_form)
		)

		logger.info(f"Todos válidos: {todos_validos}")

		if todos_validos:
			try:
				logger.info("Intentando guardar empresa...")
				# Guardar empresa
				empresa = form.save(commit=False)
				empresa.creado_por = request.user
				logger.info(f"Guardando empresa: {empresa.nombre}")
				empresa.save()
				logger.info(f"Empresa guardada con ID: {empresa.pk}")

				# Guardar configuración
				logger.info("Guardando configuración...")
				configuracion = config_form.save(commit=False)
				configuracion.empresa = empresa
				configuracion.save()
				logger.info("Configuración guardada")

				# Guardar configuración de FE
				logger.info("Guardando configuración FE...")
				fe_config = fe_form.save(commit=False)
				empresa.facturacion_electronica = fe_config.facturacion_electronica
				empresa.ambiente_sii = fe_config.ambiente_sii
				empresa.certificado_digital = fe_config.certificado_digital
				empresa.password_certificado = fe_config.password_certificado
				empresa.save()
				logger.info("Configuración FE guardada")

				messages.success(request, f'✅ Empresa "{empresa.nombre}" creada exitosamente.')
				logger.info("=== EMPRESA CREADA EXITOSAMENTE ===")
				return redirect('empresas:empresa_list')
			except Exception as e:
				logger.exception(f"ERROR AL GUARDAR EMPRESA: {e}")
				manejar_error_guardado(request, e, {'accion': 'crear empresa'})
				# IMPORTANTE: Continuar para mostrar el formulario con errores
				# NO hacer return aquí, dejar que se renderice el template con los mensajes
		else:
			logger.warning("Formularios no válidos, mostrando errores...")
			# Los errores ya fueron mostrados por validar_y_mostrar_errores
			# Pero asegurémonos de que se muestren también en el template
			if not form.is_valid():
				logger.error(f"Errores en form empresa: {form.errors}")
			if not config_form.is_valid():
				logger.error(f"Errores en form config: {config_form.errors}")
			if not fe_form.is_valid():
				logger.error(f"Errores en form FE: {fe_form.errors}")
			# Asegurar mensaje si no hay errores específicos
			from django.contrib.messages import get_messages
			if not list(get_messages(request)):
				messages.error(request, '❌ No se pudo procesar el formulario. Por favor, revise los datos ingresados.')
	else:
		# Crear formularios con valores por defecto
		form = EmpresaForm()
		config_form = ConfiguracionEmpresaForm()
		fe_form = FacturacionElectronicaForm()
		
		# Asegurar que los valores por defecto se establezcan
		# (ya se hace en __init__ de los forms, pero por si acaso)

	context = {
		'form': form,
		'config_form': config_form,
		'fe_form': fe_form,
		'empresa': None,
		'configuracion': None,
		'sucursales': None,
		'titulo': 'Nueva Empresa',
		'is_create': True
	}

	logger.info("Renderizando template...")
	return render(request, 'empresas/editar_empresa_activa.html', context)


@solo_superusuario
def empresa_detail(request, pk):
	"""Muestra los detalles de una empresa - solo superusuario"""
	empresa = get_object_or_404(Empresa, pk=pk)
	return render(request, 'empresas/empresa_detail.html', {'empresa': empresa})


@solo_superusuario
@permission_required('empresas.change_empresa', raise_exception=True)
def empresa_update(request, pk):
	"""Actualiza una empresa existente - solo superusuario"""
	import logging
	from utilidades.error_handling import validar_y_mostrar_errores, manejar_error_guardado
	
	logger = logging.getLogger(__name__)
	empresa = get_object_or_404(Empresa, pk=pk)
	
	# Obtener o crear configuración
	try:
		configuracion = ConfiguracionEmpresa.objects.get(empresa=empresa)
	except ConfiguracionEmpresa.DoesNotExist:
		configuracion = ConfiguracionEmpresa.objects.create(empresa=empresa)
	
	if request.method == 'POST':
		# Crear una copia mutable del POST para poder corregir valores
		post_data = request.POST.copy()
		
		# CORRECCIONES AUTOMÁTICAS ANTES DE VALIDAR (igual que en create)
		if 'regimen_tributario' in post_data:
			valor_regimen = post_data['regimen_tributario'].lower()
			mapeo_correcciones = {
				'general': '19',
				'iva': '19',
				'19%': '19',
			}
			if valor_regimen in mapeo_correcciones:
				post_data['regimen_tributario'] = mapeo_correcciones[valor_regimen]
		
		# Aplicar valores por defecto para campos vacíos
		valores_defecto_config = {
			'prefijo_ajustes': 'AJU',
			'siguiente_ajuste': '1',
			'formato_ajustes': '{prefijo}-{000}',
			'prefijo_orden_compra': 'OC',
			'siguiente_orden_compra': '1',
			'formato_orden_compra': '{prefijo}-{000}',
			'frecuencia_respaldo': 'diario',
		}
		for campo, valor_defecto in valores_defecto_config.items():
			if campo not in post_data or not post_data[campo]:
				post_data[campo] = valor_defecto
		
		form = EmpresaForm(post_data, request.FILES, instance=empresa)
		config_form = ConfiguracionEmpresaForm(post_data, instance=configuracion)
		fe_form = FacturacionElectronicaForm(post_data, request.FILES, instance=empresa)

		# Validar todos los formularios
		todos_validos = validar_y_mostrar_errores(
			request,
			('Formulario de Empresa', form),
			('Configuración', config_form),
			('Facturación Electrónica', fe_form)
		)

		if todos_validos:
			try:
				# Guardar empresa
				empresa = form.save(commit=False)
				empresa.save()

				# Guardar configuración
				configuracion = config_form.save(commit=False)
				configuracion.empresa = empresa
				configuracion.save()

				# Guardar configuración de FE
				fe_config = fe_form.save(commit=False)
				empresa.facturacion_electronica = fe_config.facturacion_electronica
				empresa.ambiente_sii = fe_config.ambiente_sii
				empresa.certificado_digital = fe_config.certificado_digital
				empresa.password_certificado = fe_config.password_certificado
				empresa.save()

				messages.success(request, f'✅ Empresa "{empresa.nombre}" actualizada exitosamente.')
				return redirect('empresas:empresa_detail', pk=pk)
			except Exception as e:
				logger.exception(f"ERROR AL GUARDAR EMPRESA: {e}")
				manejar_error_guardado(request, e, {'accion': 'actualizar empresa'})
	else:
		form = EmpresaForm(instance=empresa)
		config_form = ConfiguracionEmpresaForm(instance=configuracion)
		fe_form = FacturacionElectronicaForm(instance=empresa)
	
	# Obtener sucursales
	sucursales = empresa.sucursales.all().order_by('-es_principal', 'nombre')
	
	context = {
		'form': form,
		'config_form': config_form,
		'fe_form': fe_form,
		'empresa': empresa,
		'configuracion': configuracion,
		'sucursales': sucursales,
		'titulo': f'Editar Empresa: {empresa.nombre}',
		'is_create': False
	}
	
	return render(request, 'empresas/editar_empresa_activa.html', context)


@solo_superusuario
def empresa_delete(request, pk):
	"""Elimina una empresa - solo superusuario"""
	empresa = get_object_or_404(Empresa, pk=pk)
	if request.method == 'POST':
		empresa.delete()
		messages.success(request, 'Empresa eliminada exitosamente.')
		return redirect('empresas:empresa_list')
	
	return render(request, 'empresas/empresa_confirm_delete.html', {'empresa': empresa})


@requiere_empresa
@permission_required('empresas.view_sucursal', raise_exception=True)
def sucursal_list(request, empresa_id=None):
	"""
	Lista las sucursales - superusuario puede especificar empresa, usuario normal ve solo las suyas
	"""
	if request.user.is_superuser:
		if empresa_id:
			empresa = get_object_or_404(Empresa, pk=empresa_id)
		else:
			empresa = None
		sucursales = Sucursal.objects.filter(empresa=empresa) if empresa else Sucursal.objects.all()
	else:
		empresa = request.empresa
		sucursales = empresa.sucursales.all()
	
	return render(request, 'empresas/sucursal_list.html', {
		'empresa': empresa,
		'sucursales': sucursales
	})


@requiere_empresa
@permission_required('empresas.add_sucursal', raise_exception=True)
def sucursal_create(request, empresa_id=None):
	"""
	Crea una nueva sucursal - superusuario puede especificar empresa, usuario normal crea en su empresa
	"""
	if request.user.is_superuser:
		if empresa_id:
			empresa = get_object_or_404(Empresa, pk=empresa_id)
		else:
			empresa = None
	else:
		empresa = request.empresa
	
	if request.method == 'POST':
		form = SucursalForm(request.POST)
		if form.is_valid():
			sucursal = form.save(commit=False)
			sucursal.empresa = empresa
			sucursal.creado_por = request.user
			sucursal.save()
			
			messages.success(request, 'Sucursal creada exitosamente.')
			if empresa_id:
				return redirect('empresas:sucursal_list', empresa_id=empresa_id)
			else:
				return redirect('empresas:sucursal_list')
	else:
		form = SucursalForm()
	
	return render(request, 'empresas/sucursal_form.html', {'form': form, 'empresa': empresa})


@requiere_empresa
def sucursal_detail(request, pk):
	"""
	Muestra los detalles de una sucursal - verifica que pertenezca a la empresa del usuario
	"""
	sucursal = get_object_or_404(Sucursal, pk=pk)
	
	# Verificar que el usuario tenga acceso a esta sucursal
	if not request.user.is_superuser and sucursal.empresa != request.empresa:
		messages.error(request, 'No tiene acceso a esta sucursal.')
		return redirect('dashboard')
	
	return render(request, 'empresas/sucursal_detail.html', {'sucursal': sucursal})


@requiere_empresa
@permission_required('empresas.change_sucursal', raise_exception=True)
def sucursal_update(request, pk):
	"""
	Actualiza una sucursal - verifica que pertenezca a la empresa del usuario
	"""
	sucursal = get_object_or_404(Sucursal, pk=pk)
	
	# Verificar que el usuario tenga acceso a esta sucursal
	if not request.user.is_superuser and sucursal.empresa != request.empresa:
		messages.error(request, 'No tiene acceso a esta sucursal.')
		return redirect('dashboard')
	
	if request.method == 'POST':
		form = SucursalForm(request.POST, instance=sucursal)
		if form.is_valid():
			form.save()
			messages.success(request, 'Sucursal actualizada exitosamente.')
			return redirect('empresas:sucursal_detail', pk=pk)
	else:
		form = SucursalForm(instance=sucursal)
	
	return render(request, 'empresas/sucursal_form.html', {'form': form, 'sucursal': sucursal})


@requiere_empresa
@permission_required('empresas.delete_sucursal', raise_exception=True)
def sucursal_delete(request, pk):
	"""
	Elimina una sucursal - verifica que pertenezca a la empresa del usuario
	"""
	sucursal = get_object_or_404(Sucursal, pk=pk)
	
	# Verificar que el usuario tenga acceso a esta sucursal
	if not request.user.is_superuser and sucursal.empresa != request.empresa:
		messages.error(request, 'No tiene acceso a esta sucursal.')
		return redirect('dashboard')
	
	if request.method == 'POST':
		sucursal.delete()
		messages.success(request, 'Sucursal eliminada exitosamente.')
		return redirect('empresas:sucursal_list')
	
	return render(request, 'empresas/sucursal_confirm_delete.html', {'sucursal': sucursal})


@requiere_empresa
def empresa_configuracion(request):
	"""
	Vista para configurar datos de la empresa
	"""
	empresa = request.empresa
	
	# Si no hay empresa asignada, redirigir a crear una
	if not empresa:
		if request.user.is_superuser:
			messages.info(request, 'Primero debe crear una empresa.')
			return redirect('empresas:empresa_create')
		else:
			messages.error(request, 'No tiene acceso a ninguna empresa. Contacte al administrador.')
			return redirect('logout')
	
	# Obtener o crear configuración
	try:
		configuracion = ConfiguracionEmpresa.objects.get(empresa=empresa)
	except ConfiguracionEmpresa.DoesNotExist:
		configuracion = ConfiguracionEmpresa.objects.create(empresa=empresa)
	
	if request.method == 'POST':
		form = ConfiguracionEmpresaForm(request.POST, instance=configuracion)
		if form.is_valid():
			configuracion = form.save(commit=False)
			configuracion.empresa = empresa
			configuracion.save()
			messages.success(request, 'Configuración actualizada exitosamente.')
			return redirect('empresas:empresa_configuracion')
	else:
		form = ConfiguracionEmpresaForm(instance=configuracion)
	
	context = {
		'empresa': empresa,
		'form': form,
		'configuracion': configuracion,
	}
	
	return render(request, 'empresas/empresa_configuracion.html', context)


@requiere_empresa
def empresa_configuracion(request):
    """
    Vista para configurar datos de la empresa
    """
    empresa = request.empresa
    
    if not empresa:
        if request.user.is_superuser:
            messages.info(request, 'Primero debe crear una empresa.')
            return redirect('empresas:empresa_create')
        else:
            messages.error(request, 'No tiene acceso a ninguna empresa. Contacte al administrador.')
            return redirect('logout')
    
    if request.method == 'POST':
        form = EmpresaForm(request.POST, instance=empresa)
        if form.is_valid():
            form.save()
            messages.success(request, 'Configuración actualizada exitosamente.')
            return redirect('empresas:empresa_configuracion')
    else:
        form = EmpresaForm(instance=empresa)
    
    context = {
        'empresa': empresa,
        'form': form,
        'titulo': 'Configuraciones Generales',
    }
    
    return render(request, 'empresas/empresa_configuracion.html', context)


@requiere_empresa
def empresa_configuraciones(request):
    empresa = request.empresa
    if request.method == 'POST':
        form = EmpresaForm(request.POST, instance=empresa)
        if form.is_valid():
            form.save()
            messages.success(request, 'Configuraciones guardadas exitosamente.')
            return redirect('empresas:empresa_configuraciones')
    else:
        form = EmpresaForm(instance=empresa)

    context = {
        'form': form,
        'empresa': empresa,
        'titulo': 'Configuraciones Generales'
    }
    return render(request, 'empresas/empresa_configuraciones_form.html', context)

def paleta_colores(request):
	"""
	Vista para mostrar la paleta de colores del sistema
	"""
	return render(request, 'paleta_colores.html')


def seleccionar_empresa(request):
	"""
	Vista para que superusuarios seleccionen una empresa activa
	"""
	if not request.user.is_superuser:
		messages.error(request, 'Solo los administradores pueden cambiar de empresa.')
		return redirect('dashboard')
	
	empresas = Empresa.objects.all()
	empresa_actual = request.empresa
	
	empresa_id_get = clean_id(request.GET.get('empresa_id'))
	if request.method == 'POST' or empresa_id_get:
		empresa_id = clean_id(request.POST.get('empresa_id')) or empresa_id_get
		if empresa_id:
			try:
				empresa = Empresa.objects.get(id=empresa_id)
				# Guardar la empresa seleccionada en la sesión
				request.session['empresa_activa_id'] = empresa.id
				request.session.modified = True  # Forzar guardado
				
				# Crear respuesta con cookie
				response = redirect('dashboard')
				response.set_cookie(
					'empresa_activa_id',
					empresa.id,
					max_age=30*24*60*60,  # 30 días
					httponly=True,
					samesite='Lax'
				)
				
				messages.success(request, f'✓ Empresa cambiada a: {empresa.nombre}')
				return response
			except Empresa.DoesNotExist:
				messages.error(request, 'Empresa no encontrada.')
	
	context = {
		'empresas': empresas,
		'empresa_actual': empresa_actual,
	}
	
	return render(request, 'empresas/seleccionar_empresa.html', context)


def editar_empresa_activa(request):
	"""
	Vista para editar la empresa activa
	"""
	if not request.user.is_superuser:
		messages.error(request, 'Solo los administradores pueden editar empresas.')
		return redirect('dashboard')

	empresa_activa = request.empresa
	if not empresa_activa:
		messages.error(request, 'No hay empresa activa para editar.')
		return redirect('dashboard')

	# Obtener o crear configuración
	try:
		configuracion = ConfiguracionEmpresa.objects.get(empresa=empresa_activa)
	except ConfiguracionEmpresa.DoesNotExist:
		configuracion = ConfiguracionEmpresa.objects.create(empresa=empresa_activa)

	# Inicializar formularios
	form = EmpresaForm(instance=empresa_activa)
	config_form = ConfiguracionEmpresaForm(instance=configuracion)
	fe_form = FacturacionElectronicaForm(instance=empresa_activa)
	
	if request.method == 'POST':
		print(f"DEBUG - POST recibido: {request.POST}")
		print(f"DEBUG - FILES recibidos: {request.FILES}")
		
		# Determinar qué formulario se está enviando
		form_type = request.POST.get('form_type')

		if form_type == 'configuraciones':
			from .forms import ConfiguracionesGeneralesForm
			config_gen_form = ConfiguracionesGeneralesForm(request.POST, instance=empresa_activa)
			if config_gen_form.is_valid():
				config_gen_form.save()
				messages.success(request, 'Configuraciones generales guardadas correctamente.')
				return redirect('empresas:editar_empresa_activa')
			else:
				error_list = []
				for field, errors in config_gen_form.errors.items():
					for error in errors:
						error_list.append(f"{field}: {error}")
				if error_list:
					messages.error(request, f"Hubo errores en el formulario de configuraciones: {', '.join(error_list)}")
				else:
					messages.error(request, 'Hubo un error al guardar las configuraciones.')

		# Si tiene certificado_digital o resolucion_fecha, es el formulario FE específico
		elif 'certificado_digital' in request.FILES or 'resolucion_fecha' in request.POST or 'resolucion_numero' in request.POST:
			fe_form = FacturacionElectronicaForm(request.POST, request.FILES, instance=empresa_activa)
			if fe_form.is_valid():
				fe_form.save()
				messages.success(request, 'Configuración de Facturación Electrónica guardada correctamente.')
				return redirect('empresas:editar_empresa_activa')
			else:
				messages.error(request, 'Hubo errores en el formulario de Facturación Electrónica.')
		# Si tiene prefijo_ajustes pero NO tiene nombre/rut, es el formulario de folios
		elif 'prefijo_ajustes' in request.POST and 'nombre' not in request.POST:
			# Solo actualizar configuración, mantener datos de empresa
			configuracion.prefijo_ajustes = request.POST.get('prefijo_ajustes', 'Aju')
			configuracion.siguiente_ajuste = int(request.POST.get('siguiente_ajuste', 1))
			configuracion.formato_ajustes = request.POST.get('formato_ajustes', '{prefijo}-{000}')
			
			# Configuración de órdenes de compra
			configuracion.prefijo_orden_compra = request.POST.get('prefijo_orden_compra', 'OC')
			configuracion.siguiente_orden_compra = int(request.POST.get('siguiente_orden_compra', 1))
			configuracion.formato_orden_compra = request.POST.get('formato_orden_compra', '{prefijo}-{000}')
			
			configuracion.save()
			print(f"DEBUG - Solo configuración guardada: {configuracion}")
			messages.success(request, 'Configuración de folios actualizada correctamente.')
			return redirect('empresas:editar_empresa_activa')
		else:
			# Actualizar datos de empresa
			form = EmpresaForm(request.POST, request.FILES, instance=empresa_activa)
			
			# Manejar configuración manualmente si está presente
			if 'prefijo_ajustes' in request.POST:
				configuracion.prefijo_ajustes = request.POST.get('prefijo_ajustes', configuracion.prefijo_ajustes)
				configuracion.siguiente_ajuste = int(request.POST.get('siguiente_ajuste', configuracion.siguiente_ajuste))
				configuracion.formato_ajustes = request.POST.get('formato_ajustes', configuracion.formato_ajustes)
				
				# Configuración de órdenes de compra
				configuracion.prefijo_orden_compra = request.POST.get('prefijo_orden_compra', configuracion.prefijo_orden_compra)
				configuracion.siguiente_orden_compra = int(request.POST.get('siguiente_orden_compra', configuracion.siguiente_orden_compra))
				configuracion.formato_orden_compra = request.POST.get('formato_orden_compra', configuracion.formato_orden_compra)
			
			print(f"DEBUG - Form válido: {form.is_valid()}")
			print(f"DEBUG - Logo en FILES: {'logo' in request.FILES}")
			if 'logo' in request.FILES:
				print(f"DEBUG - Archivo logo: {request.FILES['logo'].name}, tamaño: {request.FILES['logo'].size}")
			print(f"DEBUG - Configuración: {configuracion.prefijo_ajustes}, {configuracion.siguiente_ajuste}, {configuracion.formato_ajustes}")
			
			if form.is_valid():
				empresa_guardada = form.save()
				configuracion.save()
				print(f"DEBUG - Empresa guardada: {empresa_guardada}")
				print(f"DEBUG - Logo guardado: {empresa_guardada.logo}")
				print(f"DEBUG - Configuración guardada: {configuracion}")
				messages.success(request, f'Empresa "{empresa_activa.nombre}" actualizada correctamente.')
				return redirect('dashboard')
			else:
				print(f"DEBUG - Errores del formulario: {form.errors}")
				for field, errors in form.errors.items():
					for error in errors:
						messages.error(request, f'{field}: {error}')
				messages.error(request, 'Hubo errores en el formulario.')

	# Obtener sucursales de la empresa
	sucursales = empresa_activa.sucursales.all().order_by('-es_principal', 'nombre')
	
	context = {
		'form': form,
		'config_form': config_form,
		'fe_form': fe_form,
		'empresa': empresa_activa,
		'configuracion': configuracion,
		'sucursales': sucursales,
		'titulo': f'Editar Empresa: {empresa_activa.nombre}',
	}

	return render(request, 'empresas/editar_empresa_activa.html', context)


# ============================================
# CRUD DE SUCURSALES
# ============================================

@login_required
@requiere_empresa
def sucursal_list(request):
	"""Lista de sucursales de la empresa activa"""
	empresa = request.empresa
	sucursales = empresa.sucursales.all().order_by('-es_principal', 'nombre')
	
	context = {
		'sucursales': sucursales,
		'empresa': empresa,
		'titulo': 'Sucursales',
	}
	return render(request, 'empresas/sucursal_list.html', context)


@login_required
@requiere_empresa
def sucursal_create(request):
	"""Crear nueva sucursal"""
	empresa = request.empresa
	
	if request.method == 'POST':
		form = SucursalForm(request.POST)
		if form.is_valid():
			sucursal = form.save(commit=False)
			sucursal.empresa = empresa
			
			# Si es la primera sucursal, marcarla como principal
			if not empresa.sucursales.exists():
				sucursal.es_principal = True
			
			# Si se marca como principal, desmarcar las demás
			if sucursal.es_principal:
				empresa.sucursales.filter(es_principal=True).update(es_principal=False)
			
			sucursal.save()
			messages.success(request, f'Sucursal "{sucursal.nombre}" creada correctamente.')
			return redirect('empresas:sucursal_list')
	else:
		form = SucursalForm()
	
	context = {
		'form': form,
		'empresa': empresa,
		'titulo': 'Nueva Sucursal',
		'accion': 'Crear',
	}
	return render(request, 'empresas/sucursal_form.html', context)


@login_required
@requiere_empresa
def sucursal_update(request, pk):
	"""Editar sucursal existente"""
	empresa = request.empresa
	sucursal = get_object_or_404(Sucursal, pk=pk, empresa=empresa)
	
	if request.method == 'POST':
		form = SucursalForm(request.POST, instance=sucursal)
		if form.is_valid():
			sucursal = form.save(commit=False)
			
			# Si se marca como principal, desmarcar las demás
			if sucursal.es_principal:
				empresa.sucursales.exclude(pk=sucursal.pk).update(es_principal=False)
			
			sucursal.save()
			messages.success(request, f'Sucursal "{sucursal.nombre}" actualizada correctamente.')
			return redirect('empresas:sucursal_list')
	else:
		form = SucursalForm(instance=sucursal)
	
	context = {
		'form': form,
		'sucursal': sucursal,
		'empresa': empresa,
		'titulo': f'Editar Sucursal: {sucursal.nombre}',
		'accion': 'Actualizar',
	}
	return render(request, 'empresas/sucursal_form.html', context)


@login_required
@requiere_empresa
def sucursal_delete(request, pk):
	"""Eliminar sucursal"""
	empresa = request.empresa
	sucursal = get_object_or_404(Sucursal, pk=pk, empresa=empresa)
	
	# No permitir eliminar la sucursal principal
	if sucursal.es_principal:
		messages.error(request, 'No se puede eliminar la sucursal principal.')
		return redirect('empresas:sucursal_list')
	
	if request.method == 'POST':
		nombre = sucursal.nombre
		sucursal.delete()
		messages.success(request, f'Sucursal "{nombre}" eliminada correctamente.')
		return redirect('empresas:sucursal_list')
	
	context = {
		'sucursal': sucursal,
		'empresa': empresa,
		'titulo': 'Eliminar Sucursal',
	}
	return render(request, 'empresas/sucursal_confirm_delete.html', context)


@login_required
@requiere_empresa
def sucursal_detail(request, pk):
	"""Ver detalle de sucursal"""
	empresa = request.empresa
	sucursal = get_object_or_404(Sucursal, pk=pk, empresa=empresa)
	
	context = {
		'sucursal': sucursal,
		'empresa': empresa,
		'titulo': f'Sucursal: {sucursal.nombre}',
	}
	return render(request, 'empresas/sucursal_detail.html', context)


@login_required
@requiere_empresa
def configurar_impresoras(request):
	"""Configurar tipos de impresora para cada tipo de documento"""
	import logging
	logger = logging.getLogger(__name__)
	
	try:
		empresa = request.empresa
		if not empresa:
			messages.error(request, '❌ No hay empresa asignada. Por favor, seleccione una empresa primero.')
			if request.user.is_superuser:
				return redirect('empresas:empresa_create')
			else:
				return redirect('logout')
	except Exception as e:
		logger.exception(f"Error al obtener empresa en configurar_impresoras: {e}")
		messages.error(request, f'❌ Error al acceder a la configuración de impresoras: {str(e)}')
		return redirect('dashboard')
	
	if request.method == 'POST':
		# Actualizar configuración de impresoras (tipos)
		empresa.impresora_factura = request.POST.get('impresora_factura', 'laser')
		empresa.impresora_boleta = request.POST.get('impresora_boleta', 'laser')
		empresa.impresora_guia = request.POST.get('impresora_guia', 'laser')
		empresa.impresora_nota_credito = request.POST.get('impresora_nota_credito', 'laser')
		empresa.impresora_nota_debito = request.POST.get('impresora_nota_debito', 'laser')
		empresa.impresora_vale = request.POST.get('impresora_vale', 'termica')
		empresa.impresora_cotizacion = request.POST.get('impresora_cotizacion', 'laser')
		
		# Actualizar nombres físicos de impresoras
		empresa.impresora_factura_nombre = request.POST.get('impresora_factura_nombre', '')
		empresa.impresora_boleta_nombre = request.POST.get('impresora_boleta_nombre', '')
		empresa.impresora_guia_nombre = request.POST.get('impresora_guia_nombre', '')
		empresa.impresora_nota_credito_nombre = request.POST.get('impresora_nota_credito_nombre', '')
		empresa.impresora_nota_debito_nombre = request.POST.get('impresora_nota_debito_nombre', '')
		empresa.impresora_vale_nombre = request.POST.get('impresora_vale_nombre', '')
		empresa.impresora_cotizacion_nombre = request.POST.get('impresora_cotizacion_nombre', '')
		
		empresa.save()
		
		messages.success(request, 'Configuración de impresoras guardada correctamente.')
		# Redirigir a la página de editar empresa
		return redirect('empresas:empresa_update', pk=empresa.id)
	
	# Agrupar documentos para mejor presentación
	documentos_electronicos = [
		{
			'nombre': 'Factura Electrónica',
			'campo': 'impresora_factura',
			'valor': empresa.impresora_factura,
			'icon': 'fas fa-file-invoice',
			'descripcion': 'Formato A4 con timbre electrónico'
		},
		{
			'nombre': 'Boleta Electrónica',
			'campo': 'impresora_boleta',
			'valor': empresa.impresora_boleta,
			'icon': 'fas fa-receipt',
			'descripcion': 'Boletas con timbre PDF417'
		},
		{
			'nombre': 'Guía de Despacho Electrónica',
			'campo': 'impresora_guia',
			'valor': empresa.impresora_guia,
			'icon': 'fas fa-truck',
			'descripcion': 'Documentos de traslado de mercadería'
		},
		{
			'nombre': 'Nota de Crédito Electrónica',
			'campo': 'impresora_nota_credito',
			'valor': empresa.impresora_nota_credito,
			'icon': 'fas fa-file-alt',
			'descripcion': 'Anulaciones y devoluciones'
		},
		{
			'nombre': 'Nota de Débito Electrónica',
			'campo': 'impresora_nota_debito',
			'valor': empresa.impresora_nota_debito,
			'icon': 'fas fa-file-alt',
			'descripcion': 'Cargos adicionales'
		},
	]
	
	documentos_internos = [
		{
			'nombre': 'Vale / Ticket de Venta',
			'campo': 'impresora_vale',
			'valor': empresa.impresora_vale,
			'icon': 'fas fa-ticket-alt',
			'descripcion': 'Preventa y tickets de caja'
		},
		{
			'nombre': 'Cotización',
			'campo': 'impresora_cotizacion',
			'valor': empresa.impresora_cotizacion,
			'icon': 'fas fa-file-signature',
			'descripcion': 'Presupuestos y cotizaciones'
		},
	]
	
	context = {
		'empresa': empresa,
		'documentos_electronicos': documentos_electronicos,
		'documentos_internos': documentos_internos,
		'titulo': 'Configuración de Impresoras',
	}
	
	return render(request, 'empresas/configurar_impresoras.html', context)


@login_required
def obtener_impresoras_sistema(request):
	"""API para obtener las impresoras instaladas en el sistema Windows"""
	import subprocess
	import json
	from django.http import JsonResponse
	
	# Verificar que haya empresa asignada, pero devolver JSON en lugar de redirect
	try:
		empresa = getattr(request, 'empresa', None)
		if not empresa:
			return JsonResponse({
				'success': False,
				'error': 'No hay empresa asignada. Por favor, seleccione una empresa primero.',
				'redirect': True
			}, status=403)
	except Exception as e:
		return JsonResponse({
			'success': False,
			'error': f'Error al verificar empresa: {str(e)}',
			'redirect': True
		}, status=403)
	
	try:
		# Ejecutar comando PowerShell para listar impresoras
		comando = 'powershell -Command "Get-Printer | Select-Object -Property Name, DriverName, PortName | ConvertTo-Json"'
		resultado = subprocess.run(comando, capture_output=True, text=True, shell=True, timeout=10)
		
		if resultado.returncode == 0:
			# Parsear JSON de PowerShell
			if not resultado.stdout or resultado.stdout.strip() == '':
				return JsonResponse({
					'success': True,
					'impresoras': [],
					'total': 0,
					'mensaje': 'No se encontraron impresoras en el sistema'
				})
			
			try:
				impresoras_raw = json.loads(resultado.stdout)
			except json.JSONDecodeError:
				# Si falla el parseo, intentar limpiar la salida
				output_limpio = resultado.stdout.strip()
				if output_limpio.startswith('['):
					impresoras_raw = json.loads(output_limpio)
				else:
					impresoras_raw = []
			
			# Si es un solo objeto, convertirlo a lista
			if isinstance(impresoras_raw, dict):
				impresoras_raw = [impresoras_raw]
			elif not isinstance(impresoras_raw, list):
				impresoras_raw = []
			
			# Formatear datos
			impresoras = []
			for imp in impresoras_raw:
				if isinstance(imp, dict):
					impresoras.append({
						'nombre': imp.get('Name', ''),
						'driver': imp.get('DriverName', ''),
						'puerto': imp.get('PortName', '')
					})
			
			return JsonResponse({
				'success': True,
				'impresoras': impresoras,
				'total': len(impresoras)
			})
		else:
			return JsonResponse({
				'success': False,
				'error': 'No se pudo ejecutar el comando de PowerShell',
				'detalles': resultado.stderr[:200] if resultado.stderr else 'Sin detalles'
			}, status=500)
			
	except subprocess.TimeoutExpired:
		return JsonResponse({
			'success': False,
			'error': 'Timeout al ejecutar comando de PowerShell. El proceso tardó más de 10 segundos.'
		}, status=500)
	except json.JSONDecodeError as e:
		return JsonResponse({
			'success': False,
			'error': 'Error al parsear respuesta de PowerShell',
			'detalles': str(e)[:200]
		}, status=500)
	except Exception as e:
		import logging
		logger = logging.getLogger(__name__)
		logger.exception(f"Error inesperado al obtener impresoras: {e}")
		return JsonResponse({
			'success': False,
			'error': f'Error al obtener impresoras: {str(e)}'
		}, status=500)
