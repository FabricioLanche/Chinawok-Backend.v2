import os, json, boto3, logging
from utils.cors_utils import get_cors_headers  # <-- importar CORS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

dynamodb = boto3.resource('dynamodb')
table_locales = dynamodb.Table(os.environ.get('TABLE_LOCALES', 'ChinaWok-Locales'))
table_usuarios = dynamodb.Table(os.environ.get('TABLE_USUARIOS', 'ChinaWok-Usuarios'))

def lambda_handler(event, context):
    headers = get_cors_headers()  # <-- CORS headers

    # Manejar preflight request
    if event.get("httpMethod") == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({"message": "CORS preflight successful"})
        }

    try:
        # Path param
        local_id = event.get('pathParameters', {}).get('local_id')
        if not local_id:
            return _resp(400, {"message": "Falta path parameter 'local_id'."}, headers)

        logger.info(f"Actualizando local con local_id: {local_id}")
        logger.info(f"Key schema: {table_locales.key_schema}")

        # Body seguro
        body_raw = event.get("body")
        if isinstance(body_raw, str):
            try:
                body = json.loads(body_raw or "{}")
            except Exception:
                return _resp(400, {"message": "Body inválido; se esperaba JSON"}, headers)
        elif isinstance(body_raw, dict):
            body = body_raw
        else:
            body = {}

        # Normalizaciones
        if "telefono" in body and body["telefono"] is not None:
            body["telefono"] = str(body["telefono"]).strip()

        gerente = body.get("gerente")
        if isinstance(gerente, dict) and "correo" in gerente and gerente["correo"] is not None:
            gerente["correo"] = str(gerente["correo"]).strip().lower()
            try:
                user_resp = table_usuarios.get_item(Key={"correo": gerente["correo"]})
                user = user_resp.get("Item")
                
                if not user:
                    return _resp(400, {"message": f"El usuario con correo '{gerente['correo']}' no existe."}, headers)
                
                user_role = user.get("role")
                if user_role not in ["Gerente", "Cliente"]:
                    return _resp(400, {"message": f"El usuario '{gerente['correo']}' debe tener rol 'Gerente' o 'Cliente'."}, headers)
                
                if user_role == "Gerente":
                    scan_resp = table_locales.scan(
                        FilterExpression="gerente.correo = :correo AND local_id <> :current_local",
                        ExpressionAttributeValues={
                            ":correo": gerente["correo"],
                            ":current_local": local_id
                        }
                    )
                    if scan_resp.get("Items"):
                        local_existente = scan_resp["Items"][0]
                        return _resp(400, {
                            "message": f"El gerente '{gerente['correo']}' ya tiene otro local asignado.",
                            "local_id": local_existente.get("local_id")
                        }, headers)
                
                gerente["nombre"] = user.get("nombre")
                gerente["contrasena"] = user.get("contrasena")
                
            except Exception as e:
                logger.error(f"Error al validar gerente: {str(e)}")
                return _resp(500, {"message": "Error al validar el gerente", "error": str(e)}, headers)

        # Construcción dinámica del UpdateExpression
        set_clauses, expr_vals, expr_names = [], {}, {}

        def set_attr(path_tokens, value):
            name_parts = []
            for i, t in enumerate(path_tokens):
                key = f"#n_{'_'.join(path_tokens[:i+1])}" if len(path_tokens) > 1 else f"#n_{t}"
                expr_names[key] = t
                name_parts.append(key)
            name_ref = ".".join(name_parts)
            val_key = f":v_{'_'.join(path_tokens)}"
            expr_vals[val_key] = value
            set_clauses.append(f"{name_ref} = {val_key}")

        for k in ["direccion", "telefono", "hora_apertura", "hora_finalizacion"]:
            if k in body and body[k] is not None:
                set_attr([k], body[k])

        if isinstance(gerente, dict):
            for gk in ["nombre", "correo", "contrasena"]:
                if gk in gerente and gerente[gk] is not None:
                    set_attr(["gerente", gk], gerente[gk])

        if not set_clauses:
            return _resp(400, {"message": "Nada que actualizar"}, headers)

        resp = table_locales.update_item(
            Key={"local_id": local_id},
            UpdateExpression="SET " + ", ".join(set_clauses),
            ExpressionAttributeValues=expr_vals,
            ExpressionAttributeNames=expr_names,
            ReturnValues="UPDATED_NEW"
        )

        return _resp(200, {"message": "Local actualizado", "updated": resp.get("Attributes")}, headers)

    except Exception as e:
        return _resp(500, {"message": "Error interno", "error": str(e)}, headers)

def _resp(status, body, headers):
    return {
        "statusCode": status,
        "headers": headers,
        "body": json.dumps(body, ensure_ascii=False)
    }
