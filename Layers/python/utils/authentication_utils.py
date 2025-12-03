"""
Utilidades de Autenticación y Autorización
Funciones compartidas para validar permisos de usuarios en todos los microservicios
"""

import boto3
import os
from typing import Dict, List, Optional

# Cliente DynamoDB
dynamodb = boto3.resource('dynamodb')

# Nombres de tablas
TABLE_USUARIOS = os.environ.get('TABLE_USUARIOS', 'ChinaWok-Usuarios')
TABLE_LOCALES = os.environ.get('TABLE_LOCALES', 'ChinaWok-Locales')


def obtener_usuario_autenticado(event: Dict) -> Dict[str, str]:
    """
    Extrae la información del usuario autenticado del Lambda Authorizer context
    
    Args:
        event: Evento de Lambda que contiene requestContext.authorizer
        
    Returns:
        dict: Información del usuario con keys: correo, role, nombre
        
    Ejemplo:
        >>> usuario = obtener_usuario_autenticado(event)
        >>> print(usuario['correo'])  # "usuario@example.com"
        >>> print(usuario['role'])    # "Cliente"
    """
    authorizer = event.get("requestContext", {}).get("authorizer", {})
    
    return {
        "correo": authorizer.get("correo"),
        "role": authorizer.get("role"),
        "nombre": authorizer.get("nombre", "")
    }


def verificar_rol(usuario: Dict[str, str], roles_permitidos: List[str]) -> bool:
    """
    Verifica si el usuario tiene uno de los roles permitidos
    
    Args:
        usuario: Diccionario con información del usuario (correo, role, nombre)
        roles_permitidos: Lista de roles que tienen acceso (ej: ["Admin", "Gerente"])
        
    Returns:
        bool: True si el usuario tiene uno de los roles permitidos
        
    Ejemplo:
        >>> if verificar_rol(usuario, ["Admin"]):
        >>>     # Solo Admin puede ejecutar esto
        >>>     pass
        >>> 
        >>> if verificar_rol(usuario, ["Admin", "Gerente"]):
        >>>     # Admin o Gerente pueden ejecutar esto
        >>>     pass
    """
    return usuario.get("role") in roles_permitidos


def obtener_local_del_gerente(gerente_correo: str) -> Optional[str]:
    """
    Obtiene el local_id asociado a un Gerente consultando la tabla de Locales
    
    Args:
        gerente_correo: Correo electrónico del Gerente
        
    Returns:
        str: local_id del local asignado al Gerente, o None si no se encuentra
        
    Ejemplo:
        >>> local_id = obtener_local_del_gerente("gerente@example.com")
        >>> print(local_id)  # "LOCAL-0001"
    """
    try:
        table = dynamodb.Table(TABLE_LOCALES)
        
        # Escanear la tabla buscando el local que tenga este Gerente
        # Nota: En producción, considerar usar un GSI en gerente.correo para mejor performance
        response = table.scan(
            FilterExpression='gerente.correo = :correo',
            ExpressionAttributeValues={':correo': gerente_correo}
        )
        
        items = response.get('Items', [])
        
        if items:
            return items[0].get('local_id')
        
        return None
        
    except Exception as e:
        print(f"Error obteniendo local del gerente: {str(e)}")
        return None


def verificar_local_gerente(usuario: Dict[str, str], local_id: str) -> bool:
    """
    Verifica que un Gerente tenga acceso al local especificado
    Admin siempre tiene acceso a todos los locales
    
    Args:
        usuario: Diccionario con información del usuario (correo, role, nombre)
        local_id: ID del local que se quiere acceder
        
    Returns:
        bool: True si el usuario tiene acceso al local
        
    Ejemplo:
        >>> if not verificar_local_gerente(usuario, local_id):
        >>>     return {'statusCode': 403, 'body': 'Acceso denegado'}
    """
    # Admin tiene acceso a todos los locales
    if usuario.get("role") == "Admin":
        return True
    
    # Gerente solo tiene acceso a su local asignado
    if usuario.get("role") == "Gerente":
        gerente_local = obtener_local_del_gerente(usuario["correo"])
        return gerente_local == local_id
    
    # Otros roles no tienen acceso a gestión de locales
    return False


def verificar_rol_solicitado(correo: str, rol_esperado: str) -> bool:
    """
    Verifica el rol de otro usuario consultando la tabla de Usuarios
    Útil cuando un Gerente quiere verificar si puede ver/modificar a otro usuario
    
    Args:
        correo: Correo del usuario a verificar
        rol_esperado: Rol que se espera (ej: "Cliente")
        
    Returns:
        bool: True si el usuario tiene el rol esperado
        
    Ejemplo:
        >>> # Gerente verifica si puede ver información de otro usuario
        >>> if not verificar_rol_solicitado(correo_solicitado, "Cliente"):
        >>>     return {'statusCode': 403, 'body': 'Solo puedes ver Clientes'}
    """
    try:
        table = dynamodb.Table(TABLE_USUARIOS)
        
        response = table.get_item(Key={'correo': correo})
        
        if 'Item' not in response:
            return False
        
        usuario = response['Item']
        return usuario.get('role') == rol_esperado
        
    except Exception as e:
        print(f"Error verificando rol del usuario: {str(e)}")
        return False


def es_mismo_usuario(usuario: Dict[str, str], correo_solicitado: str) -> bool:
    """
    Verifica si el usuario autenticado es el mismo que el correo solicitado
    
    Args:
        usuario: Diccionario con información del usuario autenticado
        correo_solicitado: Correo del usuario que se quiere acceder
        
    Returns:
        bool: True si es el mismo usuario
        
    Ejemplo:
        >>> if not es_mismo_usuario(usuario, correo_solicitado):
        >>>     return {'statusCode': 403, 'body': 'Solo puedes ver tu propia info'}
    """
    return usuario.get("correo") == correo_solicitado


def validar_acceso_usuario(usuario_autenticado: Dict[str, str], correo_solicitado: str) -> tuple[bool, str]:
    """
    Valida el acceso a información de otro usuario según las reglas de negocio:
    - Admin: puede ver a todos
    - Gerente: puede ver solo a Clientes
    - Cliente: solo puede verse a sí mismo
    
    Args:
        usuario_autenticado: Usuario que hace la petición
        correo_solicitado: Usuario al que se quiere acceder
        
    Returns:
        tuple: (tiene_acceso: bool, mensaje_error: str)
        
    Ejemplo:
        >>> tiene_acceso, error = validar_acceso_usuario(usuario, correo_solicitado)
        >>> if not tiene_acceso:
        >>>     return {'statusCode': 403, 'body': json.dumps({'message': error})}
    """
    # Admin puede ver a todos
    if verificar_rol(usuario_autenticado, ["Admin"]):
        return True, ""
    
    # Gerente puede ver a Clientes y a sí mismo
    if verificar_rol(usuario_autenticado, ["Gerente"]):
        if es_mismo_usuario(usuario_autenticado, correo_solicitado):
            return True, ""
        
        if verificar_rol_solicitado(correo_solicitado, "Cliente"):
            return True, ""
        
        return False, "Gerente solo puede ver información de Clientes"
    
    # Cliente solo puede verse a sí mismo
    if es_mismo_usuario(usuario_autenticado, correo_solicitado):
        return True, ""
    
    return False, "Solo puedes ver tu propia información"


def validar_acceso_local(usuario: Dict[str, str], local_id: str) -> tuple[bool, str]:
    """
    Valida el acceso a un local específico
    
    Args:
        usuario: Usuario que hace la petición
        local_id: ID del local que se quiere acceder
        
    Returns:
        tuple: (tiene_acceso: bool, mensaje_error: str)
        
    Ejemplo:
        >>> tiene_acceso, error = validar_acceso_local(usuario, local_id)
        >>> if not tiene_acceso:
        >>>     return {'statusCode': 403, 'body': json.dumps({'message': error})}
    """
    # Admin tiene acceso a todos los locales
    if verificar_rol(usuario, ["Admin"]):
        return True, ""
    
    # Gerente solo a su local
    if verificar_rol(usuario, ["Gerente"]):
        if verificar_local_gerente(usuario, local_id):
            return True, ""
        return False, "Solo puedes acceder a tu local asignado"
    
    # Cliente no tiene acceso a gestión de locales
    return False, "Acceso denegado"


def require_roles(roles_permitidos: List[str]):
    """
    Decorador para validar roles de usuario en endpoints Lambda
    
    Args:
        roles_permitidos: Lista de roles que pueden acceder
        
    Ejemplo:
        >>> @require_roles(["Admin"])
        >>> def lambda_handler(event, context):
        >>>     # Solo Admin puede ejecutar esto
        >>>     pass
        
        >>> @require_roles(["Admin", "Gerente"])
        >>> def lambda_handler(event, context):
        >>>     # Admin o Gerente pueden ejecutar esto
        >>>     pass
    """
    def decorator(func):
        def wrapper(event, context):
            import json
            
            usuario = obtener_usuario_autenticado(event)
            
            if not verificar_rol(usuario, roles_permitidos):
                return {
                    'statusCode': 403,
                    'body': json.dumps({
                        'message': f'Acceso denegado. Roles permitidos: {", ".join(roles_permitidos)}'
                    })
                }
            
            return func(event, context)
        
        return wrapper
    return decorator
