from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum
from django.forms import inlineformset_factory
from .models import Cliente, ContactoCliente
from .forms import ClienteForm, ContactoClienteForm, ContactoClienteInlineFormSet
from empresas.models import Empresa
from empresas.decorators import requiere_empresa


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
def cliente_list(request):
    """Lista de clientes con estadísticas"""
    # Obtener la empresa del usuario
    empresa, error = obtener_empresa_usuario(request)
    if error:
        messages.error(request, error)
        return redirect('dashboard')
    
    # Filtros
    search = request.GET.get('search', '')
    estado = request.GET.get('estado', '')
    tipo_cliente = request.GET.get('tipo_cliente', '')
    
    # Query base
    clientes = Cliente.objects.filter(empresa=empresa)
    
    # Aplicar filtros
    if search:
        clientes = clientes.filter(
            Q(nombre__icontains=search) |
            Q(codigo__icontains=search) |
            Q(rut__icontains=search) |
            Q(email__icontains=search)
        )
    
    if estado:
        clientes = clientes.filter(estado=estado)
    
    if tipo_cliente:
        clientes = clientes.filter(tipo_cliente=tipo_cliente)
    
    # Ordenamiento
    clientes = clientes.order_by('nombre')
    
    # Paginación
    paginator = Paginator(clientes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Estadísticas
    total_clientes = Cliente.objects.filter(empresa=empresa).count()
    clientes_activos = Cliente.objects.filter(empresa=empresa, estado='activo').count()
    clientes_contribuyentes = Cliente.objects.filter(empresa=empresa, tipo_cliente='contribuyente').count()
    clientes_consumidor_final = Cliente.objects.filter(empresa=empresa, tipo_cliente='consumidor_final').count()
    
    # Calcular límite de crédito total
    limite_total = Cliente.objects.filter(empresa=empresa).aggregate(
        total=Sum('limite_credito')
    )['total'] or 0
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'estado': estado,
        'tipo_cliente': tipo_cliente,
        'total_clientes': total_clientes,
        'clientes_activos': clientes_activos,
        'clientes_contribuyentes': clientes_contribuyentes,
        'clientes_consumidor_final': clientes_consumidor_final,
        'limite_total': limite_total,
        'estados': Cliente.ESTADO_CHOICES,
        'tipos_cliente': Cliente.TIPO_CLIENTE_CHOICES,
    }
    
    return render(request, 'clientes/cliente_list.html', context)


@login_required
def cliente_detail(request, pk):
    """Detalle de cliente"""
    # Obtener la empresa del usuario
    empresa, error = obtener_empresa_usuario(request)
    if error:
        messages.error(request, error)
        return redirect('clientes:cliente_list')
    
    cliente = get_object_or_404(Cliente, pk=pk, empresa=empresa)
    
    # Obtener contactos
    contactos = cliente.contactos.all().order_by('-es_contacto_principal', 'tipo_contacto', 'nombre')
    
    # Obtener movimientos de cuenta corriente (últimos 10)
    movimientos = cliente.movimientos_cuenta.all()[:10]
    
    context = {
        'cliente': cliente,
        'contactos': contactos,
        'movimientos': movimientos,
    }
    
    return render(request, 'clientes/cliente_detail.html', context)


@login_required
def cliente_create(request):
    """Crear nuevo cliente"""
    # Obtener la empresa del usuario
    if request.user.is_superuser:
        # Para superusuarios, usar la primera empresa disponible
        empresa = Empresa.objects.first()
        if not empresa:
            messages.error(request, 'No hay empresas configuradas en el sistema.')
            return redirect('clientes:cliente_list')
    else:
        # Para usuarios normales, usar su empresa asociada
        try:
            empresa = request.user.perfil.empresa
        except:
            messages.error(request, 'Usuario no tiene empresa asociada.')
            return redirect('clientes:cliente_list')
    
    ContactoFormSet = inlineformset_factory(
        Cliente, ContactoCliente, 
        form=ContactoClienteForm,
        formset=ContactoClienteInlineFormSet,
        extra=1,
        can_delete=True,
        fields=['nombre', 'cargo', 'tipo_contacto', 'telefono', 'celular', 'email', 'observaciones', 'es_contacto_principal']
    )
    
    if request.method == 'POST':
        form = ClienteForm(request.POST, empresa=empresa)
        formset = ContactoFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            cliente = form.save(commit=False)
            cliente.empresa = empresa
            cliente.creado_por = request.user
            cliente.save()
            
            # Guardar contactos
            formset.instance = cliente
            formset.save()
            
            messages.success(request, f'Cliente "{cliente.nombre}" creado exitosamente.')
            return redirect('clientes:cliente_detail', pk=cliente.pk)
    else:
        form = ClienteForm(empresa=empresa)
        formset = ContactoFormSet()
    
    context = {
        'form': form,
        'formset': formset,
        'title': 'Crear Cliente',
        'submit_text': 'Crear Cliente',
    }
    
    return render(request, 'clientes/cliente_form.html', context)


@login_required
def cliente_update(request, pk):
    """Editar cliente"""
    # Obtener la empresa del usuario
    empresa, error = obtener_empresa_usuario(request)
    if error:
        messages.error(request, error)
        return redirect('clientes:cliente_list')
    
    cliente = get_object_or_404(Cliente, pk=pk, empresa=empresa)
    
    ContactoFormSet = inlineformset_factory(
        Cliente, ContactoCliente, 
        form=ContactoClienteForm,
        formset=ContactoClienteInlineFormSet,
        extra=1,
        can_delete=True,
        fields=['nombre', 'cargo', 'tipo_contacto', 'telefono', 'celular', 'email', 'observaciones', 'es_contacto_principal']
    )
    
    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente, empresa=empresa)
        formset = ContactoFormSet(request.POST, instance=cliente)
        
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            
            messages.success(request, f'Cliente "{cliente.nombre}" actualizado exitosamente.')
            return redirect('clientes:cliente_detail', pk=cliente.pk)
    else:
        form = ClienteForm(instance=cliente, empresa=empresa)
        formset = ContactoFormSet(instance=cliente)
    
    # Obtener contactos para mostrar en la lista
    contactos = cliente.contactos.all().order_by('-es_contacto_principal', 'tipo_contacto', 'nombre')
    
    context = {
        'form': form,
        'formset': formset,
        'contactos': contactos,
        'cliente': cliente,
        'title': 'Editar Cliente',
        'submit_text': 'Actualizar Cliente',
    }
    
    return render(request, 'clientes/cliente_form.html', context)


@login_required
def cliente_delete(request, pk):
    """Eliminar cliente"""
    # Obtener la empresa del usuario
    empresa, error = obtener_empresa_usuario(request)
    if error:
        messages.error(request, error)
        return redirect('clientes:cliente_list')
    
    cliente = get_object_or_404(Cliente, pk=pk, empresa=empresa)
    
    if request.method == 'POST':
        nombre = cliente.nombre
        cliente.delete()
        messages.success(request, f'Cliente "{nombre}" eliminado exitosamente.')
        return redirect('clientes:cliente_list')
    
    context = {
        'cliente': cliente,
    }
    
    return render(request, 'clientes/cliente_confirm_delete.html', context)


@login_required
def contacto_create(request, cliente_id):
    """Crear contacto en modal"""
    cliente = get_object_or_404(Cliente, id=cliente_id)
    
    if request.method == 'POST':
        form = ContactoClienteForm(request.POST)
        if form.is_valid():
            contacto = form.save(commit=False)
            contacto.cliente = cliente
            contacto.save()
            messages.success(request, 'Contacto agregado exitosamente.')
            return redirect('clientes:cliente_detail', pk=cliente.id)
    else:
        form = ContactoClienteForm()
    
    context = {
        'form': form,
        'cliente': cliente,
    }
    
    return render(request, 'clientes/contacto_form_modal.html', context)


@login_required
def contacto_update(request, cliente_id, contacto_id):
    """Editar contacto en modal"""
    cliente = get_object_or_404(Cliente, id=cliente_id)
    contacto = get_object_or_404(ContactoCliente, id=contacto_id, cliente=cliente)
    
    if request.method == 'POST':
        form = ContactoClienteForm(request.POST, instance=contacto)
        if form.is_valid():
            form.save()
            messages.success(request, 'Contacto actualizado exitosamente.')
            return redirect('clientes:cliente_detail', pk=cliente.id)
    else:
        form = ContactoClienteForm(instance=contacto)
    
    context = {
        'form': form,
        'cliente': cliente,
        'contacto': contacto,
    }
    
    return render(request, 'clientes/contacto_form_modal.html', context)


@login_required
def contacto_delete(request, cliente_id, contacto_id):
    """Eliminar contacto"""
    cliente = get_object_or_404(Cliente, id=cliente_id)
    contacto = get_object_or_404(ContactoCliente, id=contacto_id, cliente=cliente)
    
    if request.method == 'POST':
        nombre = contacto.nombre
        contacto.delete()
        messages.success(request, f'Contacto "{nombre}" eliminado exitosamente.')
        return redirect('clientes:cliente_detail', pk=cliente.id)
    
    context = {
        'cliente': cliente,
        'contacto': contacto,
    }
    
    return render(request, 'clientes/contacto_confirm_delete.html', context)