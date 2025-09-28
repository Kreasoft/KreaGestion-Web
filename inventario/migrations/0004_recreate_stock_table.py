from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("inventario", "0003_make_bodega_required"),
        ("bodegas", "0001_initial"),
    ]

    operations = [
        # Recrear la tabla stock sin sucursal_id
        migrations.RunSQL(
            """
            CREATE TABLE inventario_stock_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cantidad decimal NOT NULL,
                stock_minimo decimal NOT NULL,
                stock_maximo decimal NOT NULL,
                precio_promedio decimal NOT NULL,
                fecha_actualizacion datetime NOT NULL,
                actualizado_por_id INTEGER NULL,
                articulo_id bigint NOT NULL,
                empresa_id bigint NOT NULL,
                bodega_id bigint NOT NULL,
                FOREIGN KEY (actualizado_por_id) REFERENCES auth_user (id),
                FOREIGN KEY (articulo_id) REFERENCES articulos_articulo (id),
                FOREIGN KEY (empresa_id) REFERENCES empresas_empresa (id),
                FOREIGN KEY (bodega_id) REFERENCES bodegas_bodega (id)
            );
            """,
            reverse_sql="DROP TABLE inventario_stock_new;"
        ),
        
        # Copiar datos existentes (solo los que tienen bodega_id)
        migrations.RunSQL(
            """
            INSERT INTO inventario_stock_new 
            SELECT id, cantidad, stock_minimo, stock_maximo, precio_promedio, 
                   fecha_actualizacion, actualizado_por_id, articulo_id, empresa_id, bodega_id
            FROM inventario_stock 
            WHERE bodega_id IS NOT NULL;
            """,
            reverse_sql=""
        ),
        
        # Eliminar tabla antigua
        migrations.RunSQL(
            "DROP TABLE inventario_stock;",
            reverse_sql=""
        ),
        
        # Renombrar tabla nueva
        migrations.RunSQL(
            "ALTER TABLE inventario_stock_new RENAME TO inventario_stock;",
            reverse_sql=""
        ),
        
        # Crear índices
        migrations.RunSQL(
            """
            CREATE UNIQUE INDEX inventario_stock_empresa_id_bodega_id_articulo_id_uniq 
            ON inventario_stock (empresa_id, bodega_id, articulo_id);
            """,
            reverse_sql=""
        ),
        
        migrations.RunSQL(
            """
            CREATE INDEX inventario_stock_bodega_id_bd3e5949 
            ON inventario_stock (bodega_id);
            """,
            reverse_sql=""
        ),
    ]
