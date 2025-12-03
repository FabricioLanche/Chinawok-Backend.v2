# 🥡 ChinaWok Backend

Sistema serverless completo para gestión de pedidos de restaurantes con AWS Lambda, DynamoDB, Step Functions y WebSockets.

## 📁 Estructura

```
.
├── DataGenerator/          # Scripts para generar datos de prueba
├── Layers/                 # Lambda Layer compartido (utilidades + dependencias)
├── Microservicios/
│   ├── Usuarios/          # Auth JWT + CRUD usuarios + Lambda Authorizer
│   ├── Empleados/         # CRUD empleados + reseñas
│   ├── Locales/           # CRUD locales + Analítica (Athena + DynamoDB Streams)
│   └── Pedidos/           # CRUD pedidos/productos/combos/ofertas + Step Functions + WebSockets
├── .env.example           # Variables de entorno
├── serverless-compose.yml # Orquestación de microservicios
└── setup_and_deploy.sh    # Script de despliegue
```

## 🚀 Despliegue Rápido

```bash
# 1. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus valores (AWS_ACCOUNT_ID, ORG_NAME, etc.)

# 2. Ejecutar script de despliegue
bash setup_and_deploy.sh
```

**Opciones:**
1. Despliegue completo (generar datos + desplegar)
2. Solo generar y poblar datos
3. Solo desplegar microservicios
4. Eliminar todos los recursos

## 🏗️ Arquitectura

### Microservicios

#### Usuarios
- **Endpoints:** `/usuario/*`
- **Funciones:** Login, registro, CRUD usuarios, historial de pedidos
- **Seguridad:** JWT (HS256) + Lambda Authorizer compartido
- **Roles:** Gerente, Cliente

#### Empleados
- **Endpoints:** `/empleados/*`, `/resenas/*`
- **Funciones:** CRUD empleados, gestión de reseñas/calificaciones
- **Roles:** Cocinero, Despachador, Repartidor
- **Features:** Sistema de disponibilidad (ocupado/libre), promedio de calificaciones

#### Locales
- **Endpoints:** `/local/*`, `/analitica/*`
- **Funciones:** CRUD locales, consultas analíticas
- **Analítica:**
  - DynamoDB Streams → S3 (JSONL) → Athena
  - Procesamiento incremental en tiempo real
  - Consultas: top productos, mejor personal, récord diario, estadísticas generales

#### Pedidos (Microservicio Principal)
- **Endpoints:** `/pedidos/*`, `/productos/*`, `/combos/*`, `/ofertas/*`
- **Funciones:** CRUD completo + workflow automatizado
- **Características:**
  - **Step Functions:** Workflow de 21 estados (cocinar → empacar → enviar → confirmar)
  - **WebSockets:** Notificaciones en tiempo real del estado del pedido
  - **EventBridge:** Disparo automático del workflow al crear pedido
  - **Gestión empleados:** Asignación automática según disponibilidad
  - **Reintentos:** Manejo robusto de errores (5 intentos antes de cancelar)
  - **Modos:** Demo (10s por etapa) o Realista (tiempos reales)

### Lambda Layer Compartido

**Utilidades:**
- `jwt_utils.py` - Generación/validación JWT
- `dynamodb_helper.py` - Operaciones DynamoDB + gestión de empleados
- `athena_client.py` - Consultas Athena
- `s3_client.py` - Operaciones S3
- `cors_utils.py`, `json_encoder.py`, `logger.py`

**Dependencias:** boto3, PyJWT, python-dotenv, fastapi, pydantic

## 🔄 Workflow de Pedidos (Step Functions)

```
Pedido Creado → EventBridge
  ↓
ExtraerDetail → Inicializar
  ↓
IntentarCocinar (busca cocinero, 5 reintentos con espera 30s)
  ↓ Espera: 10s (demo) / 15min (realista)
IntentarEmpacar (busca despachador)
  ↓ Espera: 10s (demo) / 5min (realista)
IntentarEnviar (busca repartidor)
  ↓ Espera: 10s (demo) / 30min (realista)
EsperarConfirmacionUsuario (callback token, timeout 1h)
  ↓
ConfirmarEntrega → Pedido Completado
```

**Errores manejados:**
- No empleado disponible → Reintentos (5x)
- Servicio saturado → Cancelación + limpieza
- Error fatal → Liberación de empleados + fail state
- Timeout confirmación → Confirmación automática

## 📡 WebSockets en Tiempo Real

**Conexión:**
```
wss://{api-id}.execute-api.us-east-1.amazonaws.com/dev
?usuario_correo={email}&pedido_id={id}
```

**Eventos enviados:**
- `ESTADO_ACTUALIZADO` - Cambio de estado (procesando, cocinando, empacando, enviando, recibido)
- `EMPLEADO_ASIGNADO` - Info del empleado asignado a cada etapa

## 📊 Analítica con DynamoDB Streams

**Flujo:**
```
Cambios DynamoDB → Streams → streamProcessor Lambda
  → S3 (JSONL incremental) → Glue Catalog → Athena
```

**Tablas procesadas:** Locales, Productos, Empleados, Combos, Pedidos, Ofertas, Reseñas

**Consultas disponibles:**
- `POST /analitica/productos` - Top productos vendidos
- `POST /analitica/personal` - Ranking empleados
- `POST /analitica/diario` - Récord diario por mes
- `POST /analitica/estadisticas` - Dashboard general

## 🗄️ Tablas DynamoDB

| Tabla | PK | SK | Streams |
|-------|----|----|---------|
| ChinaWok-Usuarios | correo | - | ❌ |
| ChinaWok-Locales | local_id | - | ✅ |
| ChinaWok-Empleados | local_id | dni | ✅ |
| ChinaWok-Productos | local_id | producto_id | ✅ |
| ChinaWok-Combos | local_id | combo_id | ✅ |
| ChinaWok-Pedidos | local_id | pedido_id | ✅ |
| ChinaWok-Ofertas | local_id | oferta_id | ✅ |
| ChinaWok-Resenas | local_id | resena_id | ✅ |
| ChinaWok-Conexiones | usuario_correo | pedido_id | ❌ |

## 📝 Variables de Entorno Clave

```bash
# AWS
AWS_ACCOUNT_ID=123456789012
ORG_NAME=your-org-name

# JWT
JWT_SECRET=your-secret-key-change-in-production
JWT_EXPIRATION_HOURS=24

# Step Functions
MODO_REALISTA=false  # true para tiempos reales
STEP_FUNCTION_PEDIDOS_NAME=ChinaWok-Pedidos-Processor
EVENT_BUS_NAME=chinawok-pedidos-events

# Analítica
ATHENA_DATABASE=chinawok_analytics
S3_BUCKET_NAME=chinawok-data
GLUE_CRAWLER_NAME=chinawok-analytics-crawler
```

Ver [.env.example](file:///C:/Users/ADMIN/Desktop/Chinawok-Backend-2/.env.example) para lista completa.

## 🔧 Desarrollo

### Requisitos
- Node.js 18+
- Python 3.12+
- AWS CLI configurado
- Serverless Framework

### Comandos

```bash
# Desplegar todo
serverless deploy

# Desplegar servicio específico
cd Microservicios/Pedidos && serverless deploy

# Ver logs
serverless logs -f nombreFuncion --tail

# Eliminar todo
serverless remove
```

### Orden de Despliegue
1. `shared-layer` (Layer)
2. `usuarios` 
3. `locales`
4. `empleados`
5. `pedidos` (depende de todos los anteriores)

## 🔐 Seguridad

- **Autenticación:** JWT tokens (HS256)
- **Autorización:** Lambda Authorizer compartido (TTL=0)
- **Roles:** Gerente, Cliente
- **IAM:** LabRole (AWS Academy) con permisos DynamoDB, S3, Lambda, Step Functions, EventBridge, Athena, Glue
- **Validación:** Schemas JSON en DataGenerator (no implementados en lambdas aún)

## 📦 Generador de Datos

```bash
cd DataGenerator
pip install -r requirements.txt
python DataGenerator.py   # Genera JSONs
python DataPoblator.py    # Puebla DynamoDB
```

**Genera:**
- Locales, Usuarios, Productos, Empleados, Combos, Pedidos, Ofertas, Reseñas
- Datos realistas con relaciones consistentes
- Schemas de validación en `schemas-validation/`

## 📄 Colección Postman

Ver [ChinaWok.postman_collection.json](file:///C:/Users/ADMIN/Desktop/Chinawok-Backend-2/ChinaWok.postman_collection.json) para ejemplos de requests.

## 📚 Documentación Adicional

Para análisis detallado de la arquitectura, ver documento de revisión interno.
