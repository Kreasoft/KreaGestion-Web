from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from core.decorators import requiere_empresa
import pymysql
import json

from .forms import ConexionMySQLForm, SeleccionTablaForm
from clientes.models import Cliente
from proveedores.models import Proveedor
from articulos.models import Articulo, CategoriaArticulo, UnidadMedida

# Importar funciones de mantenimiento
from .mantenimiento_utils import (
    optimizar_tablas, crear_backup, restaurar_backup, puede_gestionar_respaldos, verificar_integridad,
    limpiar_sesiones, detectar_duplicados, limpiar_archivos,
    ver_logs, exportar_logs, purgar_logs
)


@login_required
@requiere_empresa
def utilidades_dashboard(request):
    """Dashboard de utilidades"""
    context = {
        'title': 'Utilidades del Sistema',
    }
    return render(request, 'utilidades/dashboard.html', context)


@login_required
@requiere_empresa
def exportar_datos_view(request):
    """Vista para exportar datos"""
    context = {
        'title': 'Exportar Datos',
    }
    return render(request, 'utilidades/exportar_datos.html', context)


@login_required
@requiere_empresa
def mantenimiento_view(request):
    """Vista principal de mantenimiento"""
    context = {
        'title': 'Mantenimiento del Sistema',
        'puede_gestionar_respaldos': puede_gestionar_respaldos(request.user),
    }
    return render(request, 'utilidades/mantenimiento.html', context)


@login_required
@requiere_empresa
def importar_datos(request):
    """Vista principal de importación"""
    form_conexion = ConexionMySQLForm()
    form_seleccion = SeleccionTablaForm()
    
    context = {
        'title': 'Importar Datos desde MySQL',
        'form_conexion': form_conexion,
        'form_seleccion': form_seleccion,
    }
    return render(request, 'utilidades/importar_datos.html', context)


@login_required
@requiere_empresa
def conectar_mysql(request):
    """Conectar a MySQL y obtener tablas"""
    if request.method == 'POST':
        form = ConexionMySQLForm(request.POST)
        
        if form.is_valid():
            try:
                # Intentar conexión
                connection = pymysql.connect(
                    host=form.cleaned_data['host'],
                    port=form.cleaned_data['puerto'],
                    user=form.cleaned_data['usuario'],
                    password=form.cleaned_data['contrasena'],
                    database=form.cleaned_data['base_datos'],
                    charset='utf8',
                    cursorclass=pymysql.cursors.DictCursor
                )
                
                # Obtener lista de tablas
                with connection.cursor() as cursor:
                    cursor.execute("SHOW TABLES")
                    tablas = [list(row.values())[0] for row in cursor.fetchall()]
                
                connection.close()
                
                # Guardar datos de conexión en sesión
                request.session['mysql_connection'] = {
                    'host': form.cleaned_data['host'],
                    'puerto': form.cleaned_data['puerto'],
                    'base_datos': form.cleaned_data['base_datos'],
                    'usuario': form.cleaned_data['usuario'],
                    'contrasena': form.cleaned_data['contrasena'],
                }
                
                return JsonResponse({
                    'success': True,
                    'message': 'Conexión exitosa',
                    'tablas': tablas
                })
                
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': f'Error de conexión: {str(e)}'
                })
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'})


@login_required
@requiere_empresa
def mapear_campos(request):
    """Obtener campos de una tabla y mapearlos"""
    if request.method == 'POST':
        tabla = request.POST.get('tabla')
        tipo_importacion = request.POST.get('tipo_importacion')
        
        # Obtener conexión de sesión
        conn_data = request.session.get('mysql_connection')
        if not conn_data:
            return JsonResponse({'success': False, 'message': 'No hay conexión activa'})
        
        try:
            connection = pymysql.connect(
                host=conn_data['host'],
                port=conn_data['puerto'],
                user=conn_data['usuario'],
                password=conn_data['contrasena'],
                database=conn_data['base_datos'],
                charset='utf8',
                cursorclass=pymysql.cursors.DictCursor
            )
            
            # Obtener estructura de la tabla
            with connection.cursor() as cursor:
                cursor.execute(f"DESCRIBE `{tabla}`")
                campos_origen = [row['Field'] for row in cursor.fetchall()]
                
                # Obtener una muestra de datos
                cursor.execute(f"SELECT * FROM `{tabla}` LIMIT 5")
                muestra_datos = cursor.fetchall()
            
            connection.close()
            
            # Definir campos destino según tipo
            campos_destino = get_campos_destino(tipo_importacion)
            
            # DEBUG: Imprimir campos destino
            print(f"\n=== MAPEAR CAMPOS DEBUG ===")
            print(f"Tipo importación: {tipo_importacion}")
            print(f"Campos destino: {campos_destino}")
            print(f"Total campos: {len(campos_destino)}")
            print("===========================\n")
            
            return JsonResponse({
                'success': True,
                'campos_origen': campos_origen,
                'campos_destino': campos_destino,
                'muestra_datos': muestra_datos
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'})


def get_campos_destino(tipo_importacion):
    """Obtener campos destino según el tipo de importación"""
    campos = {
        'clientes': [
            {'campo': 'rut', 'nombre': 'RUT', 'requerido': True},
            {'campo': 'nombre', 'nombre': 'Nombre', 'requerido': True},
            {'campo': 'giro', 'nombre': 'Giro', 'requerido': False},
            {'campo': 'direccion', 'nombre': 'Dirección', 'requerido': False},
            {'campo': 'comuna', 'nombre': 'Comuna', 'requerido': False},
            {'campo': 'ciudad', 'nombre': 'Ciudad', 'requerido': False},
            {'campo': 'region', 'nombre': 'Región', 'requerido': False},
            {'campo': 'telefono', 'nombre': 'Teléfono', 'requerido': False},
            {'campo': 'email', 'nombre': 'Email', 'requerido': False},
        ],
        'proveedores': [
            {'campo': 'rut', 'nombre': 'RUT', 'requerido': True},
            {'campo': 'nombre', 'nombre': 'Nombre', 'requerido': True},
            {'campo': 'giro', 'nombre': 'Giro', 'requerido': False},
            {'campo': 'direccion', 'nombre': 'Dirección', 'requerido': False},
            {'campo': 'comuna', 'nombre': 'Comuna', 'requerido': False},
            {'campo': 'ciudad', 'nombre': 'Ciudad', 'requerido': False},
            {'campo': 'telefono', 'nombre': 'Teléfono', 'requerido': False},
            {'campo': 'email', 'nombre': 'Email', 'requerido': False},
        ],
        'familias': [
            {'campo': 'codigo', 'nombre': '🔑 Código de Familia (será el nuevo código de categoría)', 'requerido': True},
            {'campo': 'nombre', 'nombre': '📝 Nombre de la Familia', 'requerido': False},
            {'campo': 'descripcion', 'nombre': '📄 Descripción', 'requerido': False},
        ],
        'articulos': [
            {'campo': 'codigo', 'nombre': 'Código', 'requerido': True},
            {'campo': 'nombre', 'nombre': 'Nombre', 'requerido': True},
            {'campo': 'descripcion', 'nombre': 'Descripción', 'requerido': False},
            {'campo': 'categoria_codigo', 'nombre': 'Código Familia/Categoría', 'requerido': False},
            {'campo': 'precio_costo', 'nombre': 'Precio Costo', 'requerido': False},
            {'campo': 'precio_final', 'nombre': 'Precio Final (con todos los impuestos)', 'requerido': False},
            {'campo': 'codigo_barras', 'nombre': 'Código de Barras', 'requerido': False},
        ],
        'ventas': [
            {'campo': 'numero_venta', 'nombre': 'N° Venta / Folio', 'requerido': True},
            {'campo': 'fecha', 'nombre': 'Fecha de Emisión (YYYY-MM-DD)', 'requerido': False},
            {'campo': 'tipo_documento', 'nombre': 'Tipo Documento (factura, boleta, guia, vale, ticket)', 'requerido': False},
            {'campo': 'cliente_rut', 'nombre': 'RUT Cliente', 'requerido': False},
            {'campo': 'cliente_nombre', 'nombre': 'Nombre Cliente', 'requerido': False},
            {'campo': 'subtotal', 'nombre': 'Subtotal / Neto', 'requerido': False},
            {'campo': 'descuento', 'nombre': 'Descuento', 'requerido': False},
            {'campo': 'iva', 'nombre': 'IVA', 'requerido': False},
            {'campo': 'total', 'nombre': 'Total Venta', 'requerido': True},
            {'campo': 'forma_pago', 'nombre': 'Forma de Pago', 'requerido': False},
            {'campo': 'estado', 'nombre': 'Estado (confirmada, anulada, borrador)', 'requerido': False},
            {'campo': 'observaciones', 'nombre': 'Observaciones / Detalle', 'requerido': False},
        ],
    }
    
    return campos.get(tipo_importacion, [])


@login_required
@requiere_empresa
@transaction.atomic
def ejecutar_importacion(request):
    """Ejecutar la importación de datos"""
    if request.method == 'POST':
        try:
            tipo_importacion = request.POST.get('tipo_importacion')
            tabla = request.POST.get('tabla')
            mapeo = json.loads(request.POST.get('mapeo', '{}'))
            
            # Obtener conexión
            conn_data = request.session.get('mysql_connection')
            if not conn_data:
                return JsonResponse({'success': False, 'message': 'No hay conexión activa'})
            
            connection = pymysql.connect(
                host=conn_data['host'],
                port=conn_data['puerto'],
                user=conn_data['usuario'],
                password=conn_data['contrasena'],
                database=conn_data['base_datos'],
                charset='utf8',
                cursorclass=pymysql.cursors.DictCursor
            )
            
            # Obtener datos
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT * FROM `{tabla}`")
                datos = cursor.fetchall()
            
            connection.close()
            
            # Importar según tipo
            if tipo_importacion == 'clientes':
                resultado = importar_clientes(datos, mapeo, request.empresa)
            elif tipo_importacion == 'proveedores':
                resultado = importar_proveedores(datos, mapeo, request.empresa)
            elif tipo_importacion == 'familias':
                resultado = importar_familias(datos, mapeo, request.empresa)
            elif tipo_importacion == 'articulos':
                resultado = importar_articulos(datos, mapeo, request.empresa)
            elif tipo_importacion == 'ventas':
                resultado = importar_ventas(datos, mapeo, request.empresa)
            else:
                return JsonResponse({'success': False, 'message': 'Tipo de importación no válido'})
            
            return JsonResponse(resultado)
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'})


def importar_clientes(datos, mapeo, empresa):
    """Importar clientes (filtrando por ES_CLI = 'S')"""
    importados = 0
    errores = []
    omitidos = 0
    
    for fila in datos:
        try:
            # Verificar si tiene el campo ES_CLI y si es 'S'
            es_cliente = fila.get('ES_CLI', '').upper() == 'S'
            
            if not es_cliente:
                omitidos += 1
                continue
            
            # Mapear datos
            datos_cliente = {}
            for campo_destino, campo_origen in mapeo.items():
                if campo_origen and campo_origen in fila:
                    valor = fila[campo_origen]
                    # Convertir None a string vacío
                    datos_cliente[campo_destino] = str(valor) if valor is not None else ''
            
            # Validar campos requeridos
            if not datos_cliente.get('rut') or not datos_cliente.get('nombre'):
                errores.append(f"Fila sin RUT o nombre: {fila.get('rut', 'N/A')}")
                continue
            
            # Crear o actualizar cliente
            cliente, created = Cliente.objects.update_or_create(
                rut=datos_cliente['rut'],
                empresa=empresa,
                defaults={
                    'nombre': datos_cliente.get('nombre', ''),
                    'giro': datos_cliente.get('giro', ''),
                    'direccion': datos_cliente.get('direccion', ''),
                    'comuna': datos_cliente.get('comuna', ''),
                    'ciudad': datos_cliente.get('ciudad', ''),
                    'region': datos_cliente.get('region', ''),
                    'telefono': datos_cliente.get('telefono', ''),
                    'email': datos_cliente.get('email', ''),
                }
            )
            
            importados += 1
            
        except Exception as e:
            errores.append(f"Error en fila RUT {fila.get('rut', 'N/A')}: {str(e)}")
    
    return {
        'success': True,
        'importados': importados,
        'omitidos': omitidos,
        'errores': errores,
        'total': len(datos)
    }


def importar_proveedores(datos, mapeo, empresa):
    """Importar proveedores (filtrando por ES_PRO = 'S')"""
    importados = 0
    errores = []
    omitidos = 0
    
    for fila in datos:
        try:
            # Verificar si tiene el campo ES_PRO y si es 'S'
            es_proveedor = fila.get('ES_PRO', '').upper() == 'S'
            
            if not es_proveedor:
                omitidos += 1
                continue
            
            datos_proveedor = {}
            for campo_destino, campo_origen in mapeo.items():
                if campo_origen and campo_origen in fila:
                    valor = fila[campo_origen]
                    # Convertir None a string vacío
                    datos_proveedor[campo_destino] = str(valor) if valor is not None else ''
            
            if not datos_proveedor.get('rut') or not datos_proveedor.get('nombre'):
                errores.append(f"Fila sin RUT o nombre: {fila.get('rut', 'N/A')}")
                continue
            
            proveedor, created = Proveedor.objects.update_or_create(
                rut=datos_proveedor['rut'],
                empresa=empresa,
                defaults={
                    'nombre': datos_proveedor.get('nombre', ''),
                    'giro': datos_proveedor.get('giro', ''),
                    'direccion': datos_proveedor.get('direccion', ''),
                    'comuna': datos_proveedor.get('comuna', ''),
                    'ciudad': datos_proveedor.get('ciudad', ''),
                    'telefono': datos_proveedor.get('telefono', ''),
                    'email': datos_proveedor.get('email', ''),
                }
            )
            
            importados += 1
            
        except Exception as e:
            errores.append(f"Error en fila RUT {fila.get('rut', 'N/A')}: {str(e)}")
    
    return {
        'success': True,
        'importados': importados,
        'omitidos': omitidos,
        'errores': errores,
        'total': len(datos)
    }


def importar_familias(datos, mapeo, empresa):
    """Importar categorías de artículos"""
    importados = 0
    errores = []
    omitidos = 0
    omitidos_duplicados = 0
    
    # Primero, extraer y deduplicar nombres del archivo
    nombres_unicos = {}  # {nombre_lower: datos_categoria}
    
    for fila in datos:
        datos_categoria = {}
        for campo_destino, campo_origen in mapeo.items():
            if campo_origen and campo_origen in fila:
                valor = fila[campo_origen]
                datos_categoria[campo_destino] = str(valor) if valor is not None else ''
        
        nombre = datos_categoria.get('nombre', '').strip()
        codigo = datos_categoria.get('codigo', '').strip()
        descripcion = datos_categoria.get('descripcion', '').strip()
        
        if not codigo and not nombre:
            omitidos += 1
            continue
            
        nombre_lower = nombre.lower() if nombre else f"cod_{codigo.lower()}"
        
        # Solo guardar la primera ocurrencia de cada nombre
        if nombre_lower not in nombres_unicos:
            nombres_unicos[nombre_lower] = {
                'codigo': codigo,
                'nombre': nombre,
                'descripcion': descripcion
            }
        else:
            omitidos_duplicados += 1
    
    # Cache de códigos ya usados en este lote
    codigos_usados = set()
    
    # Ahora procesar solo los nombres únicos
    for nombre_lower, datos_categoria in nombres_unicos.items():
        try:
            codigo = datos_categoria['codigo']
            nombre = datos_categoria['nombre']
            descripcion = datos_categoria['descripcion']
            
            # Buscar si ya existe una categoría con este nombre en la BD
            categoria_existente = CategoriaArticulo.objects.filter(
                empresa=empresa,
                nombre__iexact=nombre
            ).first()
            
            if categoria_existente:
                omitidos += 1
                continue
            
            # Si no hay código, generar uno único basado en el nombre
            if not codigo:
                # Generar código desde el nombre: primeras letras + número
                if len(nombre) >= 3:
                    base_codigo = nombre[:3].upper()
                else:
                    base_codigo = nombre.upper().ljust(3, 'X')
                
                # Generar código único
                contador = 1
                codigo_generado = f"{base_codigo}{contador:03d}"
                
                # Verificar tanto en BD como en los códigos ya usados en este lote
                while (codigo_generado in codigos_usados or 
                       CategoriaArticulo.objects.filter(empresa=empresa, codigo=codigo_generado).exists()):
                    contador += 1
                    codigo_generado = f"{base_codigo}{contador:03d}"
                
                codigo = codigo_generado
            
            # Si no hay nombre, usar el código como nombre
            if not nombre:
                nombre = f"Familia {codigo}"
            
            # Crear la categoría
            categoria = CategoriaArticulo.objects.create(
                codigo=codigo,
                empresa=empresa,
                nombre=nombre,
                descripcion=descripcion
            )
            
            codigos_usados.add(codigo)
            importados += 1
            
        except Exception as e:
            nombre_para_error = datos_categoria.get('nombre', datos_categoria.get('codigo', 'N/A'))
            errores.append(f"Error en fila {nombre_para_error}: {str(e)}")
    
    return {
        'success': True,
        'importados': importados,
        'omitidos': omitidos + omitidos_duplicados,
        'errores': errores,
        'total': len(datos)
    }


def importar_articulos(datos, mapeo, empresa):
    """Importar artículos"""
    importados = 0
    errores = []
    omitidos = 0
    
    # Obtener o crear unidad de medida por defecto
    unidad_medida, _ = UnidadMedida.objects.get_or_create(
        empresa=empresa,
        nombre='Unidad',
        defaults={'simbolo': 'UN'}
    )
    
    # Obtener o crear categoría por defecto
    categoria_default, _ = CategoriaArticulo.objects.get_or_create(
        empresa=empresa,
        codigo='000',
        defaults={
            'nombre': 'Sin Categoría',
            'descripcion': 'Categoría por defecto para artículos importados'
        }
    )
    
    for fila in datos:
        try:
            datos_articulo = {}
            for campo_destino, campo_origen in mapeo.items():
                if campo_origen and campo_origen in fila:
                    valor = fila[campo_origen]
                    datos_articulo[campo_destino] = str(valor) if valor is not None else ''
            
            codigo = datos_articulo.get('codigo', '').strip()
            nombre = datos_articulo.get('nombre', '').strip()
            
            # Validar campos requeridos
            if not codigo or not nombre:
                omitidos += 1
                continue
            
            # Buscar o crear categoría por código
            categoria = categoria_default
            categoria_codigo = datos_articulo.get('categoria_codigo', '').strip()
            
            if categoria_codigo:
                # Usar get_or_create directamente para evitar race conditions
                categoria, created = CategoriaArticulo.objects.get_or_create(
                    codigo=categoria_codigo,
                    empresa=empresa,
                    defaults={
                        'nombre': f'Familia {categoria_codigo}',
                        'descripcion': 'Categoría creada automáticamente durante la importación'
                    }
                )
            
            # Limpiar y validar precios
            precio_costo_raw = datos_articulo.get('precio_costo', '0.00')
            precio_final_raw = datos_articulo.get('precio_final', '0.00')
            
            try:
                precio_costo = float(precio_costo_raw)
            except (ValueError, TypeError):
                precio_costo = 0.0
            
            try:
                precio_final = float(precio_final_raw)
            except (ValueError, TypeError):
                precio_final = 0.0
            
            # CALCULAR precio_venta (neto sin IVA) desde precio_final (con IVA)
            # Fórmula: precio_venta = precio_final / 1.19
            if precio_final > 0:
                precio_venta = precio_final / 1.19
            else:
                precio_venta = 0.0
            
            # CALCULAR margen_porcentaje desde precio_venta y costo
            # Fórmula: margen = ((precio_venta - costo) /costo) * 100
            if precio_costo > 0 and precio_venta > 0:
                margen_porcentaje = ((precio_venta - precio_costo) / precio_costo) * 100
            else:
                margen_porcentaje = 0.0
            
            # Crear o actualizar artículo
            articulo, created = Articulo.objects.update_or_create(
                codigo=codigo,
                empresa=empresa,
                defaults={
                    'nombre': nombre,
                    'descripcion': datos_articulo.get('descripcion', ''),
                    'categoria': categoria,
                    'unidad_medida': unidad_medida,
                    'precio_costo': str(round(precio_costo, 2)),
                    'precio_venta': str(round(precio_venta, 2)),
                    'precio_final': str(round(precio_final, 2)),
                    'margen_porcentaje': str(round(margen_porcentaje, 2)),
                    'codigo_barras': datos_articulo.get('codigo_barras', '') or None,
                }
            )
            
            importados += 1
        except Exception as e:
            errores.append(f"Error en código {fila.get('CODIGO', 'N/A')}: {str(e)}")
    
    return {
        'success': True,
        'importados': importados,
        'omitidos': omitidos,
        'errores': errores,
        'total': len(datos)
    }


def importar_ventas(datos, mapeo, empresa):
    """Importar ventas desde base de datos externa"""
    from ventas.models import Venta, FormaPago
    from clientes.models import Cliente
    from decimal import Decimal
    from django.utils import timezone
    from datetime import datetime, date
    import re

    importados = 0
    actualizados = 0
    errores = []
    omitidos = 0

    for fila in datos:
        try:
            datos_venta = {}
            for campo_destino, campo_origen in mapeo.items():
                if campo_origen and campo_origen in fila:
                    valor = fila[campo_origen]
                    datos_venta[campo_destino] = valor

            numero_venta = str(datos_venta.get('numero_venta') or '').strip()
            if not numero_venta:
                omitidos += 1
                continue

            # Fecha de venta
            fecha_val = datos_venta.get('fecha')
            fecha = timezone.localdate()
            if fecha_val:
                if isinstance(fecha_val, (datetime, date)):
                    fecha = fecha_val.date() if isinstance(fecha_val, datetime) else fecha_val
                elif isinstance(fecha_val, str):
                    fecha_str = fecha_val.strip().split(' ')[0]
                    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d'):
                        try:
                            fecha = datetime.strptime(fecha_str, fmt).date()
                            break
                        except ValueError:
                            pass

            # Tipo de documento
            tipo_doc_raw = str(datos_venta.get('tipo_documento') or 'boleta').strip().lower()
            if 'fact' in tipo_doc_raw or tipo_doc_raw in ('33', '34'):
                tipo_documento = 'factura'
            elif 'guia' in tipo_doc_raw or 'guía' in tipo_doc_raw or tipo_doc_raw == '52':
                tipo_documento = 'guia'
            elif 'vale' in tipo_doc_raw:
                tipo_documento = 'vale'
            elif 'ticket' in tipo_doc_raw:
                tipo_documento = 'ticket'
            elif 'cotiz' in tipo_doc_raw:
                tipo_documento = 'cotizacion'
            else:
                tipo_documento = 'boleta'

            # Cliente
            cliente = None
            cliente_rut = str(datos_venta.get('cliente_rut') or '').strip()
            if cliente_rut:
                cliente = Cliente.objects.filter(empresa=empresa, rut__iexact=cliente_rut).first()
                if not cliente:
                    rut_limpio = re.sub(r'[^0-9kK]', '', cliente_rut)
                    for c in Cliente.objects.filter(empresa=empresa):
                        if re.sub(r'[^0-9kK]', '', c.rut or '') == rut_limpio:
                            cliente = c
                            break

            if not cliente and datos_venta.get('cliente_nombre'):
                cliente_nombre = str(datos_venta.get('cliente_nombre')).strip()
                if cliente_nombre:
                    cliente = Cliente.objects.filter(empresa=empresa, nombre__iexact=cliente_nombre).first()
                    if not cliente and cliente_rut:
                        cliente = Cliente.objects.create(empresa=empresa, rut=cliente_rut, nombre=cliente_nombre)

            def _to_dec(val):
                if val is None or val == '':
                    return Decimal('0.00')
                try:
                    s = str(val).replace('$', '').replace(' ', '').replace(',', '.')
                    return Decimal(s)
                except Exception:
                    return Decimal('0.00')

            total = _to_dec(datos_venta.get('total'))
            subtotal = _to_dec(datos_venta.get('subtotal'))
            iva = _to_dec(datos_venta.get('iva'))
            descuento = _to_dec(datos_venta.get('descuento'))

            if total > 0 and subtotal == 0:
                subtotal = round(total / Decimal('1.19'), 2)
                iva = total - subtotal
            elif subtotal > 0 and total == 0:
                iva = round(subtotal * Decimal('0.19'), 2)
                total = subtotal + iva

            forma_pago = None
            fp_nombre = str(datos_venta.get('forma_pago') or '').strip()
            if fp_nombre:
                forma_pago = FormaPago.objects.filter(empresa=empresa, nombre__icontains=fp_nombre).first()

            estado_raw = str(datos_venta.get('estado') or 'confirmada').strip().lower()
            if 'anul' in estado_raw:
                estado = 'anulada'
            elif 'borr' in estado_raw:
                estado = 'borrador'
            else:
                estado = 'confirmada'

            obs = str(datos_venta.get('observaciones') or '').strip()

            venta, created = Venta.objects.update_or_create(
                empresa=empresa,
                tipo_documento=tipo_documento,
                numero_venta=numero_venta,
                defaults={
                    'fecha': fecha,
                    'cliente': cliente,
                    'forma_pago': forma_pago,
                    'tipo_documento_planeado': tipo_documento if tipo_documento != 'vale' else 'boleta',
                    'subtotal': subtotal,
                    'neto': subtotal,
                    'iva': iva,
                    'descuento': descuento,
                    'total': total,
                    'monto_pagado': total if estado == 'confirmada' else Decimal('0.00'),
                    'saldo_pendiente': Decimal('0.00'),
                    'estado': estado,
                    'observaciones': obs,
                }
            )
            if created:
                importados += 1
            else:
                actualizados += 1

        except Exception as e:
            num_err = fila.get('NUMERO', fila.get('FOLIO', fila.get('numero', 'N/A')))
            errores.append(f"Error en venta N° {num_err}: {str(e)}")

    return {
        'success': True,
        'importados': importados,
        'actualizados': actualizados,
        'omitidos': omitidos,
        'errores': errores,
        'total': len(datos)
    }

