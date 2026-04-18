"""
Servidor de Testing Local - Mi Contador de Bolsillo (Deuna)
FastAPI + Pandas + Groq API optimizado para el reto de micro-comerciantes.
"""

import sys
import io
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Configurar UTF-8 para Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Cargar variables de entorno
load_dotenv()

# Configuración de Groq API
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"  # Mantenemos este modelo por su latencia < 1s

# Configuración FastAPI
app = FastAPI(
    title="Mi Contador de Bolsillo - API",
    description="Asistente conversacional rápido y sin jerga para micro-comerciantes ecuatorianos",
    version="2.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rutas de datasets (Asegúrate de que la carpeta 'dataset' exista junto a este script)
DATASET_DIR = Path("dataset")
TRANSACCIONES_CSV = DATASET_DIR / "transacciones.csv"
CLIENTES_CSV = DATASET_DIR / "clientes.csv"
COMERCIOS_CSV = DATASET_DIR / "comercios.csv"

# ==================== CARGA Y PREPROCESAMIENTO O(1) ====================
print("📊 Cargando y optimizando datasets en memoria...")

try:
    df_transacciones = pd.read_csv(TRANSACCIONES_CSV)
    df_clientes = pd.read_csv(CLIENTES_CSV)
    df_comercios = pd.read_csv(COMERCIOS_CSV)

    # Convertir fechas y extraer dimensiones útiles para el comerciante
    df_transacciones['fecha_transaccion'] = pd.to_datetime(df_transacciones['fecha_transaccion'])
    df_transacciones['mes'] = df_transacciones['fecha_transaccion'].dt.month
    df_transacciones['dia_semana'] = df_transacciones['fecha_transaccion'].dt.day_name()
    # Mapeo a español para los días
    dias_es = {'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles', 
               'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'}
    df_transacciones['dia_semana'] = df_transacciones['dia_semana'].map(dias_es)
    df_transacciones['hora'] = pd.to_datetime(df_transacciones['hora_transaccion'], format='%H:%M:%S').dt.hour

    # Join maestro en memoria para consultas ultrarrápidas (< 5s garantizado)
    df_completo = df_transacciones.merge(
        df_comercios[['id_comercio', 'nombre_comercio', 'rubro', 'ciudad']],
        on='id_comercio',
        how='left'
    ).merge(
        df_clientes[['id_cliente', 'edad', 'genero', 'frecuencia_visita']],
        on='id_cliente',
        how='left'
    )
    print(f"✅ Datos cargados listos para análisis en tiempo real.")
except Exception as e:
    print(f"❌ Error al cargar datasets: {e}")


# ==================== MODELOS PYDANTIC ====================

class ChatRequest(BaseModel):
    mensaje: str
    id_comercio: Optional[str] = None

class ChatResponse(BaseModel):
    respuesta: str
    tipo: str
    datos: Optional[Dict] = None

class AlertaProactiva(BaseModel):
    titulo: str
    descripcion: str
    tipo: str


# ==================== MOTOR DE ANÁLISIS DE NEGOCIO ====================

class AnalizadorNegocio:
    """Extrae métricas precisas usando Pandas para inyectarlas al LLM como contexto irrefutable."""

    def __init__(self, df: pd.DataFrame, df_clientes: pd.DataFrame, df_comercios: pd.DataFrame):
        self.df = df
        self.df_clientes = df_clientes
        self.df_comercios = df_comercios

    def get_comercio_data(self, id_comercio: str) -> Dict:
        """Genera el diccionario con las 10+ respuestas matemáticas pre-calculadas."""
        df_comercio = self.df[self.df['id_comercio'] == id_comercio].copy()

        if len(df_comercio) == 0:
            return None

        comercio_info = self.df_comercios[self.df_comercios['id_comercio'] == id_comercio].iloc[0]

        # 1 y 2. Ventas y Transacciones
        total_ventas = df_comercio['monto_transaccion'].sum()
        total_transacciones = len(df_comercio)
        
        # 3. Ticket Promedio (Gasto habitual)
        ticket_promedio = df_comercio['monto_transaccion'].mean()
        clientes_unicos = df_comercio['id_cliente'].nunique()

        # 4. Métodos de pago (Efectivo vs App)
        metodos_pago = df_comercio['metodo_pago'].value_counts().to_dict()

        # 5. Top Productos
        productos_stats = df_comercio.groupby('descripcion_producto_o_servicio')['monto_transaccion'].agg(['sum', 'count']).reset_index()
        top_productos = productos_stats.sort_values('sum', ascending=False).head(3).to_dict('records')

        # 6. Tendencias mensuales
        ventas_mensuales = df_comercio.groupby('mes')['monto_transaccion'].sum()
        cambio_mes = 0
        if len(ventas_mensuales) >= 2:
            mes_actual = ventas_mensuales.iloc[-1]
            mes_anterior = ventas_mensuales.iloc[-2]
            cambio_mes = ((mes_actual - mes_anterior) / mes_anterior) * 100 if mes_anterior > 0 else 0

        # 7 y 8. Mejores días y Horas
        mejor_dia = df_comercio['dia_semana'].value_counts().index[0] if not df_comercio.empty else "N/A"
        hora_pico = df_comercio['hora'].value_counts().index[0] if not df_comercio.empty else 0

        # 9 y 10. Perfil del cliente y Top clientes
        edad_promedio = df_comercio['edad'].mean()
        frecuencia_dist = df_comercio['frecuencia_visita'].mode()[0] if 'frecuencia_visita' in df_comercio else "N/A"
        
        # Formatear datos para inyección directa
        return {
            "nombre": comercio_info['nombre_comercio'],
            "metricas_clave": {
                "ventas_totales": round(total_ventas, 2),
                "numero_ventas": int(total_transacciones),
                "promedio_gasto_por_cliente": round(ticket_promedio, 2),
                "clientes_distintos": int(clientes_unicos),
                "crecimiento_vs_mes_pasado_pct": round(cambio_mes, 1)
            },
            "habitos_compra": {
                "mejor_dia_ventas": mejor_dia,
                "hora_con_mas_clientes": f"{hora_pico}:00",
                "metodos_pago_usados": metodos_pago,
                "productos_mas_vendidos": [{"producto": p['descripcion_producto_o_servicio'], "monto_total": round(p['sum'], 2), "cantidad": p['count']} for p in top_productos]
            },
            "perfil_clientes": {
                "edad_promedio": round(edad_promedio, 0) if pd.notna(edad_promedio) else "Desconocida",
                "frecuencia_habitual": frecuencia_dist
            }
        }

    def generar_contexto_ia(self, datos: Dict) -> str:
        """Construye un bloque de texto blindado contra alucinaciones."""
        return f"""
        DATOS REALES DEL NEGOCIO "{datos['nombre']}":
        - Ingresos totales (Ventas): ${datos['metricas_clave']['ventas_totales']}
        - Cantidad de ventas realizadas: {datos['metricas_clave']['numero_ventas']}
        - En promedio, un cliente gasta: ${datos['metricas_clave']['promedio_gasto_por_cliente']}
        - Clientes únicos atendidos: {datos['metricas_clave']['clientes_distintos']}
        - Comparado con el mes anterior, las ventas {'subieron' if datos['metricas_clave']['crecimiento_vs_mes_pasado_pct'] > 0 else 'bajaron'} un {abs(datos['metricas_clave']['crecimiento_vs_mes_pasado_pct'])}%
        
        RUTINAS DEL NEGOCIO:
        - El día que más se vende es el: {datos['habitos_compra']['mejor_dia_ventas']}
        - La hora más ocupada es a las: {datos['habitos_compra']['hora_con_mas_clientes']}
        - Cómo pagan los clientes: {json.dumps(datos['habitos_compra']['metodos_pago_usados'], ensure_ascii=False)}
        - Los 3 productos que más dinero dejan: {json.dumps(datos['habitos_compra']['productos_mas_vendidos'], ensure_ascii=False)}
        
        SOBRE LOS CLIENTES:
        - Edad promedio: {datos['perfil_clientes']['edad_promedio']} años
        - Frecuencia con la que vienen: {datos['perfil_clientes']['frecuencia_habitual']}
        """

    def consultar_groq(self, mensaje: str, contexto: str) -> str:
        """Interacción rápida y controlada con la IA."""
        if not GROQ_API_KEY:
            return "Error: Falta la llave de Groq API (.env)."

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GROQ_API_KEY}"
        }

        # Prompt de Sistema enfocado en el comerciante sin conocimientos financieros
        system_prompt = (
            "Eres 'Mi Contador de Bolsillo', el asistente amigable de Deuna para dueños de micro-comercios ecuatorianos. "
            "Tu objetivo es explicar sus ventas de forma súper sencilla, como si hablaras con un amigo. "
            "REGLAS INQUEBRANTABLES:\n"
            "1. CERO JERGA FINANCIERA (no uses 'KPIs', 'revenue', 'ROI', 'ticket promedio'). Usa palabras normales como 'ingresos', 'gasto promedio' o 'lo que más vendes'.\n"
            "2. Responde en 1, 2 o máximo 3 oraciones cortas y al grano.\n"
            "3. NO INVENTES NÚMEROS. Tu única verdad es la información proporcionada. Si te preguntan algo que no está en los datos di: 'Uy, ese dato todavía no lo tengo registrado, pero sigo aprendiendo.'\n"
            "4. Usa el signo de dólar ($) y comas para los miles.\n"
            "5. Mantén un tono cálido, optimista pero muy directo."
        )

        data = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"AQUÍ ESTÁN LOS DATOS DE MI NEGOCIO:\n{contexto}\n\nMI PREGUNTA ES:\n{mensaje}"}
            ],
            "max_tokens": 150, # Reducido para asegurar respuesta rápida y al grano
            "temperature": 0.1, # Casi 0 para matar la creatividad/alucinación
            "top_p": 0.9,
            "stream": False
        }

        try:
            response = requests.post(GROQ_API_URL, headers=headers, json=data, timeout=5) # Límite estricto de 5s
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return "Lo siento, tuve un problema de conexión intentando leer tus datos. Intenta de nuevo."

    def responder(self, mensaje: str, id_comercio: Optional[str] = None) -> ChatResponse:
        """Orquestador del flujo de consulta."""
        if not id_comercio:
            return ChatResponse(respuesta="Por favor indícame cuál es tu comercio primero.", tipo="error")

        datos = self.get_comercio_data(id_comercio)
        if not datos:
            return ChatResponse(respuesta="No encuentro los datos de ese comercio.", tipo="error")

        contexto = self.generar_contexto_ia(datos)
        respuesta_ia = self.consultar_groq(mensaje, contexto)

        return ChatResponse(respuesta=respuesta_ia, tipo="ia_response", datos={"comercio_nombre": datos["nombre"]})

    def generar_alerta_proactiva(self, id_comercio: Optional[str] = None) -> AlertaProactiva:
        """Insights procesables en lenguaje de comerciante."""
        df_temp = self.df[self.df['id_comercio'] == id_comercio] if id_comercio else self.df
        nombre = self.df_comercios[self.df_comercios['id_comercio'] == id_comercio]['nombre_comercio'].iloc[0] if id_comercio else "Tu negocio"

        ventas_mensuales = df_temp.groupby('mes')['monto_transaccion'].sum()

        if len(ventas_mensuales) >= 2:
            mes_actual = ventas_mensuales.iloc[-1]
            mes_anterior = ventas_mensuales.iloc[-2]
            cambio = ((mes_actual - mes_anterior) / mes_anterior) * 100

            if cambio > 5:
                return AlertaProactiva(
                    titulo=f"¡Vas con todo! 📈",
                    descripcion=f"Tus ventas en {nombre} han subido un {cambio:.1f}% comparado con el mes pasado. ¡Sigue así!",
                    tipo="positiva"
                )
            elif cambio < -5:
                return AlertaProactiva(
                    titulo=f"Ojo con las ventas 📉",
                    descripcion=f"Tus ingresos bajaron un {abs(cambio):.1f}%. ¿Qué tal si lanzamos una promo especial esta semana?",
                    tipo="negativa"
                )

        dia_pico = df_temp['dia_semana'].value_counts().index[0] if len(df_temp) > 0 else "N/A"
        return AlertaProactiva(
            titulo=f"Un tip para vender más 💡",
            descripcion=f"Noté que los {dia_pico}s tienes muchísimos clientes. Es el día perfecto para ofrecerles productos nuevos.",
            tipo="consejo"
        )


# Instancia global
analizador = AnalizadorNegocio(df_completo, df_clientes, df_comercios)

# ==================== ENDPOINTS REST ====================

@app.get("/")
async def root():
    return FileResponse("index.html")

@app.get("/api/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat(), "model": GROQ_MODEL}

@app.get("/api/comercio/{id_comercio}")
async def get_comercio(id_comercio: str):
    datos = analizador.get_comercio_data(id_comercio)
    if not datos:
        raise HTTPException(status_code=404, detail="Comercio no encontrado")
    return datos

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    return analizador.responder(request.mensaje, request.id_comercio)

@app.get("/api/alerta-proactiva")
async def alerta_proactiva(id_comercio: Optional[str] = Query(None)):
    return analizador.generar_alerta_proactiva(id_comercio)

# ==================== EJECUCIÓN LOCAL ====================
if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*50)
    print("🚀 Deuna: Mi Contador de Bolsillo")
    print("="*50)
    uvicorn.run(app, host="0.0.0.0", port=8000)