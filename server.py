"""
Servidor de Testing Local - Mi Contador de Bolsillo (Deuna)
FastAPI + Pandas + Deepseek API para analizar datasets y responder preguntas de negocio.
"""

import sys
import io

# Configurar UTF-8 para Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import json
import os
import re
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

# Cargar variables de entorno
load_dotenv()

# Configuración de Deepseek API
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API")
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"  # Modelo más rápido (non-thinking mode)

# Configuración
app = FastAPI(
    title="Mi Contador de Bolsillo - API",
    description="Asistente conversacional para micro-comerciantes ecuatorianos con Deepseek AI",
    version="2.0.0"
)

# CORS para desarrollo local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# Convertir fechas
df_transacciones['fecha_transaccion'] = pd.to_datetime(df_transacciones['fecha_transaccion'])
df_transacciones['hora_transaccion'] = pd.to_datetime(df_transacciones['hora_transaccion'], format='%H:%M:%S').dt.time
df_transacciones['mes'] = df_transacciones['fecha_transaccion'].dt.month
df_transacciones['trimestre'] = df_transacciones['fecha_transaccion'].dt.quarter
df_transacciones['dia_semana'] = df_transacciones['fecha_transaccion'].dt.day_name()
df_transacciones['hora'] = pd.to_datetime(df_transacciones['hora_transaccion'], format='%H:%M:%S').dt.hour

# Merge con comercios y clientes
df_completo = df_transacciones.merge(
    df_comercios[['id_comercio', 'nombre_comercio', 'rubro', 'ciudad']],
    on='id_comercio',
    how='left'
).merge(
    df_clientes[['id_cliente', 'edad', 'genero', 'frecuencia_visita']],
    on='id_cliente',
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


# ==================== MOTOR DE ANÁLISIS CON DEEPSEEK ====================

class AnalizadorNegocio:
    """Motor para analizar preguntas de negocio usando Deepseek AI."""

    def __init__(self, df: pd.DataFrame, df_clientes: pd.DataFrame, df_comercios: pd.DataFrame):
        self.df = df
        self.df_clientes = df_clientes
        self.df_comercios = df_comercios
        self.comercios = df['nombre_comercio'].unique()
        self.rubros = df['rubro'].unique()

    def get_comercio_data(self, id_comercio: str) -> Dict:
        """Obtiene los datos de un comercio específico con cálculos matemáticos correctos."""
        df_comercio = self.df[self.df['id_comercio'] == id_comercio].copy()

        if len(df_comercio) == 0:
            return None

        comercio_info = self.df_comercios[self.df_comercios['id_comercio'] == id_comercio].iloc[0]

        # Cálculos matemáticos correctos
        total_ventas = df_comercio['monto_transaccion'].sum()
        total_transacciones = len(df_comercio)
        ticket_promedio = df_comercio['monto_transaccion'].mean()
        ticket_mediana = df_comercio['monto_transaccion'].median()
        ticket_min = df_comercio['monto_transaccion'].min()
        ticket_max = df_comercio['monto_transaccion'].max()
        clientes_unicos = df_comercio['id_cliente'].nunique()

        # Métodos de pago
        metodos_pago = df_comercio['metodo_pago'].value_counts().to_dict()
        metodos_pct = {
            metodo: round((cantidad / total_transacciones) * 100, 2)
            for metodo, cantidad in metodos_pago.items()
        }

        # Top productos por monto y cantidad
        productos_stats = df_comercio.groupby('descripcion_producto_o_servicio').agg({
            'monto_transaccion': ['sum', 'count', 'mean']
        }).reset_index()
        productos_stats.columns = ['producto', 'total_monto', 'cantidad_ventas', 'promedio_monto']
        productos_stats = productos_stats.sort_values('total_monto', ascending=False)
        top_productos = productos_stats.head(5).to_dict('records')

        # Ventas por mes
        ventas_mensuales = df_comercio.groupby('mes').agg({
            'monto_transaccion': ['sum', 'count']
        }).reset_index()
        ventas_mensuales.columns = ['mes', 'ventas_total', 'transacciones']
        ventas_mensuales_dict = ventas_mensuales.set_index('mes').to_dict('index')

        # Días de la semana
        dias_ventas = df_comercio['dia_semana'].value_counts().to_dict()

        # Horas pico
        horas_pico = df_comercio['hora'].value_counts().head(5).to_dict()

        # Información de clientes
        clientes_df = df_comercio.merge(
            self.df_clientes[['id_cliente', 'edad', 'genero', 'frecuencia_visita']],
            on='id_cliente',
            how='left'
        )

        edad_promedio = clientes_df['edad'].mean() if 'edad' in clientes_df.columns and not clientes_df['edad'].isna().all() else 0
        genero_dist = clientes_df['genero'].value_counts().to_dict() if 'genero' in clientes_df.columns else {}
        frecuencia_dist = clientes_df['frecuencia_visita'].value_counts().to_dict() if 'frecuencia_visita' in clientes_df.columns else {}

        # Clientes top por gasto
        clientes_gasto = df_comercio.groupby('id_cliente')['monto_transaccion'].sum().sort_values(ascending=False).head(5)

        # Comparación mes a mes
        if len(ventas_mensuales) >= 2:
            ventas_list = ventas_mensuales['ventas_total'].tolist()
            cambio_mes = ((ventas_list[-1] - ventas_list[-2]) / ventas_list[-2]) * 100 if ventas_list[-2] != 0 else 0
        else:
            cambio_mes = 0

        return {
            "comercio": {
                "id": id_comercio,
                "nombre": comercio_info['nombre_comercio'],
                "rubro": comercio_info['rubro'],
                "ciudad": comercio_info.get('ciudad', 'N/A')
            },
            "metricas": {
                "total_ventas": round(total_ventas, 2),
                "total_transacciones": int(total_transacciones),
                "ticket_promedio": round(ticket_promedio, 2),
                "ticket_mediana": round(ticket_mediana, 2),
                "ticket_minimo": round(ticket_min, 2),
                "ticket_maximo": round(ticket_max, 2),
                "clientes_unicos": int(clientes_unicos)
            },
            "metodos_pago": {
                "conteo": metodos_pago,
                "porcentajes": metodos_pct
            },
            "productos_top": top_productos,
            "ventas_mensuales": ventas_mensuales_dict,
            "dias_ventas": dias_ventas,
            "horas_pico": horas_pico,
            "clientes": {
                "edad_promedio": round(edad_promedio, 1),
                "distribucion_genero": genero_dist,
                "distribucion_frecuencia": frecuencia_dist,
                "top_clientes_gasto": clientes_gasto.to_dict()
            },
            "tendencia": {
                "cambio_mes_anterior": round(cambio_mes, 2)
            }
        }

    def generar_contexto_ia(self, datos: Dict) -> str:
        """Genera un contexto optimizado para la IA."""
        m = datos['metricas']
        c = datos['comercio']

        contexto = f"""=== DATOS DEL COMERCIO ===
Nombre: {c['nombre']}
Rubro: {c['rubro']}
Ciudad: {c['ciudad']}

=== MÉTRICAS CLAVE (CÁLCULOS REALES) ===
• Total de ventas: ${m['total_ventas']:,.2f}
• Número de transacciones: {m['total_transacciones']:,}
• Ticket promedio: ${m['ticket_promedio']:.2f}
• Ticket mediana: ${m['ticket_mediana']:.2f}
• Clientes únicos: {m['clientes_unicos']:,}
• Tendencia vs mes anterior: {datos['tendencia']['cambio_mes_anterior']:+.1f}%

=== MÉTODOS DE PAGO ===
"""
        for metodo, pct in datos['metodos_pago']['porcentajes'].items():
            contexto += f"• {metodo}: {pct}% ({datos['metodos_pago']['conteo'][metodo]} trans)\n"

        contexto += "\n=== TOP 5 PRODUCTOS POR VENTAS ===\n"
        for i, prod in enumerate(datos['productos_top'], 1):
            contexto += f"{i}. {prod['producto']}: ${prod['total_monto']:,.2f} ({prod['cantidad_ventas']} ventas, promedio ${prod['promedio_monto']:.2f})\n"

        contexto += "\n=== VENTAS POR MES ===\n"
        for mes, data in sorted(datos['ventas_mensuales'].items()):
            contexto += f"• Mes {mes}: ${data['ventas_total']:,.2f} ({data['transacciones']} transacciones)\n"

        contexto += f"\n=== PERFIL DE CLIENTES ===\n• Edad promedio: {datos['clientes']['edad_promedio']} años\n"
        if datos['clientes']['distribucion_genero']:
            contexto += "• Género: " + ", ".join([f"{k}: {v}" for k, v in datos['clientes']['distribucion_genero'].items()]) + "\n"

        contexto += "\nINSTRUCCIONES: Responde basándote ÚNICAMENTE en estos datos. Sé conciso y directo. Si preguntan cálculos, usa estos valores exactos."

        return contexto

    def consultar_deepseek(self, mensaje: str, contexto: str) -> str:
        """Consulta a Deepseek API."""
        if not DEEPSEEK_API_KEY:
            return "Error: No se ha configurado la API key de Deepseek (DEEPSEEK_API)."

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
        }

        data = {
            "model": DEEPSEEK_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "Eres un asistente experto en análisis de datos para micro-comerciantes ecuatorianos. Responde de manera clara, concisa y útil. Usa máximo 3-4 oraciones."
                },
                {
                    "role": "user",
                    "content": f"{contexto}\n\nPREGUNTA: {mensaje}"
                }
            ],
            "max_tokens": 500,
            "temperature": 0.5,
            "stream": False
        }

        try:
            response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except requests.exceptions.RequestException as e:
            return f"Error de conexión con Deepseek: {str(e)}"
        except (KeyError, IndexError) as e:
            return f"Error procesando respuesta: {str(e)}"

    def responder(self, mensaje: str, id_comercio: Optional[str] = None) -> ChatResponse:
        """Genera una respuesta usando Deepseek AI."""
        if not id_comercio:
            return ChatResponse(
                respuesta="Por favor selecciona un comercio primero. Puedes ver los disponibles en /api/comercios",
                tipo="error",
                datos={}
            )

        datos = self.get_comercio_data(id_comercio)

        if not datos:
            return ChatResponse(
                respuesta=f"No se encontró el comercio '{id_comercio}'. Verifica el ID.",
                tipo="error",
                datos={"comercios_disponibles": self.df_comercios['id_comercio'].tolist()}
            )

        contexto = self.generar_contexto_ia(datos)
        respuesta = self.consultar_deepseek(mensaje, contexto)

        return ChatResponse(
            respuesta=respuesta,
            tipo="ia_response",
            datos={"comercio": datos['comercio']}
        )

    def generar_alerta_proactiva(self, id_comercio: Optional[str] = None) -> AlertaProactiva:
        """Genera una alerta proactiva basada en tendencias."""
        if id_comercio:
            df_temp = self.df[self.df['id_comercio'] == id_comercio]
            nombre = self.df_comercios[self.df_comercios['id_comercio'] == id_comercio]['nombre_comercio'].iloc[0] if len(self.df_comercios[self.df_comercios['id_comercio'] == id_comercio]) > 0 else "Tu negocio"
        else:
            df_temp = self.df
            nombre = "Tu negocio"

        ventas_mensuales = df_temp.groupby('mes')['monto_transaccion'].sum()

        if len(ventas_mensuales) >= 2:
            mes_actual = ventas_mensuales.iloc[-1]
            mes_anterior = ventas_mensuales.iloc[-2]
            cambio = ((mes_actual - mes_anterior) / mes_anterior) * 100

            if cambio > 10:
                return AlertaProactiva(
                    titulo=f"¡{nombre} va en aumento! 📈",
                    descripcion=f"Tus ventas subieron un {cambio:.1f}% respecto al mes pasado.",
                    tipo="positiva"
                )
            elif cambio < -10:
                return AlertaProactiva(
                    titulo=f"Alerta en {nombre} 📉",
                    descripcion=f"Tus ventas bajaron un {abs(cambio):.1f}% respecto al mes pasado.",
                    tipo="negativa"
                )

        dia_pico = df_temp['dia_semana'].value_counts().index[0] if len(df_temp) > 0 else "este día"
        return AlertaProactiva(
            titulo=f"Consejo para {nombre} 💡",
            descripcion=f"Los {dia_pico}s son tus días con más ventas. Considera promociones.",
            tipo="consejo"
        )


# Inicializar analizador
analizador = AnalizadorNegocio(df_completo, df_clientes, df_comercios)


# ==================== ENDPOINTS ====================

@app.get("/")
async def root():
    """Sirve el index.html"""
    return FileResponse("index.html")


@app.get("/api/health")
async def health():
    """Endpoint de salud."""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "ai_provider": "deepseek",
        "model": DEEPSEEK_MODEL,
        "datos": {
            "transacciones": len(df_transacciones),
            "clientes": len(df_clientes),
            "comercios": len(df_comercios)
        }
    }


@app.get("/api/comercios")
async def get_comercios():
    """Devuelve todos los comercios disponibles con sus métricas."""
    comercios_list = []

    for _, comercio in df_comercios.iterrows():
        datos = analizador.get_comercio_data(comercio['id_comercio'])
        if datos:
            comercios_list.append({
                "id": comercio['id_comercio'],
                "nombre": comercio['nombre_comercio'],
                "rubro": comercio['rubro'],
                "ciudad": comercio.get('ciudad', 'N/A'),
                "metricas": datos['metricas']
            })

    return {
        "comercios": comercios_list,
        "total": len(comercios_list)
    }


@app.get("/api/comercio/{id_comercio}")
async def get_comercio(id_comercio: str):
    """Devuelve datos completos de un comercio específico."""
    datos = analizador.get_comercio_data(id_comercio)

    if not datos:
        raise HTTPException(status_code=404, detail=f"Comercio '{id_comercio}' no encontrado")

    return datos


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Endpoint principal para el chatbot con Deepseek AI.
    Requiere un mensaje y opcionalmente un id_comercio.
    """
    try:
        respuesta = analizador.responder(request.mensaje, request.id_comercio)
        return respuesta
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error procesando la consulta: {str(e)}")


@app.get("/api/alerta-proactiva")
async def alerta_proactiva(id_comercio: Optional[str] = Query(None)):
    """Genera una alerta proactiva basada en tendencias del negocio."""
    return analizador.generar_alerta_proactiva(id_comercio)


@app.get("/api/transacciones")
async def get_transacciones(
    limit: int = Query(100, ge=1, le=1000),
    id_comercio: Optional[str] = Query(None)
):
    """Devuelve transacciones, opcionalmente filtradas por comercio."""
    df_result = df_transacciones.copy()

    if id_comercio:
        df_result = df_result[df_result['id_comercio'] == id_comercio]

    # Merge con info de comercios
    df_result = df_result.merge(
        df_comercios[['id_comercio', 'nombre_comercio', 'rubro']],
        on='id_comercio',
        how='left'
    )

    return {
        "transacciones": df_result.head(limit).to_dict('records'),
        "total": len(df_result)
    }


# ==================== INICIAR SERVIDOR ====================

if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*60)
    print("🚀 Mi Contador de Bolsillo - Servidor con Deepseek AI")
    print("="*60)
    print(f"\n🤖 Modelo: {DEEPSEEK_MODEL}")
    print(f"🔑 API Key: {'✅ Configurada' if DEEPSEEK_API_KEY else '❌ No configurada'}")
    print("\n📍 URLs disponibles:")
    print("   • Frontend:    http://localhost:8000")
    print("   • API Docs:    http://localhost:8000/docs")
    print("   • Health:      http://localhost:8000/api/health")
    print("   • Comercios:   http://localhost:8000/api/comercios")
    print("\n💡 Ejemplos de uso:")
    print("   • Listar comercios: GET /api/comercios")
    print("   • Datos de comercio: GET /api/comercio/COM001")
    print("   • Chat: POST /api/chat")
    print("\n" + "="*60 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8000)
