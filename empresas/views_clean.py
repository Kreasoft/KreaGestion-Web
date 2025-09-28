"""
Vistas para el módulo de empresas
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import views as auth_views
from usuarios.decorators import requiere_empresa, solo_superusuario, filtrar_por_empresa
from .models import Empresa, Sucursal, ConfiguracionEmpresa
from .forms import EmpresaForm, SucursalForm, ConfiguracionEmpresaForm


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
def empresa_list(request):
	"""Lista todas las empresas - solo superusuario"""
	empresas = Empresa.objects.all()
	return render(request, 'empresas/empresa_list.html', {'empresas': empresas})


@solo_superusuario
def empresa_create(request):
	"""Crea una nueva empresa - solo superusuario"""
	if request.method == 'POST':
		form = EmpresaForm(request.POST, request.FILES)
		if form.is_valid():
			empresa = form.save(commit=False)
			empresa.creado_por = request.user
			empresa.save()
			
			# Crear configuración por defecto
			ConfiguracionEmpresa.objects.create(empresa=empresa)
			
			messages.success(request, 'Empresa creada exitosamente.')
			return redirect('empresas:empresa_detail', pk=empresa.pk)
	else:
		form = EmpresaForm()
	
	return render(request, 'empresas/empresa_form.html', {'form': form})


@solo_superusuario
def empresa_detail(request, pk):
	"""Muestra los detalles de una empresa - solo superusuario"""
	empresa = get_object_or_404(Empresa, pk=pk)
	return render(request, 'empresas/empresa_detail.html', {'empresa': empresa})


@solo_superusuario
def empresa_update(request, pk):
	"""Actualiza una empresa existente - solo superusuario"""
	empresa = get_object_or_404(Empresa, pk=pk)
	if request.method == 'POST':
		form = EmpresaForm(request.POST, request.FILES, instance=empresa)
		if form.is_valid():
			form.save()
			messages.success(request, 'Empresa actualizada exitosamente.')
			return redirect('empresas:empresa_detail', pk=pk)
	else:
		form = EmpresaForm(instance=empresa)
	
	return render(request, 'empresas/empresa_form.html', {'form': form, 'empresa': empresa})


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
	
	if request.method == 'POST':
		empresa_id = request.POST.get('empresa_id')
		if empresa_id:
			try:
				empresa = Empresa.objects.get(id=empresa_id)
				# Guardar la empresa seleccionada en la sesión
				request.session['empresa_activa_id'] = empresa.id
				messages.success(request, f'Empresa cambiada a: {empresa.nombre}')
				return redirect('dashboard')  # Redirigir al dashboard principal
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

	if request.method == 'POST':
		form = EmpresaForm(request.POST, request.FILES, instance=empresa_activa)
		
		if form.is_valid():
			empresa_guardada = form.save()
			messages.success(request, f'Empresa "{empresa_activa.nombre}" actualizada correctamente.')
			return redirect('dashboard')
		else:
			messages.error(request, 'Hubo errores en el formulario.')
	else:
		form = EmpresaForm(instance=empresa_activa)

	context = {
		'form': form,
		'empresa': empresa_activa,
		'titulo': f'Editar Empresa: {empresa_activa.nombre}',
	}

	return render(request, 'empresas/editar_empresa_activa.html', context)
