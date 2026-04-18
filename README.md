# Mi Contador de Bolsillo - Servidor de Testing

Asistente conversacional para micro-comerciantes ecuatorianos. Proyecto para el hackathon Interact2Hack 2026.

## Estructura del Proyecto

```
.
├── server.py              # Servidor FastAPI principal
├── requirements.txt       # Dependencias Python
├── index.html            # Frontend (Dashboard Deuna)
├── dataset/              # Datos sintéticos
│   ├── transacciones.csv  # ~2000 transacciones por comercio
│   ├── clientes.csv       # Catálogo de clientes
│   ├── comercios.csv      # Información de comercios
│   ├── glosario_terminos.txt
│   └── preguntas_tipicas.txt
└── README.md
```

## Instalación

### 1. Crear entorno virtual (recomendado)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Mac/Linux
python3 -m venv venv
source venv/bin/activate
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

## Ejecutar el Servidor

```bash
python server.py
```

El servidor se iniciará en:
- **Frontend**: http://localhost:8000
- **API Docs (Swagger)**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/health

## Endpoints de la API

### Chat del Asistente
```
POST /api/chat
{
  "mensaje": "¿Cuáles son mis ventas totales?",
  "id_comercio": "COM001"  // opcional
}
```

### Obtener Comercios
```
GET /api/comercios
```

### Resumen de Comercio
```
GET /api/resumen/COM001
```

### Alerta Proactiva
```
GET /api/alerta-proactiva
```

### Transacciones Recientes
```
GET /api/transacciones?limit=50&comercio=SuperFresh
```

## Ejemplos de Preguntas Soportadas

El asistente entiende preguntas en lenguaje natural como:

- **Ventas**: "¿Cuáles son mis ventas totales?", "¿Cuánto vendí este mes?"
- **Ticket Promedio**: "¿Cuál es el ticket promedio en SuperFresh?"
- **Transacciones**: "¿Cuántas transacciones tuve?"
- **Métodos de Pago**: "¿Qué métodos de pago usan mis clientes?"
- **Productos**: "¿Cuáles son mis productos más vendidos?"
- **Tendencias**: "¿Cómo han evolucionado mis ventas?"
- **Clientes**: "¿Cuántos clientes tengo?"
- **Días**: "¿En qué día de la semana vendo más?"
- **Horas**: "¿A qué hora tengo más ventas?"

## Características

- ✅ Procesamiento de datos con Pandas
- ✅ Detección de intenciones en español
- ✅ Filtros por período (mes, trimestre)
- ✅ Filtros por comercio
- ✅ Respuestas en lenguaje natural
- ✅ Alertas proactivas basadas en tendencias
- ✅ CORS habilitado para desarrollo

## Criterios de Éxito del Reto

| Criterio | Implementación |
|----------|----------------|
| 80% precisión | Motor de análisis con regex + pandas |
| < 5 segundos | Respuestas en memoria, sin LLM externo |
| Español natural | Respuestas formateadas amigablemente |
| 10+ tipos de preguntas | Ventas, ticket, transacciones, métodos, productos, tendencias, clientes, días, horas, comparaciones |
| Alerta proactiva | Endpoint `/api/alerta-proactiva` con análisis de tendencias |

## Demo Rápida

```bash
# 1. Iniciar servidor
python server.py

# 2. Abrir navegador en http://localhost:8000

# 3. Probar endpoints en http://localhost:8000/docs
```
