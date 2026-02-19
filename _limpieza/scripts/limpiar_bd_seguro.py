import sqlite3
from pathlib import Path

def limpiar_bd():
    db_path = Path('db.sqlite3')
    if not db_path.exists():
        print("❌ No se encontró la base de datos.")
        return

    # Tablas a limpiar (en orden correcto para respetar foreign keys)
    tablas = [
        'ventas_ventadetalle',
        'tesoreria_movimientocuentacorrientecliente',
        'caja_movimientocaja',
        'caja_aperturacaja',
        'ventas_venta'
    ]

    try:
        conn = sqlite3.connect('db.sqlite3')
        cursor = conn.cursor()
        
        # Desactivar temporalmente las restricciones de clave foránea
        cursor.execute("PRAGMA foreign_keys = OFF")
        
        # Contar registros antes
        print("📊 Registros a eliminar:")
        for tabla in tablas:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {tabla}")
                count = cursor.fetchone()[0]
                print(f"   - {tabla}: {count} registros")
            except sqlite3.OperationalError:
                print(f"   - {tabla}: No existe, omitiendo...")
        
        # Confirmar
        confirmacion = input("\n⚠️  ¿Deseas continuar con la limpieza? (s/n): ")
        if confirmacion.lower() != 's':
            print("❌ Operación cancelada")
            return
            
        # Limpiar tablas
        print("\n🗑️  Limpiando datos...")
        for tabla in tablas:
            try:
                cursor.execute(f"DELETE FROM {tabla}")
                # Resetear secuencia si existe
                cursor.execute(f"DELETE FROM sqlite_sequence WHERE name = '{tabla}'")
                print(f"   ✓ {tabla} limpiada")
            except sqlite3.OperationalError as e:
                print(f"   - {tabla}: Error al limpiar - {str(e)}")
                
        conn.commit()
        print("\n✅ Base de datos limpiada exitosamente!")
        print("\nAhora puedes ejecutar las migraciones con:")
        print("1. python manage.py makemigrations")
        print("2. python manage.py migrate")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    print("🔍 Analizando base de datos...")
    limpiar_bd()
