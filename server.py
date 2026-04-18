"""
Servidor de Testing Local - Mi Contador de Bolsillo (Deuna)
FastAPI + Pandas + Groq API para analizar datasets y responder preguntas de negocio.
"""

import sys
import io

# Configurar UTF-8 para Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import json
import os
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Cargar variables de entorno
load_dotenv()

# Obtener el directorio base del proyecto
BASE_DIR = Path(__file__).parent.resolve()

# Configuración de Groq API
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant" 

# Configuración
app = FastAPI(
    title="Mi Contador de Bolsillo - API",
    description="API híbrida: Endpoints rápidos para datos duros y chatbot IA para análisis avanzado.",
    version="3.1.0"
)

# CORS para desarrollo local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montar carpeta public para archivos estáticos
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "public")), name="static")

# Rutas de datasets
DATASET_DIR = Path("dataset")
TRANSACCIONES_CSV = DATASET_DIR / "transacciones.csv"
CLIENTES_CSV = DATASET_DIR / "clientes.csv"
COMERCIOS_CSV = DATASET_DIR / "comercios.csv"

# Cargar datos en memoria al iniciar
print("📊 Cargando datasets...")

df_transacciones = pd.read_csv(TRANSACCIONES_CSV)
df_clientes = pd.read_csv(CLIENTES_CSV)
df_comercios = pd.read_csv(COMERCIOS_CSV)

# Convertir fechas (nuevas columnas)
df_transacciones['fecha'] = pd.to_datetime(df_transacciones['fecha'])
df_transacciones['hora_dt'] = pd.to_datetime(df_transacciones['hora'], format='%H:%M', errors='coerce')
# Las columnas mes, dia_semana ya vienen en el CSV

# Merge con comercios y clientes (nuevas columnas)
df_completo = df_transacciones.merge(
    df_comercios[['comercio_id', 'nombre', 'categoria', 'ciudad', 'zona']],
    on='comercio_id',
    how='left'
).merge(
    df_clientes[['cliente_id', 'rango_edad', 'genero', 'visitas_por_mes', 'segmento', 'canal_preferido', 'nps_score']],
    on='cliente_id',
    how='left'
)

print(f"✅ Datos cargados: {len(df_transacciones):,} transacciones, {len(df_clientes)} clientes, {len(df_comercios)} comercios")


# ==================== MODELOS ====================

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


# ==================== MOTOR DE ANÁLISIS CON GROQ ====================

class AnalizadorNegocio:
    def __init__(self, df: pd.DataFrame, df_clientes: pd.DataFrame, df_comercios: pd.DataFrame):
        self.df = df
        self.df_clientes = df_clientes
        self.df_comercios = df_comercios

    def get_comercio_data(self, id_comercio: str) -> Dict:
        df_comercio = self.df[self.df['comercio_id'] == id_comercio].copy()

        if len(df_comercio) == 0:
            return None

        comercio_info = self.df_comercios[self.df_comercios['comercio_id'] == id_comercio].iloc[0]

        # Solo transacciones completadas para el saldo
        df_completadas = df_comercio[df_comercio['estado'] == 'Completada']
        total_ventas = df_completadas['monto_usd'].sum()
        total_transacciones = len(df_comercio)
        ticket_promedio = df_comercio['monto_usd'].mean()
        clientes_unicos = df_comercio['cliente_id'].nunique()

        metodos_pago = df_comercio['metodo_pago'].value_counts().to_dict()
        metodos_pct = {m: round((c / total_transacciones) * 100, 2) for m, c in metodos_pago.items()}

        productos_stats = df_comercio.groupby('categoria_producto').agg({
            'monto_usd': ['sum', 'count']
        }).reset_index()
        productos_stats.columns = ['producto', 'total_monto', 'cantidad_ventas']
        top_productos = productos_stats.sort_values('total_monto', ascending=False).head(5).to_dict('records')

        ventas_mensuales = df_comercio.groupby('mes').agg({'monto_usd': ['sum', 'count']}).reset_index()
        ventas_mensuales.columns = ['mes', 'ventas_total', 'transacciones']
        ventas_mensuales_dict = ventas_mensuales.set_index('mes').to_dict('index')

        # Ya tenemos datos de clientes en df_completo desde el merge inicial
        # rango_edad es categórica, no numérica
        genero_dist = df_comercio['genero'].value_counts().to_dict() if 'genero' in df_comercio.columns else {}
        # Usar segmento_cliente del dataframe de transacciones
        segmento_dist = df_comercio['segmento_cliente'].value_counts().to_dict() if 'segmento_cliente' in df_comercio.columns else {}
        visitas_promedio = df_comercio['visitas_por_mes'].mean() if 'visitas_por_mes' in df_comercio.columns else 0

        return {
            "comercio": {
                "id": id_comercio,
                "nombre": comercio_info['nombre'],
                "categoria": comercio_info['categoria'],
                "ciudad": comercio_info.get('ciudad', 'N/A'),
                "zona": comercio_info.get('zona', 'N/A')
            },
            "metricas": {
                "saldo_actual": round(total_ventas, 2),
                "total_transacciones": int(total_transacciones),
                "ticket_promedio": round(ticket_promedio, 2),
                "clientes_unicos": int(clientes_unicos)
            },
            "metodos_pago": {"conteo": metodos_pago, "porcentajes": metodos_pct},
            "productos_top": top_productos,
            "ventas_mensuales": ventas_mensuales_dict,
            "clientes": {
                "distribucion_genero": genero_dist,
                "distribucion_segmento": segmento_dist,
                "visitas_promedio_por_mes": round(visitas_promedio, 1)
            }
        }

    def generar_contexto_ia(self, datos: Dict) -> str:
        m = datos['metricas']
        c = datos['comercio']
        cl = datos['clientes']

        contexto = f"""=== ESTADO FINANCIERO Y DATOS DEL NEGOCIO ===
Nombre del Comercio: {c['nombre']}
Categoría: {c['categoria']}
Ubicación: {c['ciudad']} - {c['zona']}

=== SALDO Y MÉTRICAS CLAVE ===
• SALDO ACTUAL GENERADO (Total de ventas completadas): ${m['saldo_actual']:,.2f}
• Total de transacciones realizadas: {m['total_transacciones']:,}
• Ticket promedio por compra: ${m['ticket_promedio']:.2f}
• Clientes únicos atendidos: {m['clientes_unicos']}

=== TOP CATEGORÍAS DE PRODUCTOS ===\n"""
        for i, prod in enumerate(datos['productos_top'], 1):
            contexto += f"{i}. {prod['producto']}: ${prod['total_monto']:,.2f} ({prod['cantidad_ventas']} ventas)\n"

        contexto += f"\n=== PERFIL DE CLIENTES ===\n"
        contexto += f"• Visitas promedio por mes: {cl['visitas_promedio_por_mes']}\n"
        contexto += f"• Distribución por género: {cl['distribucion_genero']}\n"
        contexto += f"• Segmentos: {cl['distribucion_segmento']}\n"

        return contexto

    def consultar_groq(self, mensaje: str, contexto: str) -> str:
        if not GROQ_API_KEY: return "Error: GROQ_API_KEY no configurada."
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {GROQ_API_KEY}"}
        instrucciones = "Eres un asesor financiero analítico. Da consejos e insights basados en los datos. No inventes números."
        
        data = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": instrucciones},
                {"role": "user", "content": f"DATOS DEL NEGOCIO:\n{contexto}\n\nPREGUNTA: {mensaje}"}
            ],
            "max_tokens": 1024, "temperature": 0.3
        }

        try:
            r = requests.post(GROQ_API_URL, headers=headers, json=data, timeout=30)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"Error con Groq: {str(e)}"

    def responder(self, mensaje: str, id_comercio: Optional[str] = None) -> ChatResponse:
        if not id_comercio: return ChatResponse(respuesta="Selecciona un comercio.", tipo="error")
        datos = self.get_comercio_data(id_comercio)
        if not datos: return ChatResponse(respuesta="Comercio no encontrado.", tipo="error")
        return ChatResponse(respuesta=self.consultar_groq(mensaje, self.generar_contexto_ia(datos)), tipo="ia_response")


analizador = AnalizadorNegocio(df_completo, df_clientes, df_comercios)

def clean_df_for_json(df: pd.DataFrame) -> List[Dict]:
    return df.replace({np.nan: None}).to_dict('records')


# ==================== NUEVO ENDPOINT RAPIDO ====================

@app.get("/api/comercio/{id_comercio}/saldo")
async def get_saldo_comercio(id_comercio: str):
    """
    Devuelve de forma instantánea el saldo actual de un comercio 
    sin consultar a la Inteligencia Artificial.
    """
    datos = analizador.get_comercio_data(id_comercio)
    if not datos:
        raise HTTPException(status_code=404, detail=f"Comercio '{id_comercio}' no encontrado")
    
    return {
        "id_comercio": id_comercio,
        "nombre_comercio": datos['comercio']['nombre'],
        "saldo_actual": datos['metricas']['saldo_actual'],
        "moneda": "USD"
    }


# Endpoint para obtener datos completos de un comercio (para el dashboard)
@app.get("/api/comercio/{id_comercio}")
async def get_comercio_completo(id_comercio: str):
    """Devuelve datos completos de un comercio para el dashboard."""
    datos = analizador.get_comercio_data(id_comercio)
    if not datos:
        raise HTTPException(status_code=404, detail=f"Comercio '{id_comercio}' no encontrado")
    return datos


# Endpoint para alertas proactivas (simulado)
@app.get("/api/alerta-proactiva")
async def get_alerta_proactiva(id_comercio: str = Query(..., description="ID del comercio")):
    """Devuelve una alerta proactiva basada en análisis de datos."""
    datos = analizador.get_comercio_data(id_comercio)
    if not datos:
        raise HTTPException(status_code=404, detail=f"Comercio '{id_comercio}' no encontrado")

    # Generar alerta simple basada en los datos
    import random
    alertas = [
        {"titulo": "Ventas ↑", "descripcion": "Tus ventas subieron 15% esta semana", "tipo": "positiva"},
        {"titulo": "Oportunidad", "descripcion": "El método Nequi tiene alta demanda", "tipo": "oportunidad"},
        {"titulo": "Alerta", "descripcion": "Tus ventas bajaron 5% respecto al mes pasado", "tipo": "negativa"},
    ]

    # Seleccionar alerta basada en el ID del comercio para consistencia
    idx = hash(id_comercio) % len(alertas)
    return alertas[idx]


# ==================== RESTO DE ENDPOINTS ====================

@app.get("/api/datos/clientes")
async def get_todos_clientes(): return clean_df_for_json(df_clientes)

@app.get("/api/datos/comercios")
async def get_todos_comercios(): return clean_df_for_json(df_comercios)

@app.get("/api/datos/transacciones")
async def get_todas_transacciones(): return clean_df_for_json(df_transacciones.copy().astype(str))

@app.get("/api/datos/completos")
async def get_todo_fusionado(): return {"total_filas": len(df_completo), "datos": clean_df_for_json(df_completo.copy().astype(str))}

@app.get("/")
async def root(): return FileResponse(str(BASE_DIR / "public" / "index.html"))

@app.get("/api/comercios")
async def get_comercios():
    comercios_list = [analizador.get_comercio_data(c['comercio_id']) for _, c in df_comercios.iterrows() if analizador.get_comercio_data(c['comercio_id'])]
    return {"comercios": comercios_list, "total": len(comercios_list)}

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest): return analizador.responder(request.mensaje, request.id_comercio)


if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*65)
    print("🚀 Mi Contador de Bolsillo - Servidor Optimizado")
    print("="*65)
    print("\n📍 ENDPOINTS PRINCIPALES:")
    print("   • 💰 Saldo Rápido (GET):   http://localhost:5000/api/comercio/COM001/saldo")
    print("   • 🤖 Chat IA (POST):       http://localhost:5000/api/chat")
    print("   • 🏢 Comercios (GET):      http://localhost:5000/api/comercios")
    print("\n" + "="*65 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=5000)