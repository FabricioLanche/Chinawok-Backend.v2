import json
import os
from data_generator_utils.config import Config
from data_generator_utils.generators import (
    LocalesGenerator,
    UsuariosGenerator,
    ProductosGenerator,
    EmpleadosGenerator,
    CombosGenerator,
    PedidosGenerator,
    OfertasGenerator,
    ResenasGenerator
)

# ============================================================================
# GENERADOR DE DATOS PARA DYNAMODB - CHINA WOK
# ============================================================================

def guardar_json(filename, data):
    """Guarda datos en formato JSON"""
    out_dir = os.path.join(os.path.dirname(__file__), "dynamodb_data")
    os.makedirs(out_dir, exist_ok=True)
    filepath = os.path.join(out_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  ✅ {filename} generado y sobrescrito en {filepath} ({len(data)} registros)")


def main():
    """Función principal para generar todos los datos"""
    print("=" * 80)
    print("🍜 GENERADOR DE DATOS - CHINA WOK")
    print("=" * 80)
    
    # Crear directorio de salida
    Config.crear_directorio_salida()
    
    # 1. Generar Locales
    print("\n📍 Generando Locales...")
    locales, locales_ids = LocalesGenerator.generar_locales()
    guardar_json("locales.json", locales)
    
    # 2. Generar Usuarios (pasando datos de locales para crear gerentes)
    print("\n👥 Generando Usuarios...")
    usuarios, usuarios_ids = UsuariosGenerator.generar_usuarios(locales_data=locales)
    guardar_json("usuarios.json", usuarios)
    
    # 3. Generar Productos
    print("\n🍜 Generando Productos...")
    productos, productos_por_local = ProductosGenerator.generar_productos(locales_ids)
    guardar_json("productos.json", productos)
    
    # 4. Generar Empleados
    print("\n👨‍🍳 Generando Empleados...")
    empleados, empleados_por_local = EmpleadosGenerator.generar_empleados(locales_ids)
    guardar_json("empleados.json", empleados)
    
    # 5. Generar Combos
    print("\n🎁 Generando Combos...")
    combos, combos_por_local = CombosGenerator.generar_combos(
        locales_ids, productos_por_local, productos
    )
    guardar_json("combos.json", combos)
    
    # 6. Generar Pedidos
    print("\n📦 Generando Pedidos...")
    pedidos, pedidos_ids = PedidosGenerator.generar_pedidos(
        locales_ids, usuarios, productos, productos_por_local, empleados_por_local, combos_por_local
    )
    guardar_json("pedidos.json", pedidos)
    
    # 7. Generar Ofertas
    print("\n🎉 Generando Ofertas...")
    ofertas = OfertasGenerator.generar_ofertas(
        locales_ids, productos_por_local, combos_por_local
    )
    guardar_json("ofertas.json", ofertas)
    
    # 8. Generar Reseñas
    print("\n⭐ Generando Reseñas...")
    resenas = ResenasGenerator.generar_resenas(pedidos, empleados_por_local)
    guardar_json("resenas.json", resenas)

    # 9. Generar Conexiones
    print("\n🌐 Generando Conexiones...")
    conexiones = []
    guardar_json("conexiones.json", conexiones)
    
    # Resumen final
    print("\n" + "=" * 80)
    print("✅ GENERACIÓN COMPLETADA")
    print("=" * 80)
    print(f"📊 Resumen:")
    print(f"   • Locales: {len(locales)}")
    print(f"   • Usuarios: {len(usuarios)}")
    print(f"   • Productos: {len(productos)}")
    print(f"   • Empleados: {len(empleados)}")
    print(f"   • Combos: {len(combos)}")
    print(f"   • Pedidos: {len(pedidos)}")
    print(f"   • Ofertas: {len(ofertas)}")
    print(f"   • Reseñas: {len(resenas)}")
    print(f"\n📁 Archivos generados en: {Config.OUTPUT_DIR}/")
    print("=" * 80)


if __name__ == "__main__":
    main()