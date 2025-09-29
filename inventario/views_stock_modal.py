from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from .models import Stock
from .forms import StockModalForm
# from usuarios.decorators import requiere_empresa


@login_required
def stock_update_modal(request, pk):
    """Editar registro de stock en modal"""
    try:
        # Obtener el stock directamente
        stock = get_object_or_404(Stock, pk=pk)
        empresa = stock.empresa
        
        print(f"DEBUG - Stock ID: {pk}")
        print(f"DEBUG - Empresa: {empresa}")
        print(f"DEBUG - User: {request.user}")
    except Exception as e:
        print(f"ERROR: {e}")
        return HttpResponse(f"Error: {e}", status=500)
    
    if request.method == 'POST':
        form = StockModalForm(request.POST, instance=stock, empresa=empresa)
        if form.is_valid():
            stock = form.save(commit=False)
            stock.actualizado_por = request.user
            stock.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Stock de {stock.articulo.nombre} actualizado exitosamente.'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Error en el formulario.',
                'errors': form.errors
            })
    else:
        form = StockModalForm(instance=stock, empresa=empresa)
    
    context = {
        'form': form,
        'stock': stock,
        'titulo': f'Editar Stock: {stock.articulo.nombre}'
    }
    
    return HttpResponse(render_to_string('inventario/includes/stock_form_modal.html', context, request=request))
