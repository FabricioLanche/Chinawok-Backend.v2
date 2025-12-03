"""
Generador de Empleados
"""
import random
from ..config import Config
from ..sample_data import SampleData
from ..helpers import Helpers

class EmpleadosGenerator:
    """Generador de datos para la tabla Empleados"""
    
    # Set global para rastrear DNIs ya generados
    _dnis_generados = set()
    
    @classmethod
    def generar_empleados(cls, locales_ids):
        """Genera empleados ÚNICOS para cada local (multi-tenancy)"""
        empleados = []
        empleados_por_local = {
            local_id: {
                "repartidor": [],
                "cocinero": [],
                "despachador": [],
                "info_empleados": {}
            }
            for local_id in locales_ids
        }
        
        # Limpiar DNIs generados al inicio
        cls._dnis_generados.clear()
        
        for local_id in locales_ids:
            # Garantizar mínimo 2 empleados de cada tipo (6 total)
            # Primero crear los empleados obligatorios
            roles_requeridos = ["Repartidor", "Repartidor", "Cocinero", "Cocinero", "Despachador", "Despachador"]
            
            for role in roles_requeridos:
                empleado = cls._crear_empleado(local_id, role)
                empleados.append(empleado)
                
                # Guardar DNI en lista por rol ESPECÍFICO DEL LOCAL
                empleados_por_local[local_id][empleado["role"].lower()].append(empleado["dni"])
                
                # Guardar información completa del empleado ESPECÍFICO DEL LOCAL
                empleados_por_local[local_id]["info_empleados"][empleado["dni"]] = {
                    "nombre": empleado["nombre"],
                    "apellido": empleado["apellido"],
                    "calificacion_prom": empleado.get("calificacion_prom")
                }
            
            # Agregar 0-3 empleados adicionales aleatorios
            num_empleados_extra = random.randint(0, 3)
            for _ in range(num_empleados_extra):
                empleado = cls._crear_empleado(local_id)
                empleados.append(empleado)
                
                # Guardar DNI en lista por rol ESPECÍFICO DEL LOCAL
                empleados_por_local[local_id][empleado["role"].lower()].append(empleado["dni"])
                
                # Guardar información completa del empleado ESPECÍFICO DEL LOCAL
                empleados_por_local[local_id]["info_empleados"][empleado["dni"]] = {
                    "nombre": empleado["nombre"],
                    "apellido": empleado["apellido"],
                    "calificacion_prom": empleado.get("calificacion_prom")
                }
        
        print(f"  ✅ {len(empleados)} empleados generados")
        print(f"  ℹ️  Distribuidos en {len(locales_ids)} locales (multi-tenancy)")
        print(f"  ℹ️  DNIs peruanos únicos: {len(cls._dnis_generados)} generados")
        print(f"  ℹ️  Campo 'ocupado' = False por defecto (se actualizará en tiempo real)")
        return empleados, empleados_por_local
    
    @classmethod
    def _crear_empleado(cls, local_id, role=None):
        """Crea un empleado individual con rol específico u opcional"""
        nombre = random.choice(SampleData.NOMBRES)
        apellido = random.choice(SampleData.APELLIDOS)
        
        # Generar DNI peruano único (8 dígitos)
        dni = cls._generar_dni_unico()
        
        # Si no se especifica role, elegir uno aleatorio
        if role is None:
            role = random.choice(["Repartidor", "Cocinero", "Despachador"])
        
        return {
            "local_id": local_id,
            "dni": dni,
            "nombre": nombre,
            "apellido": apellido,
            "calificacion_prom": round(random.uniform(3.5, 5.0), 2),
            "sueldo": round(random.uniform(1200, 3000), 2),
            "role": role,
            "ocupado": False
        }
    
    @classmethod
    def _generar_dni_unico(cls):
        """Genera un DNI peruano único (8 dígitos numéricos)"""
        max_intentos = 1000
        intentos = 0
        
        while intentos < max_intentos:
            dni = Helpers.generar_dni_peruano()
            
            if dni not in cls._dnis_generados:
                cls._dnis_generados.add(dni)
                return dni
            
            intentos += 1
        
        # Si después de muchos intentos no se genera único, agregar sufijo
        dni_base = Helpers.generar_dni_peruano()
        print(f"  ⚠️  Colisión de DNI detectada después de {max_intentos} intentos")
        return dni_base
