"""
Funciones auxiliares para el generador
"""
import uuid
import random
from datetime import datetime


class Helpers:
    """Funciones auxiliares para generación de datos"""
    
    @staticmethod
    def generar_uuid():
        """Genera un UUID único"""
        return str(uuid.uuid4())
    
    @staticmethod
    def generar_timestamp():
        """Genera timestamp ISO 8601"""
        return datetime.now().isoformat()
    
    @staticmethod
    def generar_email(nombre, apellido, suffix=""):
        """Genera email único"""
        return f"{nombre.lower()}.{apellido.lower()}{suffix}@email.com"
    
    @staticmethod
    def generar_telefono():
        """Genera número de teléfono peruano"""
        return f"+51-{random.randint(900000000, 999999999)}"
    
    @staticmethod
    def generar_dni():
        """Genera DNI de 8 dígitos"""
        return ''.join([str(random.randint(0, 9)) for _ in range(8)])
    
    @staticmethod
    def generar_dni_peruano():
        """Genera un DNI peruano válido (8 dígitos numéricos)"""
        # DNI peruano: 8 dígitos, rango típico 10000000-99999999
        return str(random.randint(10000000, 99999999))
    
    @staticmethod
    def generar_tarjeta():
        """Genera número de tarjeta de 16 dígitos"""
        return ''.join([str(random.randint(0, 9)) for _ in range(16)])
    
    @staticmethod
    def generar_cvv():
        """Genera CVV de 3 dígitos"""
        return ''.join([str(random.randint(0, 9)) for _ in range(3)])
    
    @staticmethod
    def generar_fecha_vencimiento():
        """Genera fecha de vencimiento MM/YY"""
        return f"{random.randint(1, 12):02d}/{random.randint(25, 30):02d}"
    
    @staticmethod
    def generar_direccion(calles, distritos):
        """Genera una dirección completa"""
        return {
            "calle": random.choice(calles),
            "numero": str(random.randint(100, 9999)),
            "distrito": random.choice(distritos),
            "ciudad": "Lima",
            "codigo_postal": f"150{random.randint(10, 99)}"
        }
    
    @staticmethod
    def generar_direccion_string(calles, distritos):
        """Genera una dirección como string"""
        return f"{random.choice(calles)} {random.randint(100, 999)}, {random.choice(distritos)}, Lima"
