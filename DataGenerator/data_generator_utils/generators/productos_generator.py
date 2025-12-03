"""
Generador de Productos
"""
import random
from ..config import Config
from ..helpers import Helpers

class ProductosGenerator:
    """Generador de datos para la tabla Productos"""
    
    PRODUCTOS_BASE = {
        "Arroces": [
            "Arroz Chaufa de Pollo", "Arroz Chaufa de Carne", "Arroz Chaufa Mixto",
            "Arroz Chaufa de Mariscos", "Arroz Chaufa Especial"
        ],
        "Tallarines": [
            "Tallarín Saltado de Pollo", "Tallarín Saltado de Carne",
            "Tallarín Saltado Mixto", "Tallarín con Mariscos"
        ],
        "Pollo al wok": [
            "Pollo con Tamarindo", "Pollo Chi Jau Kay", "Pollo Tipakay",
            "Pollo con Verduras"
        ],
        "Carne de res": [
            "Carne Mongoliana", "Lomo Saltado", "Carne con Ostión",
            "Carne con Verduras al Wok"
        ],
        "Cerdo": [
            "Cerdo Agridulce", "Chancho con Tamarindo", "Cerdo al Sillao"
        ],
        "Mariscos": [
            "Chicharrón de Calamar", "Camarones al Tamarindo",
            "Arroz con Mariscos", "Chijaukai de Mariscos"
        ],
        "Entradas": [
            "Wantán Frito", "Empanaditas Chinas", "Siu Mai",
            "Rollitos Primavera"
        ],
        "Guarniciones": [
            "Arroz Blanco", "Wantanes Fritos", "Chapsui de Verduras"
        ],
        "Sopas": [
            "Sopa Wantán", "Sopa de Gallina China", "Sopa Min"
        ],
        "Bebidas": [
            "Chicha Morada 1L", "Inca Kola 1.5L", "Agua Mineral 625ml",
            "Té Helado 500ml"
        ],
        "Postres": [
            "Helado de Lúcuma", "Picarones", "Mazamorra Morada"
        ]
    }
    
    @classmethod
    def generar_productos(cls, locales_ids):
        """Genera productos únicos para cada local (multi-tenancy)"""
        productos = []
        productos_por_local = {}
        
        # Crear lista plana de todos los productos disponibles
        todos_los_productos = []
        for categoria, items in cls.PRODUCTOS_BASE.items():
            for nombre in items:
                todos_los_productos.append({
                    "nombre": nombre,
                    "categoria": categoria
                })
        
        total_productos_disponibles = len(todos_los_productos)
        print(f"  ℹ️  Total de productos únicos disponibles: {total_productos_disponibles}")
        
        productos_duplicados = 0
        
        for local_id in locales_ids:
            # Cada local tiene su propia lista de productos
            productos_por_local[local_id] = []
            productos_usados = set()  # Para detectar duplicados
            
            # Cada local tiene entre 30-50 productos (limitado por productos disponibles)
            num_productos_local = min(random.randint(30, 50), total_productos_disponibles)
            
            # Seleccionar productos aleatorios sin repetir
            productos_seleccionados = random.sample(todos_los_productos, num_productos_local)
            
            for prod_info in productos_seleccionados:
                nombre = prod_info["nombre"]
                categoria = prod_info["categoria"]
                
                # Verificación de duplicados (no debería ocurrir con sample, pero por seguridad)
                if nombre in productos_usados:
                    productos_duplicados += 1
                    print(f"  ⚠️  Producto duplicado detectado: {nombre} en local {local_id}")
                    continue
                
                productos_usados.add(nombre)
                
                producto = cls._crear_producto(local_id, nombre, categoria)
                productos.append(producto)
                productos_por_local[local_id].append(nombre)
        
        print(f"  ✅ {len(productos)} productos generados")
        print(f"  ℹ️  Distribuidos en {len(locales_ids)} locales")
        
        if productos_duplicados > 0:
            print(f"  ⚠️  Duplicados evitados: {productos_duplicados}")
        
        # Validar que no hay duplicados en el resultado final
        claves_unicas = set()
        duplicados_finales = 0
        for prod in productos:
            clave = (prod["local_id"], prod["nombre"])
            if clave in claves_unicas:
                duplicados_finales += 1
                print(f"  🔴 ERROR: Duplicado final detectado - Local: {prod['local_id']}, Producto: {prod['nombre']}")
            claves_unicas.add(clave)
        
        if duplicados_finales > 0:
            print(f"  🔴 TOTAL DE DUPLICADOS EN RESULTADO FINAL: {duplicados_finales}")
        else:
            print(f"  ✅ Validación: No hay duplicados en el resultado final")
        
        return productos, productos_por_local
    
    @classmethod
    def _crear_producto(cls, local_id, nombre_producto, categoria):
        """Crea un producto individual con datos aleatorios"""
        # Solo campos permitidos por el schema de validación
        return {
            "local_id": local_id,
            "nombre": nombre_producto,
            "precio": round(random.uniform(Config.PRECIO_MIN_PRODUCTO, Config.PRECIO_MAX_PRODUCTO), 2),
            "descripcion": f"{nombre_producto} preparado al estilo China Wok",
            "categoria": categoria,
            "stock": random.randint(10, 100)
        }
