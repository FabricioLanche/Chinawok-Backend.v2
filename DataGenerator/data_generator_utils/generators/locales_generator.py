"""
Generador de Locales
"""
import random
from ..config import Config
from ..sample_data import SampleData
from ..helpers import Helpers

class LocalesGenerator:
    """Generador de datos para la tabla Locales"""
    
    @classmethod
    def generar_locales(cls):
        """Genera locales, cada uno con su gerente único (multi-tenancy)"""
        locales = []
        locales_ids = []
        
        for i in range(Config.NUM_LOCALES):
            local = cls._crear_local(i)
            locales.append(local)
            locales_ids.append(local["local_id"])
        
        print(f"  ✅ {Config.NUM_LOCALES} locales generados")
        print(f"  👤 Cada local tiene su gerente único (multi-tenancy)")
        return locales, locales_ids
    
    @classmethod
    def _crear_local(cls, index):
        """Crea un local individual con su gerente único"""
        local_id = Helpers.generar_uuid()
        direccion = random.choice(SampleData.DIRECCIONES_LIMA)
        
        # Cada local tiene su propio gerente (multi-tenancy)
        nombre_gerente = random.choice(SampleData.NOMBRES)
        apellido_gerente = random.choice(SampleData.APELLIDOS)
        
        return {
            "local_id": local_id,
            "direccion": direccion,
            "telefono": f"+51{random.randint(900000000, 999999999)}",
            "hora_apertura": "08:00",
            "hora_finalizacion": "22:00",
            "gerente": {
                "nombre": f"{nombre_gerente} {apellido_gerente}",
                "correo": f"gerente.local{index + 1:03d}@chinawok.pe",
                "contrasena": f"Gerente{index + 1:03d}!Pass"
            }
        }
