"""
Utilidades para generación de datos
"""
import random
import string

def generar_email(nombre, apellido):
    """Genera un email a partir de nombre y apellido"""
    nombre_limpio = nombre.lower().replace(" ", "")
    apellido_limpio = apellido.lower().replace(" ", "")
    numero = random.randint(1, 9999)
    dominios = ["gmail.com", "hotmail.com", "outlook.com", "yahoo.com"]
    dominio = random.choice(dominios)
    
    return f"{nombre_limpio}.{apellido_limpio}{numero}@{dominio}"


def generar_password():
    """Genera una contraseña aleatoria de 8-12 caracteres"""
    longitud = random.randint(8, 12)
    caracteres = string.ascii_letters + string.digits + "!@#$%"
    password = ''.join(random.choice(caracteres) for _ in range(longitud))
    
    # Asegurar que tenga al menos una mayúscula, minúscula y número
    if not any(c.isupper() for c in password):
        password = password[:-1] + random.choice(string.ascii_uppercase)
    if not any(c.islower() for c in password):
        password = password[:-1] + random.choice(string.ascii_lowercase)
    if not any(c.isdigit() for c in password):
        password = password[:-1] + random.choice(string.digits)
    
    return password


def generar_tarjeta():
    """Genera información bancaria ficticia"""
    # Generar número de tarjeta (16 dígitos)
    numero_tarjeta = ''.join([str(random.randint(0, 9)) for _ in range(16)])
    
    # Generar CVV (3 dígitos)
    cvv = ''.join([str(random.randint(0, 9)) for _ in range(3)])
    
    # Generar fecha de vencimiento (formato MM/YY)
    mes = f"{random.randint(1, 12):02d}"
    anio = f"{random.randint(25, 30):02d}"  # 2025-2030
    fecha_vencimiento = f"{mes}/{anio}"
    
    # Dirección de facturación
    direcciones = [
        "Av. Javier Prado Este 456, San Isidro",
        "Av. Arequipa 1234, Miraflores",
        "Calle Los Olivos 789, San Borja",
        "Av. Larco 567, Miraflores",
        "Calle Las Begonias 234, San Isidro"
    ]
    
    return {
        "numero_tarjeta": numero_tarjeta,
        "cvv": cvv,
        "fecha_vencimiento": fecha_vencimiento,
        "direccion_facturacion": random.choice(direcciones)
    }


def generar_telefono_pe():
    """Genera un número de teléfono peruano"""
    return f"+51-{random.randint(900000000, 999999999)}"


def generar_dni():
    """Genera un DNI peruano (8 dígitos)"""
    return f"{random.randint(10000000, 99999999)}"
