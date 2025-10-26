from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from empresas.decorators import requiere_empresa
import pymysql
import json

from .forms import ConexionMySQLForm, SeleccionTablaForm
from clientes.models import Cliente
from proveedores.models import Proveedor
from articulos.models import Articulo, CategoriaArticulo, UnidadMedida

# Importar funciones de mantenimiento
from .mantenimiento_utils import (
    optimizar_tablas, crear_backup, verificar_integridad,
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
