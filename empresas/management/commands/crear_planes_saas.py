from django.core.management.base import BaseCommand
from empresas.models import PlanSaaS
from decimal import Decimal

class Command(BaseCommand):
    help = 'Crea los planes SaaS base para el sistema'

    def handle(self, *args, **options):
        planes = [
            {
                'nombre': 'Plan Emprendedor',
                'descripcion': 'Ideal para pequeños negocios que están comenzando.',
                'precio_mensual': Decimal('19990'),
                'max_usuarios': 2,
                'max_sucursales': 1,
                'max_productos': 500,
                'max_documentos_mes': 100,
                'incluye_produccion': False,
            },
            {
                'nombre': 'Plan Profesional',
                'descripcion': 'Nuestro plan más popular para empresas en crecimiento.',
                'precio_mensual': Decimal('39990'),
                'max_usuarios': 5,
                'max_sucursales': 3,
                'max_productos': 5000,
                'max_documentos_mes': 1000,
                'incluye_produccion': True,
                'incluye_despacho': True,
            },
            {
                'nombre': 'Plan Corporativo',
                'descripcion': 'Control total para grandes empresas con múltiples almacenes.',
                'precio_mensual': Decimal('89990'),
                'max_usuarios': 50,
                'max_sucursales': 10,
                'max_productos': 50000,
                'max_documentos_mes': 10000,
                'incluye_produccion': True,
                'incluye_despacho': True,
                'incluye_api': True,
            }
        ]

        for p_data in planes:
            plan, created = PlanSaaS.objects.get_or_create(
                nombre=p_data['nombre'],
                defaults=p_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'✅ Plan creado: {plan.nombre}'))
            else:
                self.stdout.write(self.style.WARNING(f'⚠️ Plan ya existía: {plan.nombre}'))
