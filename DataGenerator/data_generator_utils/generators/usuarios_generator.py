"""
Generador de Usuarios
"""
import random
from ..config import Config
from ..sample_data import SampleData

class UsuariosGenerator:
    """Generador de datos para la tabla Usuarios"""
    
    @classmethod
    def generar_usuarios(cls, locales_data=None):
        """Genera 1 Admin único (desde .env) + Gerentes (uno por local) + Clientes"""
        usuarios = []
        usuarios_ids = []
        
        # Crear UN ÚNICO Admin (desde variables de entorno)
        admin = cls._crear_admin_unico()
        usuarios.append(admin)
        usuarios_ids.append(admin["correo"])
        
        # Crear Gerentes (uno por cada local) - IMPORTANTE: pasar locales_data
        num_gerentes = 0
        if locales_data:
            for local in locales_data:
                gerente_data = local["gerente"]
                local_id = local["local_id"]  # Obtener local_id del local
                gerente = cls._crear_gerente_desde_local(gerente_data, local_id)
                usuarios.append(gerente)
                usuarios_ids.append(gerente["correo"])
                num_gerentes += 1
        
        # Crear clientes
        for i in range(Config.NUM_USUARIOS):
            usuario = cls._crear_cliente(i)
            usuarios.append(usuario)
            usuarios_ids.append(usuario["correo"])
        
        print(f"  ✅ 1 Admin + {num_gerentes} Gerentes + {Config.NUM_USUARIOS} Clientes generados")
        print(f"  ℹ️  Admin: {admin['correo']}")
        if num_gerentes > 0:
            print(f"  ℹ️  Gerentes: {num_gerentes} (uno por local)")
        return usuarios, usuarios_ids
    
    @classmethod
    def _crear_admin_unico(cls):
        """Crea el único usuario administrador de toda la plataforma (desde .env)"""
        return {
            "nombre": Config.ADMIN_NOMBRE,
            "apellido": Config.ADMIN_APELLIDO,
            "correo": Config.ADMIN_EMAIL,
            "contrasena": Config.ADMIN_PASSWORD,
            "role": "Admin",
            "historial_pedidos": []
        }
    
    @classmethod
    def _crear_gerente_desde_local(cls, gerente_data, local_id):
        """Crea un usuario Gerente a partir de los datos del local"""
        return {
            "nombre": gerente_data["nombre"].split()[0],  # Primer nombre
            "apellido": " ".join(gerente_data["nombre"].split()[1:]),  # Apellidos
            "correo": gerente_data["correo"],
            "contrasena": gerente_data["contrasena"],
            "role": "Gerente",
            "local_id": local_id,  # Asociar gerente con su local
            "historial_pedidos": []
        }
    
    @classmethod
    def _crear_cliente(cls, index):
        """Crea un cliente individual"""
        nombre = random.choice(SampleData.NOMBRES)
        apellido = random.choice(SampleData.APELLIDOS)
        
        usuario = {
            "nombre": nombre,
            "apellido": apellido,
            "correo": f"{nombre.lower()}.{apellido.lower()}{index}@email.com",
            "telefono": f"+51{random.randint(900000000, 999999999)}",
            "contrasena": f"cliente{index:04d}",
            "role": "Cliente",  # Primera letra mayúscula
            "historial_pedidos": []  # Array vacío por defecto
        }
        
        # 70% de los clientes tienen información bancaria COMPLETA
        if random.random() > 0.3:
            usuario["informacion_bancaria"] = {
                "numero_tarjeta": ''.join([str(random.randint(0, 9)) for _ in range(16)]),
                "cvv": ''.join([str(random.randint(0, 9)) for _ in range(3)]),
                "fecha_vencimiento": f"{random.randint(1, 12):02d}/{random.randint(25, 30):02d}",
                "direccion_delivery": random.choice(SampleData.DIRECCIONES_LIMA)
            }
        
        return usuario
