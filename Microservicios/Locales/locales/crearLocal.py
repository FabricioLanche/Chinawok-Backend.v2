import os
import json
import uuid
import boto3
import logging
from utils.cors_utils import get_cors_headers  # <-- importar CORS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TABLE_LOCALES = os.environ.get("TABLE_LOCALES", "ChinaWok-Locales")
TABLE_USUARIOS = os.environ.get("TABLE_USUARIOS", "ChinaWok-Usuarios")
dynamodb = boto3.resource("dynamodb")
table_locales = dynamodb.Table(TABLE_LOCALES)
table_usuarios = dynamodb.Table(TABLE_USUARIOS)

def lambda_handler(event, context):
    headers = get_cors_headers()  # <-- aplicar CORS

    # Manejar preflight request
    if event.get("httpMethod") == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({"message": "CORS preflight successful"})
        }

    try:
        # Parseo seguro del body (API GW o tests)
        body_raw = event.get("body")
        if isinstance(body_raw, str):
            body = json.loads(body_raw or "{}")
        elif isinstance(body_raw, dict):
            body = body_raw
        else:
            body = {}

        # Log con contraseña enmascarada
        body_for_log = _mask_password(body)
        logger.info("Event (masked body): %s", json.dumps({**event, "body": body_for_log})[:2000])

        # Extraer campos esperados
        direccion = body.get("direccion")
        telefono = body.get("telefono")
        hora_apertura = body.get("hora_apertura")
        hora_finalizacion = body.get("hora_finalizacion")

        gerente = body.get("gerente")
        if not isinstance(gerente, dict) or "correo" not in gerente:
            return _resp(400, {"message": "Falta 'gerente.correo' en el body."}, headers)

        correo_gerente = str(gerente["correo"]).strip().lower()
        
        # Consultar el usuario en la tabla de usuarios
        try:
            user_resp = table_usuarios.get_item(Key={"correo": correo_gerente})
            user = user_resp.get("Item")
            
            if not user:
                return _resp(400, {"message": f"El usuario con correo '{correo_gerente}' no existe."}, headers)
            
            user_role = user.get("role")
            if user_role not in ["Gerente", "Cliente"]:
                return _resp(400, {"message": f"El usuario '{correo_gerente}' debe tener rol 'Gerente' o 'Cliente'."}, headers)
            
            if user_role == "Gerente":
                scan_resp = table_locales.scan(
                    FilterExpression="gerente.correo = :correo",
                    ExpressionAttributeValues={":correo": correo_gerente}
                )
                if scan_resp.get("Items"):
                    local_existente = scan_resp["Items"][0]
                    return _resp(400, {
                        "message": f"El gerente '{correo_gerente}' ya tiene un local asignado.",
                        "local_id": local_existente.get("local_id")
                    }, headers)
            
            if user_role == "Cliente":
                logger.info(f"Actualizando rol de Cliente a Gerente para: {correo_gerente}")
                table_usuarios.update_item(
                    Key={"correo": correo_gerente},
                    UpdateExpression="SET #role = :new_role",
                    ExpressionAttributeNames={"#role": "role"},
                    ExpressionAttributeValues={":new_role": "Gerente"}
                )
            
            gerente_completo = {
                "nombre": user.get("nombre"),
                "correo": correo_gerente,
                "contrasena": user.get("contrasena")
            }
            
        except Exception as e:
            logger.error(f"Error al validar gerente: {str(e)}")
            return _resp(500, {"message": "Error al validar el gerente", "error": str(e)}, headers)

        if not direccion:
            return _resp(400, {"message": "El campo 'direccion' es obligatorio."}, headers)

        if telefono is not None:
            telefono = str(telefono).strip()

        _ = table_locales.table_status
        logger.info(f"Key schema de tabla locales: {table_locales.key_schema}")

        item = {
            "local_id": str(uuid.uuid4()),
            "direccion": direccion,
            "telefono": telefono,
            "hora_apertura": hora_apertura,
            "hora_finalizacion": hora_finalizacion,
            "gerente": gerente_completo,
        }

        item = _prune_nones(item)

        logger.info(f"Creando local con local_id: {item.get('local_id')}")
        table_locales.put_item(Item=item)
        return _resp(201, item, headers)

    except Exception as e:
        logger.exception("Fallo en local/crear")
        return _resp(500, {"message": "Error interno", "error": str(e)}, headers)


def _resp(status, body, headers):
    return {
        "statusCode": status,
        "headers": headers,
        "body": json.dumps(body, ensure_ascii=False) if body != "" else ""
    }

def _mask_password(body: dict):
    try:
        b = json.loads(json.dumps(body))
        if isinstance(b.get("gerente"), dict) and "contrasena" in b["gerente"]:
            b["gerente"]["contrasena"] = "***"
        return b
    except Exception:
        return {"_unloggable_body": True}

def _prune_nones(obj):
    if isinstance(obj, dict):
        return {k: _prune_nones(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_prune_nones(v) for v in obj]
    return obj
