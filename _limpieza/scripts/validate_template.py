import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from django.template import Template, TemplateSyntaxError
from django.template.loader import get_template

try:
    template = get_template('base.html')
    print("✓ Template base.html es válido sintácticamente")
except TemplateSyntaxError as e:
    print(f"✗ Error de sintaxis en template:")
    print(f"  Línea: {e.template_debug['line']}")
    print(f"  Mensaje: {e}")
    print(f"  Contexto:")
    for i, line in enumerate(e.template_debug['during'].split('\n'), 1):
        print(f"    {i}: {line}")
except Exception as e:
    print(f"✗ Error: {e}")
