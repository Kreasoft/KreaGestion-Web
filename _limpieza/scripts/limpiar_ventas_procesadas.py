"""
Script para limpiar la tabla caja_ventaprocesada
"""
import sqlite3
from pathlib import Path

def limpiar_ventas_procesadas():
    db_path = Path('db.sqlite3')
    if not db_path.exists():
        print("❌ No se encontró la base de datos.")
        return

    try:
        conn = sqlite3.connect('db.sqlite3')
        cursor = conn.cursor()
        
        # Contar registros antes
        cursor.execute("SELECT COUNT(*) FROM caja_ventaprocesada")
        count = cursor.fetchone()[0]
        print(f"📊 Registros en caja_ventaprocesada: {count}")
        
        # Mostrar advertencia
        print("\n⚠️  ADVERTENCIA: Se eliminarán TODOS los registros de ventas procesadas.")
        print("   Esto es necesario para continuar con la migración.")
        
        confirmacion = input("\n¿Deseas continuar? (s/n): ")
        if confirmacion.lower() != 's':
            print("❌ Operación cancelada")
            return
            
        # Limpiar tabla
        print("\n🗑️  Limpiando registros...")
        cursor.execute("DELETE FROM caja_ventaprocesada")
        conn.commit()
        
        # Verificar
        cursor.execute("SELECT COUNT(*) FROM caja_ventaprocesada")
        new_count = cursor.fetchone()[0]
        
        print(f"\n✅ Tabla limpiada exitosamente. Registros restantes: {new_count}")
        print("\nAhora puedes ejecutar: python manage.py migrate")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    print("🔍 Iniciando limpieza de ventas procesadas...")
    limpiar_ventas_procesadas()
