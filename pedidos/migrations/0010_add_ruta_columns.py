# Generated manually to fix missing columns in pedidos_ruta table

from django.db import migrations, models
import django.db.models.deletion


def add_missing_columns(apps, schema_editor):
    """Agrega las columnas faltantes a la tabla pedidos_ruta si no existen"""
    from django.db import connection
    
    with connection.cursor() as cursor:
        # Verificar qué columnas existen
        cursor.execute("PRAGMA table_info(pedidos_ruta)")
        existing_columns = [row[1] for row in cursor.fetchall()]
        
        # Agregar dias_visita si no existe
        if 'dias_visita' not in existing_columns:
            cursor.execute("ALTER TABLE pedidos_ruta ADD COLUMN dias_visita VARCHAR(50) DEFAULT ''")
        
        # Agregar orden_visita si no existe
        if 'orden_visita' not in existing_columns:
            cursor.execute("ALTER TABLE pedidos_ruta ADD COLUMN orden_visita INTEGER DEFAULT 0")
        
        # Agregar creado_por_id si no existe
        if 'creado_por_id' not in existing_columns:
            cursor.execute("ALTER TABLE pedidos_ruta ADD COLUMN creado_por_id INTEGER NULL")


def reverse_add_columns(apps, schema_editor):
    """No revertimos porque podríamos perder datos"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('pedidos', '0009_ruta_hojaruta'),
        migrations.swappable_dependency('auth.user'),
    ]

    operations = [
        migrations.RunPython(add_missing_columns, reverse_add_columns),
    ]

