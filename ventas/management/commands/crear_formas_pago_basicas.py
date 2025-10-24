from django.core.management.base import BaseCommand
from ventas.models import FormaPago
from empresas.models import Empresa


class Command(BaseCommand):
    help = 'Crear formas de pago básicas para todas las empresas'

    def handle(self, *args, **options):
        empresas = Empresa.objects.all()
        
        if not empresas.exists():
            self.stdout.write(
                self.style.ERROR('No hay empresas en el sistema.')
            )
            return
        
        formas_pago_basicas = [
            {'codigo': 'EF', 'nombre': 'Efectivo', 'requiere_cheque': False, 'es_cuenta_corriente': False},
            {'codigo': 'CH', 'nombre': 'Cheque', 'requiere_cheque': True, 'es_cuenta_corriente': False},
            {'codigo': 'TR', 'nombre': 'Transferencia', 'requiere_cheque': False, 'es_cuenta_corriente': False},
            {'codigo': 'TC', 'nombre': 'Tarjeta de Crédito', 'requiere_cheque': False, 'es_cuenta_corriente': False},
            {'codigo': 'TD', 'nombre': 'Tarjeta de Débito', 'requiere_cheque': False, 'es_cuenta_corriente': False},
            {'codigo': 'CC', 'nombre': 'Cuenta Corriente', 'requiere_cheque': False, 'es_cuenta_corriente': True},
        ]
        
        for empresa in empresas:
            self.stdout.write(f'Procesando empresa: {empresa.nombre}')
            
            for fp_data in formas_pago_basicas:
                forma_pago, created = FormaPago.objects.get_or_create(
                    empresa=empresa,
                    codigo=fp_data['codigo'],
                    defaults={
                        'nombre': fp_data['nombre'],
                        'requiere_cheque': fp_data['requiere_cheque'],
                        'es_cuenta_corriente': fp_data['es_cuenta_corriente'],
                        'activo': True
                    }
                )
                
                if created:
                    self.stdout.write(
                        self.style.SUCCESS(f'  ✓ Creada: {fp_data["codigo"]} - {fp_data["nombre"]}')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'  - Ya existe: {fp_data["codigo"]} - {fp_data["nombre"]}')
                    )
        
        self.stdout.write(
            self.style.SUCCESS('\nFormas de pago básicas creadas exitosamente.')
        )











