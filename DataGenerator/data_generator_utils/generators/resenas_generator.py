"""
Generador de Reseñas
"""
import random
from ..config import Config
from ..sample_data import SampleData
from ..helpers import Helpers

class ResenasGenerator:
    """Generador de datos para la tabla Reseñas"""
    
    @classmethod
    def generar_resenas(cls, pedidos, empleados_por_local):
        """Genera reseñas solo para pedidos completados que tengan los 3 empleados"""
        resenas = []
        pedidos_resenados = set()  # Rastrear pedidos que ya tienen reseña
        
        # Filtrar solo pedidos en estado "recibido"
        pedidos_completados = [p for p in pedidos if p["estado"] == "recibido"]
        
        # Barajar para tener variedad
        random.shuffle(pedidos_completados)
        
        # Intentar generar hasta NUM_RESENAS
        for pedido in pedidos_completados:
            if len(resenas) >= Config.NUM_RESENAS:
                break
            
            # IMPORTANTE: Solo una reseña por pedido
            if pedido["pedido_id"] in pedidos_resenados:
                continue
                
            resena = cls._crear_resena(pedido)
            if resena:
                resenas.append(resena)
                pedidos_resenados.add(pedido["pedido_id"])
        
        print(f"  ✅ {len(resenas)} reseñas generadas de {len(pedidos_completados)} pedidos completados")
        print(f"  ℹ️  Garantizado: 1 reseña por pedido único")
        return resenas
    
    @classmethod
    def _crear_resena(cls, pedido):
        """Crea una reseña extrayendo los 3 DNIs del historial del pedido"""
        # Extraer los DNIs directamente del historial
        cocinero_dni = None
        repartidor_dni = None
        despachador_dni = None
        
        for entrada in pedido.get("historial_estados", []):
            empleado = entrada.get("empleado")
            if empleado and empleado.get("dni") and empleado.get("rol"):
                rol = empleado["rol"].lower()
                
                if rol == "cocinero":
                    cocinero_dni = empleado["dni"]
                elif rol == "repartidor":
                    repartidor_dni = empleado["dni"]
                elif rol == "despachador":
                    despachador_dni = empleado["dni"]
        
        # Si faltan empleados, saltar este pedido
        if not all([cocinero_dni, repartidor_dni, despachador_dni]):
            return None
        
        # Generar reseña
        resena_id = Helpers.generar_uuid()
        calificacion = random.uniform(1, 5)
        
        if calificacion >= 4:
            resena_texto = random.choice(SampleData.RESENAS_POSITIVAS)
        elif calificacion >= 3:
            resena_texto = random.choice(SampleData.RESENAS_NEUTRAS)
        else:
            resena_texto = random.choice(SampleData.RESENAS_NEGATIVAS)
        
        return {
            "local_id": pedido["local_id"],
            "cocinero_dni": cocinero_dni,
            "repartidor_dni": repartidor_dni,
            "despachador_dni": despachador_dni,
            "resena_id": resena_id,
            "pedido_id": pedido["pedido_id"],
            "resena": resena_texto,
            "calificacion": round(calificacion, 2)
        }
