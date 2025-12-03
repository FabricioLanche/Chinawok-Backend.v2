"""
Configuración del generador de datos
"""
import os
from dotenv import load_dotenv

# Cargar variables de entorno desde .env en la raíz del proyecto
# Buscar el archivo .env dos niveles arriba (en la raíz)
env_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
load_dotenv(dotenv_path=env_path)


class Config:
    """Configuración global del generador de datos"""
    
    # Directorio de salida
    OUTPUT_DIR = "dynamodb_data"
    
    # Cantidad de registros a generar
    NUM_LOCALES = 100
    NUM_USUARIOS = 5000
    NUM_EMPLEADOS_POR_LOCAL = 5  # Promedio de empleados por local
    NUM_COMBOS = 500
    NUM_PEDIDOS = 10000
    NUM_OFERTAS = 500
    NUM_RESENAS = 5000
    
    # Cantidades de registros
    NUM_PRODUCTOS_POR_LOCAL = 50
    NUM_EMPLEADOS = 500
    NUM_COMBOS_POR_LOCAL = 5
    NUM_OFERTAS_POR_LOCAL = 5
    NUM_RESENAS = 1000
    
    # Porcentajes
    PORCENTAJE_USUARIOS_CON_TARJETA = 0.7
    PORCENTAJE_PRODUCTOS_VEGETARIANOS = 0.3
    PORCENTAJE_PRODUCTOS_PICANTES = 0.3
    PORCENTAJE_PEDIDOS_CON_RESENA = 0.5  # 50% de pedidos completados tendrán reseña
    
    # Rangos de precios
    PRECIO_MIN_PRODUCTO = 10.0
    PRECIO_MAX_PRODUCTO = 50.0
    PRECIO_MIN_DELIVERY = 3.0
    PRECIO_MAX_DELIVERY = 8.0
    
    # Rangos de salarios
    SALARIO_MIN = 1200.0
    SALARIO_MAX = 3000.0
    
        # Admin credentials (Usuario único con rol Admin - administrador general de la plataforma)
    ADMIN_NOMBRE = os.getenv('ADMIN_NOMBRE', 'Administrador')
    ADMIN_APELLIDO = os.getenv('ADMIN_APELLIDO', 'General')
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@chinawok.pe')
    ADMIN_TELEFONO = os.getenv('ADMIN_TELEFONO', '+51999999999')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'AdminChinaWok2024!')
    
    # Estados de pedidos (DEBEN coincidir con schema exactamente)
    ESTADOS_PEDIDO = ["procesando", "cocinando", "empacando", "enviando", "recibido"]
    
    # Roles de empleados (DEBEN coincidir con schema: Primera letra mayúscula)
    ROLES_EMPLEADO = ["Repartidor", "Cocinero", "Despachador"]
    
    # Categorías de productos (DEBEN coincidir con schema exactamente)
    CATEGORIAS_PRODUCTO = [
        "Arroces",
        "Tallarines",
        "Pollo al wok",
        "Carne de res",
        "Cerdo",
        "Mariscos",
        "Entradas",
        "Guarniciones",
        "Sopas",
        "Combos",
        "Bebidas",
        "Postres"
    ]
    
    # Roles de usuarios (DEBEN coincidir con schema: Primera letra mayúscula)
    # Cliente: usuarios que realizan pedidos (pueden o no tener info bancaria)
    # Gerente: encargado de un local específico (multi-tenancy) - se genera automáticamente con cada local
    # Admin: administrador general de toda la plataforma (SOLO 1, se crea desde .env)
    ROLES_USUARIO = ["Cliente", "Gerente", "Admin"]

    @staticmethod
    def crear_directorio_salida():
        """Crea el directorio de salida si no existe"""
        import os
        if not os.path.exists(Config.OUTPUT_DIR):
            os.makedirs(Config.OUTPUT_DIR)
            print(f"📁 Directorio '{Config.OUTPUT_DIR}/' creado")
        else:
            print(f"📁 Usando directorio existente: '{Config.OUTPUT_DIR}/'")
