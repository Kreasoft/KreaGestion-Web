import re

with open('ventas/views_pos_procesar.py', 'r', encoding='utf-8') as f:
    content = f.read()

# We need to replace the body of procesar_venta_pos
# The function ends with return redirect(vale_url)

old_body = r"""    # Redirigir a impresión de vale
    from urllib.parse import quote
    pos_url = reverse('ventas:pos_view')
    vale_url = reverse('ventas:vale_html', args=\[ticket.pk\])
    # Codificar return_url para que se pase correctamente
    vale_url \+= f"\?auto=1&autoclose=1&autoclose_delay=2000&return_url=\{quote\(pos_url, safe=''\)\}"
    
    print\(f"\[POS VALE\] Vale generado - Redirigiendo a impresión: \{vale_url\}"\)
    return redirect\(vale_url\)"""

new_body = """    # Enviar a Cola de Impresión Local
    from caja.models import ColaImpresion
    from caja.impresion_utils import generar_esc_pos_ticket
    
    try:
        contenido = generar_esc_pos_ticket(ticket)
        ColaImpresion.objects.create(
            empresa=empresa,
            tipo_documento='vale',
            documento_id=ticket.id,
            contenido_esc_pos=contenido,
            estado='pendiente'
        )
        print(f"[POS VALE] Impresión encolada para ticket {ticket.id}")
        messages.success(request, f"Vale #{ticket.numero_venta} generado e impreso con éxito.")
    except Exception as e:
        print(f"[POS VALE] Error al encolar impresión: {e}")
        messages.error(request, f"El vale se generó pero hubo un error al imprimir: {e}")
        
    return redirect('ventas:pos_view')"""

content = re.sub(old_body, new_body, content)

with open('ventas/views_pos_procesar.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done replacing redirect with local print in views_pos_procesar")
