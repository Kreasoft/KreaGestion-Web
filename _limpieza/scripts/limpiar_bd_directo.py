"""
Script para limpiar datos directamente de la base de datos
"""
import sqlite3
import os

# Ruta a la base de datos
db_path = 'db.sqlite3'

if not os.path.exists(db_path):
    print(f"❌ No se encontró la base de datos en: {db_path}")
    exit(1)

print("🔄 Conectando a la base de datos...")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # Obtener conteo antes
    print("\n📊 Registros encontrados:")
    
    cursor.execute("SELECT COUNT(*) FROM ventas_ventadetalle")
    detalles_count = cursor.fetchone()[0]
    print(f"   - Detalles de ventas: {detalles_count}")
    
    cursor.execute("SELECT COUNT(*) FROM ventas_venta")
    ventas_count = cursor.fetchone()[0]
    print(f"   - Ventas: {ventas_count}")
    
    cursor.execute("SELECT COUNT(*) FROM tesoreria_movimientocuentacorrientecliente")
    movimientos_cc_count = cursor.fetchone()[0]
    print(f"   - Movimientos cuenta corriente: {movimientos_cc_count}")
    
    cursor.execute("SELECT COUNT(*) FROM caja_movimientocaja")
    movimientos_caja_count = cursor.fetchone()[0]
    print(f"   - Movimientos de caja: {movimientos_caja_count}")
    
    cursor.execute("SELECT COUNT(*) FROM caja_aperturacaja")
    aperturas_count = cursor.fetchone()[0]
    print(f"   - Aperturas de caja: {aperturas_count}")
    
    # Confirmar
    respuesta = input("\n⚠️  ¿Deseas eliminar estos datos? (escribe 'SI' para confirmar): ")
    
    if respuesta != 'SI':
        print("❌ Operación cancelada")
        exit(0)
    
    print("\n🗑️  Eliminando datos...")
    
    # Eliminar en orden correcto (respetando foreign keys)
    cursor.execute("DELETE FROM ventas_ventadetalle")
    print(f"   ✓ {detalles_count} detalles de ventas eliminados")
    
    cursor.execute("DELETE FROM tesoreria_movimientocuentacorrientecliente")
    print(f"   ✓ {movimientos_cc_count} movimientos de cuenta corriente eliminados")
    
    cursor.execute("DELETE FROM caja_movimientocaja")
    print(f"   ✓ {movimientos_caja_count} movimientos de caja eliminados")
    
    cursor.execute("DELETE FROM caja_aperturacaja")
    print(f"   ✓ {aperturas_count} aperturas de caja eliminadas")
    
    cursor.execute("DELETE FROM ventas_venta")
    print(f"   ✓ {ventas_count} ventas eliminadas")
    
    # Commit
    conn.commit()
    
    print("\n✅ Limpieza completada exitosamente!")
    print("   Ahora puedes ejecutar:")
    print("   1. python manage.py makemigrations")
    print("   2. python manage.py migrate")
    
except Exception as e:
    print(f"\n❌ Error: {str(e)}")
    conn.rollback()
finally:
    conn.close()
