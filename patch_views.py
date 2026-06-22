import sys

def patch_views():
    filepath = 'ventas/views.py'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    idx = content.find("if tipo_venta in ['factura', 'boleta', 'guia']:")
    end_idx = content.find("context = {", idx)
    if idx == -1 or end_idx == -1:
        print("Could not find block")
        return

    old_block = content[idx:end_idx]
    new_block = old_block
    
    # Replace sequential numbers with original numbers + COT- prefix
    new_block = new_block.replace('numero_nueva_venta = f"{ultimo_numero + 1:06d}"', 'numero_nueva_venta = f"COT-{cotizacion.numero_venta}"')
    new_block = new_block.replace('numero_nueva_venta = f"V{cotizacion.numero_venta}"', 'numero_nueva_venta = f"COT-{cotizacion.numero_venta}"')
    
    # Replace the redirect at the end of block with new printing and redirect logic
    search_str = "messages.success(request, f'Cotización convertida en {tipo_venta} #{nueva_venta.numero_venta}')\n            return redirect('ventas:cotizacion_detail', pk=cotizacion.pk)"
    if search_str not in new_block:
        # try without encoding issue
        search_str = "messages.success(request, f'Cotizaci"
        idx_msg = new_block.find(search_str)
        if idx_msg != -1:
            idx_end = new_block.find("return redirect('ventas:cotizacion_detail', pk=cotizacion.pk)", idx_msg)
            if idx_end != -1:
                search_str = new_block[idx_msg:idx_end+62]
    
    replacement_str = """
            # Enviar a Cola de Impresión Local para ticket facturable
            from caja.models import ColaImpresion, AperturaCaja
            from caja.impresion_utils import generar_esc_pos_ticket
            try:
                contenido = generar_esc_pos_ticket(nueva_venta)
                caja_id = 1
                if nueva_venta.estacion_trabajo:
                    aps = AperturaCaja.objects.filter(caja__empresa=cotizacion.empresa, estado='abierta')
                    for ap in aps:
                        if ap.caja.estacion_trabajo == nueva_venta.estacion_trabajo:
                            caja_id = ap.caja.id
                            break
                elif hasattr(request.user, 'perfil') and request.user.perfil.estacion_trabajo:
                    aps = AperturaCaja.objects.filter(caja__empresa=cotizacion.empresa, estado='abierta')
                    for ap in aps:
                        if ap.caja.estacion_trabajo == request.user.perfil.estacion_trabajo:
                            caja_id = ap.caja.id
                            break
                ColaImpresion.objects.create(caja_id=caja_id, venta=nueva_venta, contenido_raw=contenido, estado='pendiente')
            except Exception as e:
                print(f"[COTIZACION] Error al encolar impresion: {e}")

            messages.success(request, f'Cotización enviada a caja exitosamente (Ticket #{nueva_venta.numero_venta} impreso)')
            if request.user.has_perm('caja.add_movimientocaja'):
                return redirect('caja:procesar_venta_buscar')
            else:
                return redirect('ventas:cotizacion_detail', pk=cotizacion.pk)
"""
    new_block = new_block.replace(search_str, replacement_str)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content[:idx] + new_block + content[end_idx:])
    
    print("Patched successfully")

patch_views()
