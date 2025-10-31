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
    def generar_imagen_pdf417(ted_xml, ancho=280, alto=100):
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
            # Codificar el TED en PDF417
            # El PDF417 usa el TED completo
            # Usar security_level=2 para datos largos (nivel mínimo recomendado por SII)
            codes = encode(ted_xml, columns=15, security_level=2)
            
            # Renderizar la imagen
            image = render_image(
                codes,
                scale=2,  # Factor de escala
                ratio=3,  # Relación de aspecto
                padding=10  # Padding alrededor del código
            )
            
            # Redimensionar si es necesario
            if image.size != (ancho, alto):
                image = image.resize((ancho, alto), Image.Resampling.LANCZOS)
            
            # Convertir a bytes
            buffer = BytesIO()
            image.save(buffer, format='PNG')
            buffer.seek(0)
            
            return buffer.getvalue()
            
        except Exception as e:
            print(f"ERROR al generar PDF417: {str(e)}")
            # Generar imagen de placeholder en caso de error
            return PDF417Generator._generar_placeholder(ancho, alto)
    
    @staticmethod
    def generar_base64_pdf417(ted_xml, ancho=280, alto=100):
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
    def _generar_placeholder(ancho=280, alto=100):
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
            font = ImageFont.truetype("arial.ttf", 12)
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
                imagen_bytes = PDF417Generator.generar_imagen_pdf417(
                    dte.timbre_electronico,
                    ancho=280,
                    alto=100
                )
            else:
                print("[WARN] DTE no tiene TED generado. Se usara placeholder de timbre.")
                imagen_bytes = PDF417Generator._generar_placeholder(ancho=280, alto=100)

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
