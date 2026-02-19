"""
Script para marcar guías existentes con TED como enviadas
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from facturacion_electronica.models import DocumentoTributarioElectronico


class Command(BaseCommand):
    help = 'Marca las guías con TED como enviadas'

    def handle(self, *args, **options):
        # Buscar guías con TED que no estén marcadas como enviadas
        guias = DocumentoTributarioElectronico.objects.filter(
            tipo_dte='52',
            timbre_electronico__isnull=False
        ).exclude(estado_sii='enviado')
        
        total = guias.count()
        
        if total == 0:
            self.stdout.write(self.style.SUCCESS('No hay guías pendientes con TED'))
            return
        
        self.stdout.write(f'Encontradas {total} guías con TED pendientes de marcar como enviadas')
        
        actualizadas = 0
        for guia in guias:
            self.stdout.write(f'  Guía Folio {guia.folio}: {guia.estado_sii} → enviado')
            guia.estado_sii = 'enviado'
            guia.fecha_envio_sii = timezone.now()
            guia.error_envio = ''
            guia.save(update_fields=['estado_sii', 'fecha_envio_sii', 'error_envio'])
            actualizadas += 1
        
        self.stdout.write(self.style.SUCCESS(f'✓ {actualizadas} guías actualizadas como enviadas'))
