import jwt
import os
from datetime import datetime, timedelta
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _mask_token(t: str) -> str:
    """Enmascara el token para logging seguro (no exponer el token completo)."""
    if not t:
        return "<empty>"
    try:
        if len(t) <= 12:
            return t[:3] + "..." + t[-3:]
        return t[:6] + "..." + t[-6:]
    except Exception:
        return "<invalid-token>"

# Solo necesitamos JWT_SECRET, no tablas de DynamoDB
JWT_SECRET = os.getenv("JWT_SECRET", "tu-clave-secreta-super-segura-cambiar-en-produccion")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))

def generar_token(correo, role, nombre):
    """
    Genera un JWT como Spring Boot
    """
    # Usar timestamps enteros en lugar de objetos datetime para compatibilidad consistente
    now = datetime.utcnow()
    exp = now + timedelta(hours=JWT_EXPIRATION_HOURS)

    payload = {
        "correo": correo,
        "role": role,
        "nombre": nombre,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp())
    }
    
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    # PyJWT v1 puede devolver bytes; asegurarse de devolver str
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token


def validar_token(token):
    """
    Valida un JWT y retorna información del usuario
    
    Returns:
        dict: {
            "valido": bool,
            "correo": str,
            "role": str,
            "nombre": str,
            "error": str (opcional)
        }
    """
    if not token:
        logger.info("validar_token: token ausente")
        return {"valido": False, "error": "Token es obligatorio"}

    # Normalizar token (acepta bytes, y 'Bearer <token>')
    if isinstance(token, bytes):
        try:
            token = token.decode("utf-8")
        except Exception:
            logger.info("validar_token: decodificación de bytes fallida")
            return {"valido": False, "error": "Token inválido (decodificación)"}
    token = token.strip()
    masked = _mask_token(token)
    if token.lower().startswith("bearer "):
        token = token.split(" ", 1)[1].strip()
        logger.info(f"validar_token: token con prefijo Bearer recibido (enmascarado)={masked}")

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        
        return {
            "valido": True,
            "correo": payload.get("correo"),
            "role": payload.get("role", "Cliente"),
            "nombre": payload.get("nombre", "")
        }
    except jwt.ExpiredSignatureError:
        logger.info(f"validar_token: token expirado (enmascarado)={_mask_token(token)}")
        return {"valido": False, "error": "Token expirado"}
    except jwt.InvalidTokenError as e:
        logger.info(f"validar_token: token inválido (enmascarado)={_mask_token(token)} error={str(e)}")
        return {"valido": False, "error": "Token inválido"}


def verificar_rol(usuario_autenticado, roles_permitidos):
    """
    Verifica si el usuario tiene uno de los roles permitidos
    
    Args:
        usuario_autenticado: dict con 'role' del token
        roles_permitidos: list de roles permitidos, ej: ["Admin", "Gerente"]
    
    Returns:
        bool: True si tiene permiso
    """
    role_usuario = usuario_autenticado.get("role")
    return role_usuario in roles_permitidos
