"""
Generador de Combos
"""
import random
from ..config import Config
from ..helpers import Helpers


class CombosGenerator:
    """Generador de datos para la tabla Combos"""
    
    COMBOS_BASE = [
        {"nombre": "Combo Personal", "descripcion": "Plato principal + bebida", "num_productos": 2},
        {"nombre": "Combo Pareja", "descripcion": "2 platos principales + 2 bebidas", "num_productos": 4},
        {"nombre": "Combo Familiar", "descripcion": "3 platos + entrada + 3 bebidas", "num_productos": 7},
        {"nombre": "Combo Ejecutivo", "descripcion": "Plato principal + sopa + bebida", "num_productos": 3},
        {"nombre": "Combo Premium", "descripcion": "2 platos especiales + entrada + 2 bebidas + postre", "num_productos": 6}
    ]
    
    @classmethod
    def generar_combos(cls, locales_ids, productos_por_local, productos):
        """Genera combos usando SOLO productos del mismo local (multi-tenancy)"""
        combos = []
        combos_por_local = {local_id: [] for local_id in locales_ids}
        
        # Crear diccionario de productos por nombre para búsqueda rápida
        productos_dict = {p["nombre"]: p for p in productos}
        
        for _ in range(Config.NUM_COMBOS):
            local_id = random.choice(locales_ids)
            
            # IMPORTANTE: Solo usar productos DEL LOCAL ESPECÍFICO
            productos_del_local = productos_por_local.get(local_id, [])
            
            if len(productos_del_local) < 2:
                # Si el local no tiene suficientes productos, saltar
                continue
            
            combo = cls._crear_combo(
                local_id, 
                productos_del_local,  # Solo productos de este local
                productos_dict
            )
            
            combos.append(combo)
            combos_por_local[local_id].append(combo["combo_id"])
        
        print(f"  ✅ {len(combos)} combos generados")
        print(f"  ℹ️  Distribuidos en {len(locales_ids)} locales")
        return combos, combos_por_local
    
    @classmethod
    def _crear_combo(cls, local_id, productos_disponibles, productos_dict):
        """Crea un combo usando solo productos del local especificado"""
        combo_id = Helpers.generar_uuid()
        
        # Seleccionar 2-4 productos DEL LOCAL
        num_productos = random.randint(2, min(4, len(productos_disponibles)))
        productos_seleccionados = random.sample(productos_disponibles, num_productos)
        
        # Calcular precio base sumando precios de productos
        precio_base = sum([
            productos_dict[nombre]["precio"] 
            for nombre in productos_seleccionados 
            if nombre in productos_dict
        ])
        
        # Aplicar descuento (15-30%)
        descuento_pct = random.uniform(15, 30)
        precio_combo = precio_base * (1 - descuento_pct / 100)
        
        return {
            "local_id": local_id,
            "combo_id": combo_id,
            "nombre": f"Combo {combo_id[:8]}",
            "productos_nombres": productos_seleccionados,
            "precio": round(precio_combo, 2),
            "disponible": random.choice([True, False])
        }
