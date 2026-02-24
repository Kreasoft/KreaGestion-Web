from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.models import User
from decimal import Decimal
from empresas.models import Empresa, Sucursal
from clientes.models import Cliente
from ventas.models import Venta, VentaDetalle, Vendedor, FormaPago
from articulos.models import Articulo, CategoriaArticulo, UnidadMedida
from facturacion_electronica.dte_service import DTEService

class Command(BaseCommand):
    help = 'Crea una venta ficticia y trata de enviarla al SII usando DTEService'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== Iniciando Prueba de Emisión DTE ==='))

        # 1. Obtener Empresa
        empresa = Empresa.objects.first()
        if not empresa:
            self.stdout.write(self.style.ERROR('No hay empresas creadas.'))
            return
            
        # Asegurar datos de resolucion para pruebas
        import datetime
        empresa.resolucion_numero = 80  # Número de resolución oficial para ambiente de pruebas SII
        empresa.resolucion_fecha = datetime.date(2014, 8, 22)
        empresa.rut = '77117239-3' # RUT valido para pruebas DTEBox/GDExpress (usualmente KreaSoft)
        empresa.save()
        
        self.stdout.write(f"Empresa seleccionada: {empresa.nombre} (RUT: {empresa.rut})")
        self.stdout.write(f"Resolución: {empresa.resolucion_numero} del {empresa.resolucion_fecha}")

        # 2. Obtener Usuario
        usuario = User.objects.first()
        if not usuario:
             self.stdout.write(self.style.ERROR('No hay usuarios creados.'))
             # Crear uno temporal si no hay
             usuario = User.objects.create_user('test_user', 'test@example.com', 'password')

        # 3. Obtener Cliente (Crear si no existe)
        cliente, created = Cliente.objects.get_or_create(
            rut='66666666-6',
            empresa=empresa,
            defaults={
                'nombre': 'Cliente de Prueba DTE',
                'direccion': 'Dirección de Prueba 123',
                'comuna': 'Santiago',
                'ciudad': 'Santiago',
                'telefono': '912345678',
                'email': 'cliente@prueba.cl',
                'giro': 'Giro de Prueba',
                'tipo_cliente': 'consumidor_final'
            }
        )
        self.stdout.write(f"Cliente: {cliente.nombre} (RUT: {cliente.rut})")

        # 4. Obtener/Crear Vendedor
        vendedor, _ = Vendedor.objects.get_or_create(
            codigo='VEND-TEST',
            empresa=empresa,
            defaults={'nombre': 'Vendedor Test'}
        )

        # 5. Obtener/Crear Forma de Pago
        forma_pago, _ = FormaPago.objects.get_or_create(
            codigo='EFECTIVO',
            empresa=empresa,
            defaults={'nombre': 'Efectivo'}
        )
        
        # 6. Obtener/Crear Sucursal
        sucursal = Sucursal.objects.filter(empresa=empresa).first()
        if not sucursal:
            sucursal = Sucursal.objects.create(
                empresa=empresa,
                codigo='SUC-001',
                nombre='Sucursal Test',
                direccion='Dir Test',
                comuna='Comuna Test',
                ciudad='Ciudad Test',
                region='Region Test',
                telefono='123456',
                horario_apertura='09:00',
                horario_cierre='18:00'
            )

        # 7. Crear Articulo de Prueba
        unidad, _ = UnidadMedida.objects.get_or_create(
            empresa=empresa, nombre='Unidad', defaults={'simbolo': 'UN'}
        )
        categoria, _ = CategoriaArticulo.objects.get_or_create(
            empresa=empresa, codigo='CAT-TEST', defaults={'nombre': 'Categoria Test'}
        )
        
        articulo, _ = Articulo.objects.get_or_create(
            empresa=empresa,
            codigo='ART-DTE-TEST',
            defaults={
                'nombre': 'Articulo Prueba DTE',
                'categoria': categoria,
                'unidad_medida': unidad,
                'precio_venta': '1000',
                'precio_final': '1190', # Con IVA
                'control_stock': False
            }
        )

        # 8. Crear Venta
        # Generar numero venta unico simple
        import random
        # Usar un numero aleatorio grande para evitar conflictos
        numero_venta = f"TEST-{random.randint(10000, 99999)}"
        
        venta = Venta.objects.create(
            empresa=empresa,
            sucursal=sucursal,
            numero_venta=numero_venta,
            cliente=cliente,
            vendedor=vendedor,
            forma_pago=forma_pago,
            tipo_documento='boleta',
            tipo_documento_planeado='boleta',
            estado='confirmada',
            usuario_creacion=usuario
        )

        # 9. Crear Detalle Venta
        VentaDetalle.objects.create(
            venta=venta,
            articulo=articulo,
            cantidad=1,
            precio_unitario=1190, # Bruto
            precio_total=1190
        )
        
        venta.calcular_totales()
        self.stdout.write(f"Venta creada: ID {venta.id}, Total {venta.total}")

        # 10. Generar y Enviar DTE
        try:
            service = DTEService(empresa)
            self.stdout.write("Generando DTE (Boleta)...")
            
            # Usamos tipo 33 (Factura) forzada a folio 72
            dte = service.generar_dte_desde_venta(venta, tipo_dte='33')
            dte.folio = 72
            dte.save()
            self.stdout.write(self.style.SUCCESS(f"DTE Generado Forzado: Folio {dte.folio}, ID {dte.id}"))
            
            # Guardar XML para inspección
            with open('ultimo_dte_prueba.xml', 'w', encoding='ISO-8859-1') as f:
                f.write(dte.xml_firmado)
            self.stdout.write(f"XML guardado en ultimo_dte_prueba.xml para inspección")
            
            # 11. Enviar al SII
            self.stdout.write("Enviando al SII (GDExpress)...")
            resultado = service.enviar_dte_al_sii(dte)
            
            if resultado['success']:
                self.stdout.write(self.style.SUCCESS(f"Envio Exitoso! Track ID: {resultado['track_id']}"))
                self.stdout.write(f"XML Respuesta: {resultado.get('xml_respuesta')[:200]}...")
            else:
                 self.stdout.write(self.style.ERROR(f"Error en envio: {resultado.get('error')}"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Excepcion durante el proceso: {str(e)}"))
            # Imprimir respuesta raw si está disponible
            if hasattr(e, 'read'):
                print(f"Respuesta Raw: {e.read().decode('utf-8', errors='ignore')}")
            import traceback
            traceback.print_exc()
