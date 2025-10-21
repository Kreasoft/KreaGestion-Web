"""
Comando para generar documentos de prueba reutilizando folios
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from ventas.models import Venta, Cliente, Vendedor
from articulos.models import Articulo
from facturacion_electronica.dte_service import DTEService
from decimal import Decimal


class Command(BaseCommand):
    help = 'Genera documentos de prueba reutilizando folios (modo prueba)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tipo',
            type=str,
            choices=['33', '39', '34'],
            default='33',
            help='Tipo de documento (33=Factura, 39=Boleta, 34=Factura Exenta)'
        )
        parser.add_argument(
            '--cantidad',
            type=int,
            default=1,
            help='Cantidad de documentos a generar'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Generando documentos de prueba...'))

        # Obtener datos necesarios
        try:
            empresa = self._obtener_empresa()
            cliente = self._obtener_cliente()
            vendedor = self._obtener_vendedor()
            articulo = self._obtener_articulo()
            usuario = self._obtener_usuario()

            if not all([empresa, cliente, vendedor, articulo, usuario]):
                return

            # Verificar que el modo prueba esté habilitado
            if not empresa.modo_reutilizacion_folios:
                self.stdout.write(self.style.ERROR('ERROR: El modo de reutilización no está habilitado'))
                self.stdout.write(self.style.ERROR('Use: python manage.py configurar_modo_prueba --habilitar'))
                return

            # Generar documentos
            for i in range(options['cantidad']):
                venta = self._crear_venta_prueba(empresa, cliente, vendedor, articulo, usuario)
                if venta:
                    self._generar_dte(venta, options['tipo'], empresa)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))

    def _obtener_empresa(self):
        """Obtiene la primera empresa con facturación electrónica activa"""
        from empresas.models import Empresa
        try:
            return Empresa.objects.filter(facturacion_electronica=True).first()
        except:
            self.stdout.write(self.style.ERROR('No se encontró empresa con facturación electrónica activa'))
            return None

    def _obtener_cliente(self):
        """Obtiene o crea un cliente de prueba"""
        try:
            cliente = Cliente.objects.first()
            if not cliente:
                cliente = Cliente.objects.create(
                    nombre='Cliente Prueba',
                    rut='66666666-6',
                    email='cliente@prueba.cl'
                )
            return cliente
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error con cliente: {e}'))
            return None

    def _obtener_vendedor(self):
        """Obtiene o crea un vendedor de prueba"""
        try:
            vendedor = Vendedor.objects.first()
            if not vendedor:
                vendedor = Vendedor.objects.create(
                    nombre='Vendedor Prueba',
                    rut='11111111-1'
                )
            return vendedor
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error con vendedor: {e}'))
            return None

    def _obtener_articulo(self):
        """Obtiene o crea un artículo de prueba"""
        try:
            articulo = Articulo.objects.first()
            if not articulo:
                articulo = Articulo.objects.create(
                    nombre='Articulo Prueba',
                    precio=10000,
                    stock=100
                )
            return articulo
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error con articulo: {e}'))
            return None

    def _obtener_usuario(self):
        """Obtiene el primer usuario administrador"""
        try:
            return User.objects.filter(is_superuser=True).first()
        except:
            self.stdout.write(self.style.ERROR('No se encontró usuario administrador'))
            return None

    def _crear_venta_prueba(self, empresa, cliente, vendedor, articulo, usuario):
        """Crea una venta de prueba"""
        try:
            # Generar número de venta único
            import random
            numero_venta = f'PRUEBA-{random.randint(1000, 9999)}'

            venta = Venta.objects.create(
                empresa=empresa,
                cliente=cliente,
                vendedor=vendedor,
                usuario_creacion=usuario,
                numero_venta=numero_venta,
                subtotal=Decimal('10000'),
                iva=Decimal('1900'),
                total=Decimal('11900'),
                estado='confirmada'
            )

            # Agregar item a la venta
            from ventas.models import VentaDetalle
            VentaDetalle.objects.create(
                venta=venta,
                articulo=articulo,
                cantidad=Decimal('1'),
                precio_unitario=Decimal('10000'),
                precio_total=Decimal('10000')
            )

            return venta
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error creando venta: {e}'))
            return None

    def _generar_dte(self, venta, tipo_dte, empresa):
        """Genera el DTE para la venta"""
        try:
            dte_service = DTEService(empresa)
            dte = dte_service.generar_dte_desde_venta(venta, tipo_dte)

            if dte:
                self.stdout.write(self.style.SUCCESS(f'Documento {tipo_dte} generado - Folio: {dte.folio}'))

                # Intentar enviar al SII si no está en modo prueba completo
                if not empresa.modo_reutilizacion_folios:
                    respuesta = dte_service.enviar_dte_al_sii(dte)
                    if respuesta:
                        self.stdout.write(self.style.SUCCESS(f'  Enviado al SII - Track ID: {respuesta.get("track_id")}'))
            else:
                self.stdout.write(self.style.ERROR(f'Error generando documento {tipo_dte}'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error generando DTE: {str(e)}'))
