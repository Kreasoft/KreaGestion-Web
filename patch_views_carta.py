import sys

def patch_views_carta():
    filepath = 'ventas/views.py'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # We need to replace the ColaImpresion logic in cotizacion_convertir_venta
    old_block = """                # Enviar a Cola de Impresión Local para que imprima físicamente un ticket facturable
                from caja.models import ColaImpresion, AperturaCaja
                from caja.impresion_utils import generar_esc_pos_ticket
                
                try:
                    contenido = generar_esc_pos_ticket(nueva_venta)
                    
                    # Buscar caja activa para la estación del usuario o de la venta
                    caja_id = 1
                    if nueva_venta.estacion_trabajo:
                        aps = AperturaCaja.objects.filter(caja__empresa=cotizacion.empresa, estado='abierta')
                        for ap in aps:
                            if ap.caja.estacion_trabajo == nueva_venta.estacion_trabajo:
                                caja_id = ap.caja.id
                                break
                    elif request.user.perfil.estacion_trabajo:
                        aps = AperturaCaja.objects.filter(caja__empresa=cotizacion.empresa, estado='abierta')
                        for ap in aps:
                            if ap.caja.estacion_trabajo == request.user.perfil.estacion_trabajo:
                                caja_id = ap.caja.id
                                break
                                
                    ColaImpresion.objects.create(
                        caja_id=caja_id,
                        venta=nueva_venta,
                        contenido_raw=contenido,
                        estado='pendiente'
                    )
                    print(f"[COTIZACION] Impresión encolada para ticket {nueva_venta.id}")
                except Exception as e_print:
                    print(f"[COTIZACION] Error al encolar impresión: {e_print}")
                
                messages.success(request, f'Cotización enviada a caja exitosamente (Ticket #{nueva_venta.numero_venta} impreso)')
                
                # Redirigir a procesar venta si tiene permiso
                if request.user.has_perm('caja.add_movimientocaja'):
                    return redirect('caja:procesar_venta_buscar')
                else:
                    return redirect('ventas:cotizacion_detail', pk=cotizacion.pk)"""

    new_block = """                formato = nueva_venta.estacion_trabajo.formato_impresion if nueva_venta.estacion_trabajo else '80mm'
                if formato == 'carta':
                    messages.success(request, f'Cotización convertida a {tipo_venta}. Abriendo documento...')
                    return redirect('ventas:venta_imprimir_y_volver', pk=nueva_venta.id)
                else:
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
                        elif request.user.perfil.estacion_trabajo:
                            aps = AperturaCaja.objects.filter(caja__empresa=cotizacion.empresa, estado='abierta')
                            for ap in aps:
                                if ap.caja.estacion_trabajo == request.user.perfil.estacion_trabajo:
                                    caja_id = ap.caja.id
                                    break
                                    
                        ColaImpresion.objects.create(caja_id=caja_id, venta=nueva_venta, contenido_raw=contenido, estado='pendiente')
                        print(f"[COTIZACION] Impresión encolada para ticket {nueva_venta.id}")
                    except Exception as e_print:
                        print(f"[COTIZACION] Error al encolar impresión: {e_print}")
                    
                    messages.success(request, f'Cotización enviada a caja exitosamente (Ticket #{nueva_venta.numero_venta} impreso)')
                    if request.user.has_perm('caja.add_movimientocaja'):
                        return redirect('caja:procesar_venta_buscar')
                    else:
                        return redirect('ventas:cotizacion_detail', pk=cotizacion.pk)"""

    # Because replace can be tricky with formatting, I will use a search substring.
    if old_block in content:
        content = content.replace(old_block, new_block)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print("Patched views.py (Carta)")
    else:
        # Fallback to searching without leading spaces
        search_str = "from caja.models import ColaImpresion, AperturaCaja"
        idx = content.find(search_str)
        if idx != -1:
            idx_start = content.rfind("# Enviar a Cola", 0, idx)
            if idx_start == -1: idx_start = content.rfind("from caja.models", 0, idx)
            idx_end = content.find("return redirect('ventas:cotizacion_detail', pk=cotizacion.pk)", idx)
            if idx_end != -1:
                idx_end += len("return redirect('ventas:cotizacion_detail', pk=cotizacion.pk)")
                old_dyn = content[idx_start:idx_end]
                content = content.replace(old_dyn, new_block)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                print("Patched views.py (Carta) using dynamic search")
            else:
                print("Could not find end of block")
        else:
            print("Could not find block")

patch_views_carta()
