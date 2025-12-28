from django.core.management.base import BaseCommand
from django.db import transaction
from django.core.files.base import ContentFile
from facturacion_electronica.models import ArchivoCAF
from empresas.models import Empresa
from dte_gdexpress.caf.gestor import GestorCAF
import os
from lxml import etree
import datetime

class Command(BaseCommand):
    help = 'Carga archivos CAF desde el directorio folios/'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("=== Iniciando Carga de CAFs ==="))
        
        empresa = Empresa.objects.first()
        if not empresa:
            self.stdout.write(self.style.ERROR("No hay empresa creada"))
            return

        caf_dir = os.path.join(os.getcwd(), 'folios')
        if not os.path.exists(caf_dir):
             self.stdout.write(self.style.ERROR(f"Directorio folios no existe: {caf_dir}"))
             return

        files = [f for f in os.listdir(caf_dir) if f.endswith('.xml')]
        
        if not files:
            self.stdout.write(self.style.WARNING("No hay archivos XML en folios/"))
            return

        for filename in files:
            filepath = os.path.join(caf_dir, filename)
            self.stdout.write(f"\nProcesando: {filename}")
            
            try:
                with open(filepath, 'rb') as f:
                    xml_content = f.read()
                
                # Parsear XML para extraer datos
                parser = etree.XMLParser(recover=True, encoding='iso-8859-1')
                try:
                    root = etree.fromstring(xml_content, parser=parser)
                except Exception as e:
                    # Retry with default parser/utf-8
                    try:
                        root = etree.fromstring(xml_content)
                    except Exception as e2:
                        self.stdout.write(self.style.WARNING(f"⚠️  No es un XML válido: {e} | {e2}"))
                        continue
                
                # Namespace map (habitualmente CAF no tiene ns definidos explícitamente en el root para AUTORIZACION)
                # La estructura es <AUTORIZACION><CAF><DA><TD>...</TD><RNG><D>...</D><H>...</H></RNG>...
                
                caf_node = root.find('.//CAF')
                if caf_node is None:
                    self.stdout.write(self.style.WARNING("⚠️  No contiene nodo CAF"))
                    continue

                da_node = caf_node.find('DA')
                tipo_dte = da_node.find('TD').text
                
                rng_node = da_node.find('RNG')
                folio_desde = int(rng_node.find('D').text)
                folio_hasta = int(rng_node.find('H').text)
                
                fa_text = da_node.find('FA').text # Fecha Autorizacion YYYY-MM-DD
                fecha_auth = datetime.datetime.strptime(fa_text, '%Y-%m-%d').date()
                
                # Extraer firma FRMA
                frma_node = caf_node.find('FRMA')
                firma = frma_node.text
                
                # Guardar en DB
                with transaction.atomic():
                    # Verificar si ya existe
                    exists = ArchivoCAF.objects.filter(
                        empresa=empresa,
                        tipo_documento=tipo_dte,
                        folio_desde=folio_desde,
                        folio_hasta=folio_hasta
                    ).exists()
                    
                    if exists:
                        self.stdout.write(self.style.WARNING(f"ℹ️  CAF {tipo_dte} ({folio_desde}-{folio_hasta}) ya existe. Saltando."))
                        continue
                    
                    nuevo_caf = ArchivoCAF(
                        empresa=empresa,
                        tipo_documento=tipo_dte,
                        folio_desde=folio_desde,
                        folio_hasta=folio_hasta,
                        cantidad_folios=(folio_hasta - folio_desde + 1),
                        contenido_caf=xml_content.decode('utf-8', errors='ignore'),
                        fecha_autorizacion=fecha_auth,
                        firma_electronica=firma,
                        folios_utilizados=0,
                        folio_actual=folio_desde - 1,
                        estado='activo',
                        usuario_carga=None
                    )
                    
                    # Guardar archivo fisico
                    nuevo_caf.archivo_xml.save(filename, ContentFile(xml_content), save=False)
                    nuevo_caf.save()
                    
                    self.stdout.write(self.style.SUCCESS(f"✅ CAF cargado: Tipo {tipo_dte} [{folio_desde}-{folio_hasta}]"))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Error procesando {filename}: {e}"))
                import traceback
                traceback.print_exc()

