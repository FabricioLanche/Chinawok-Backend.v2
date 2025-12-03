"""
Lambda Authorizer para validar tokens JWT en API Gateway
"""
import json
import logging
from utils.jwt_utils import validar_token

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _mask_token_local(t: str) -> str:
    """Versión local de enmascarado para evitar depender de la implementación en el Layer."""
    if not t:
        return "<empty>"
    try:
        if len(t) <= 12:
            return t[:3] + "..." + t[-3:]
        return t[:6] + "..." + t[-6:]
    except Exception:
        return "<invalid-token>"

def _get_token_from_event(event):
    """Extrae el token desde varias ubicaciones comunes del evento."""
    if not isinstance(event, dict):
        return None
    # Token authorizer clásico
    token = event.get("authorizationToken")
    if token:
        return token
    # Token puede venir en headers (API Gateway HTTP/API V2)
    headers = event.get("headers") or {}
    if isinstance(headers, dict):
        # comprobar mayúsculas/minúsculas
        return headers.get("authorization") or headers.get("Authorization")
    return None

def lambda_handler(event, context):
    """
    Lambda Authorizer con validación de JWT
    
    Este authorizer valida el token JWT y retorna una política IAM
    que permite o deniega el acceso al endpoint solicitado.
    """
    token = _get_token_from_event(event) or ""
    
    # Log del token recibido (enmascarado) para debugging
    try:
        masked = _mask_token_local(token if isinstance(token, str) else (token.decode("utf-8") if isinstance(token, bytes) else None))
    except Exception:
        masked = "<no-mask-possible>"
    logger.info(f"Authorizer: authorizationToken recibido (enmascarado)={masked}")

    # Asegurarse de trabajar con str
    if isinstance(token, bytes):
        try:
            token = token.decode("utf-8")
        except Exception:
            logger.info("Authorization token no pudo decodificarse")
            raise Exception("Unauthorized")
    
    # Extraer token si viene con prefijo "Bearer "
    if isinstance(token, str) and token.lower().startswith("bearer "):
        token = token.split(" ", 1)[1].strip()
    
    # Validar token usando la utilidad compartida
    resultado = validar_token(token)
    
    if not resultado.get("valido"):
        # Log con detalle para debugging interno (no devolver al cliente)
        logger.info(f"Authorizer: token inválido: {resultado.get('error')} (token enmascarado={masked})")
        raise Exception("Unauthorized")
    
    # Token válido - Retornar política IAM con contexto del usuario
    return {
        "principalId": resultado["correo"],
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": "Allow",
                    "Resource": event["methodArn"]
                }
            ]
        },
        "context": {
            "correo": resultado["correo"],
            "role": resultado["role"],
            "nombre": resultado.get("nombre", "")
        }
    }
