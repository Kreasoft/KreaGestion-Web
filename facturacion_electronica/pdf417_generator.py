"""
Generador de código PDF417 para timbre electrónico
"""
from pdf417 import encode, render_image
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import base64


class PDF417Generator:
    """Generador de código de barras PDF417 para timbres electrónicos"""
    
    @staticmethod
    def generar_imagen_pdf417(ted_xml, ancho=400, alto=150):
        """
        Genera una imagen PNG del código PDF417 a partir del TED
        
        Args:
            ted_xml: XML del TED (Timbre Electrónico Digital)
            ancho: Ancho de la imagen en píxeles
            alto: Alto de la imagen en píxeles
            
        Returns:
            bytes: Imagen PNG en bytes
        """
        try:
            # Detectar si el TED viene en base64 (empieza con <TED -> PFRFRC)
            # DTEBox y otros servicios suelen entregarlo ya codificado
            if isinstance(ted_xml, str) and (ted_xml.startswith('PFRFRC') or ted_xml.startswith('PD')):
                try:
                    ted_xml = base64.b64decode(ted_xml).decode('ISO-8859-1')
                    print(f"[PDF417] TED decodificado desde base64 (longitud: {len(ted_xml)})")
                except:
                    print("[PDF417] Falló decodificación base64, se usará raw")

            # El SII requiere ISO-8859-1 para el timbre
            if isinstance(ted_xml, str):
                data = ted_xml.encode('ISO-8859-1', errors='replace')
            else:
                data = ted_xml

            # Codificar el TED en PDF417
            # Intentar parámetros adaptativos si falla por longitud
            codes = None
            # security_level 2 es estándar, pero bajamos a 1 o 0 si el DTE es extremadamente grande
            # y aumentamos columnas para aprovechar más capacidad (máx 30 columnas)
            for s_level in [2, 1, 0]:
                for cols in [15, 18, 20, 25, 30]:
                    try:
                        codes = encode(data, columns=cols, security_level=s_level)
                        if codes: break
                    except Exception:
                        continue
                if codes: break
            
            if not codes:
                raise ValueError("No se pudo encajar la información en el PDF417 ni con parámetros mínimos")
            
            # Renderizar la imagen
            # Aumentamos scale para mejor resolución
            image = render_image(
                codes,
                scale=3,  # Factor de escala
                ratio=3,  # Relación de aspecto
                padding=10  # Padding alrededor del código
            )
            
            # Redimensionar al tamaño solicitado manteniendo calidad y RELACIÓN DE ASPECTO
            # No queremos aplastar el código de barras
            image.thumbnail((ancho, alto), Image.Resampling.LANCZOS)
            
            # Crear un canvas del tamaño exacto 400x150 y pegar el código centrado
            canvas = Image.new('RGB', (ancho, alto), color='white')
            offset = ((ancho - image.size[0]) // 2, (alto - image.size[1]) // 2)
            canvas.paste(image, offset)
            
            # Convertir a bytes
            buffer = BytesIO()
            canvas.save(buffer, format='PNG')
            buffer.seek(0)
            
            return buffer.getvalue()
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"ERROR crítico al generar PDF417: {str(e)}\n{error_details}")
            # Generar imagen de placeholder en caso de error
            return PDF417Generator._generar_placeholder(ancho, alto)
    
    @staticmethod
    def generar_base64_pdf417(ted_xml, ancho=400, alto=150):
        """
        Genera el código PDF417 en formato base64 para usar en HTML
        
        Args:
            ted_xml: XML del TED
            ancho: Ancho de la imagen
            alto: Alto de la imagen
            
        Returns:
            str: Imagen en base64
        """
        imagen_bytes = PDF417Generator.generar_imagen_pdf417(ted_xml, ancho, alto)
        return base64.b64encode(imagen_bytes).decode('ascii')
    
    @staticmethod
    def _generar_placeholder(ancho=400, alto=150):
        """
        Genera una imagen placeholder cuando falla la generación del PDF417
        
        Args:
            ancho: Ancho de la imagen
            alto: Alto de la imagen
            
        Returns:
            bytes: Imagen PNG placeholder
        """
        # Crear imagen en blanco
        image = Image.new('RGB', (ancho, alto), color='white')
        draw = ImageDraw.Draw(image)
        
        # Dibujar borde
        draw.rectangle([(0, 0), (ancho-1, alto-1)], outline='black', width=2)
        
        # Agregar texto
        try:
            # Intentar usar una fuente del sistema
            font = ImageFont.truetype("arial.ttf", 14)
        except:
            # Usar fuente por defecto si no encuentra arial
            font = ImageFont.load_default()
        
        text = "TIMBRE ELECTRÓNICO SII"
        
        # Calcular posición centrada del texto
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        x = (ancho - text_width) // 2
        y = (alto - text_height) // 2
        
        draw.text((x, y), text, fill='black', font=font)
        
        # Convertir a bytes
        buffer = BytesIO()
        image.save(buffer, format='PNG')
        buffer.seek(0)
        
        return buffer.getvalue()
    
    @staticmethod
    def guardar_pdf417_en_dte(dte):
        """
        Genera y guarda el PDF417 en un objeto DTE
        
        Args:
            dte: Instancia de DocumentoTributarioElectronico
            
        Returns:
            bool: True si se guardó exitosamente
        """
        try:
            # Generar imagen PDF417 (si no hay TED, usar placeholder igualmente)
            if dte.timbre_electronico:
                # Usar dimensiones mayores para mejor legibilidad
                imagen_bytes = PDF417Generator.generar_imagen_pdf417(
                    dte.timbre_electronico,
                    ancho=400,
                    alto=150
                )
            else:
                print("[WARN] DTE no tiene TED generado. Se usara placeholder de timbre.")
                imagen_bytes = PDF417Generator._generar_placeholder(ancho=400, alto=150)

            # Guardar en el campo del modelo
            from django.core.files.base import ContentFile
            dte.timbre_pdf417.save(
                f'timbre_{dte.tipo_dte}_{dte.folio}.png',
                ContentFile(imagen_bytes),
                save=True
            )

            print(f"PDF417 generado y guardado para DTE {dte.tipo_dte}-{dte.folio}")
            return True

        except Exception as e:
            print(f"ERROR al guardar PDF417: {str(e)}")
            return False
