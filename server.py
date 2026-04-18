"""
Servidor de Testing Local - Mi Contador de Bolsillo (Deuna)
FastAPI + Pandas para analizar datasets y responder preguntas de negocio.
"""

import sys
import io

# Configurar UTF-8 para Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Configuración
app = FastAPI(
    title="Mi Contador de Bolsillo - API",
    description="Asistente conversacional para micro-comerciantes ecuatorianos",
    version="1.0.0"
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
    df_comercios[['id_comercio', 'nombre_comercio', 'rubro']],
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


# ==================== MOTOR DE ANÁLISIS ====================

class AnalizadorNegocio:
    """Motor para analizar preguntas de negocio y generar respuestas."""

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.comercios = df['nombre_comercio'].unique()
        self.rubros = df['rubro'].unique()

    def detectar_intencion(self, mensaje: str) -> tuple:
        """Detecta la intención de la pregunta del usuario."""
        mensaje_lower = mensaje.lower()

        # Patrones de intención
        patrones = {
            'ventas_totales': r'(ventas? total|ingresos? total|cuanto (vendio|gano)|total de ventas)',
            'ticket_promedio': r'(ticket promedio|promedio por venta|venta promedio|ticket medio)',
            'transacciones_count': r'(cuantas? transacciones|numero de ventas|cantidad de operaciones)',
            'metodo_pago': r'(metodo de pago|forma de pago|como pagan|tarjeta o efectivo)',
            'productos_top': r'(productos? (mas vendido|top)|lo mas vendido|que se vende mas)',
            'tendencias': r'(tendencia|evolucion|como (va|fue)|subio o bajo)',
            'clientes': r'(clientes?|compradores?|consumidores?)',
            'dia_semana': r'(dia de la semana|que dia|cuando se vende mas)',
            'hora_pico': r'(hora|momento del dia|en que hora)',
            'comparacion': r'(comparar|vs|contra|versus|diferencia entre)',
        }

        for intencion, patron in patrones.items():
            if re.search(patron, mensaje_lower):
                return intencion, mensaje_lower

        return 'general', mensaje_lower

    def extraer_comercio(self, mensaje: str) -> Optional[str]:
        """Extrae el nombre del comercio mencionado."""
        for comercio in self.comercios:
            if comercio.lower() in mensaje.lower():
                return comercio
        return None

    def extraer_periodo(self, mensaje: str) -> Optional[str]:
        """Extrae el período de tiempo mencionado."""
        mensaje_lower = mensaje.lower()

        if 'ultimo mes' in mensaje_lower or 'mes pasado' in mensaje_lower:
            return 'ultimo_mes'
        elif 'ultimo trimestre' in mensaje_lower or 'trimestre pasado' in mensaje_lower:
            return 'ultimo_trimestre'
        elif 'este mes' in mensaje_lower or 'mes actual' in mensaje_lower:
            return 'mes_actual'
        elif 'hoy' in mensaje_lower:
            return 'hoy'
        elif 'ayer' in mensaje_lower:
            return 'ayer'
        elif 'semana' in mensaje_lower:
            return 'semana'
        elif 'mes' in mensaje_lower:
            return 'mes'
        return None

    def filtrar_por_periodo(self, df: pd.DataFrame, periodo: str) -> pd.DataFrame:
        """Filtra el dataframe según el período."""
        if periodo == 'ultimo_mes':
            mes_max = df['mes'].max()
            return df[df['mes'] == mes_max]
        elif periodo == 'ultimo_trimestre':
            trim_max = df['trimestre'].max()
            return df[df['trimestre'] == trim_max]
        return df

    def responder(self, mensaje: str, id_comercio: Optional[str] = None) -> ChatResponse:
        """Genera una respuesta basada en la pregunta del usuario."""

        intencion, mensaje_lower = self.detectar_intencion(mensaje)
        comercio = self.extraer_comercio(mensaje)
        periodo = self.extraer_periodo(mensaje)

        # Filtrar por comercio si se especifica
        df_filtrado = self.df.copy()
        if comercio:
            df_filtrado = df_filtrado[df_filtrado['nombre_comercio'] == comercio]

        if periodo:
            df_filtrado = self.filtrar_por_periodo(df_filtrado, periodo)

        # Generar respuesta según intención
        respuestas = {
            'ventas_totales': self._resp_ventas_totales(df_filtrado, comercio, periodo),
            'ticket_promedio': self._resp_ticket_promedio(df_filtrado, comercio, periodo),
            'transacciones_count': self._resp_transacciones_count(df_filtrado, comercio, periodo),
            'metodo_pago': self._resp_metodo_pago(df_filtrado, comercio),
            'productos_top': self._resp_productos_top(df_filtrado, comercio),
            'tendencias': self._resp_tendencias(df_filtrado, comercio),
            'clientes': self._resp_clientes(df_filtrado, comercio),
            'dia_semana': self._resp_dia_semana(df_filtrado, comercio),
            'hora_pico': self._resp_hora_pico(df_filtrado, comercio),
            'comparacion': self._resp_comparacion(df_filtrado, mensaje_lower),
            'general': self._resp_general(df_filtrado, comercio),
        }

        return respuestas.get(intencion, respuestas['general'])

    def _resp_ventas_totales(self, df: pd.DataFrame, comercio: Optional[str], periodo: Optional[str]) -> ChatResponse:
        total = df['monto_transaccion'].sum()
        count = len(df)

        comercio_str = f"de **{comercio}**" if comercio else "totales"
        periodo_str = self._periodo_str(periodo)

        return ChatResponse(
            respuesta=f"Las ventas {comercio_str} {periodo_str} fueron **${total:,.2f}** en {count:,} transacciones. 💰",
            tipo="ventas",
            datos={"total": round(total, 2), "transacciones": count}
        )

    def _resp_ticket_promedio(self, df: pd.DataFrame, comercio: Optional[str], periodo: Optional[str]) -> ChatResponse:
        promedio = df['monto_transaccion'].mean()
        mediana = df['monto_transaccion'].median()

        comercio_str = f"de **{comercio}**" if comercio else "general"
        periodo_str = self._periodo_str(periodo)

        return ChatResponse(
            respuesta=f"El ticket promedio {comercio_str} {periodo_str} es de **${promedio:.2f}**. La mediana es ${mediana:.2f}. 🧾",
            tipo="ticket_promedio",
            datos={"promedio": round(promedio, 2), "mediana": round(mediana, 2)}
        )

    def _resp_transacciones_count(self, df: pd.DataFrame, comercio: Optional[str], periodo: Optional[str]) -> ChatResponse:
        count = len(df)

        comercio_str = f"en **{comercio}**" if comercio else "totales"
        periodo_str = self._periodo_str(periodo)

        return ChatResponse(
            respuesta=f"Se realizaron **{count:,} transacciones** {comercio_str} {periodo_str}. 📊",
            tipo="conteo",
            datos={"transacciones": count}
        )

    def _resp_metodo_pago(self, df: pd.DataFrame, comercio: Optional[str]) -> ChatResponse:
        metodos = df['metodo_pago'].value_counts()
        total = len(df)

        respuesta = "Los métodos de pago más usados son:\n\n"
        for metodo, cantidad in metodos.head(3).items():
            porcentaje = (cantidad / total) * 100
            respuesta += f"• **{metodo}**: {porcentaje:.1f}% ({cantidad:,} operaciones)\n"

        return ChatResponse(
            respuesta=respuesta + "\n💳 ¿Te gustaría ver más detalles?",
            tipo="metodos_pago",
            datos=metodos.to_dict()
        )

    def _resp_productos_top(self, df: pd.DataFrame, comercio: Optional[str]) -> ChatResponse:
        productos = df.groupby('descripcion_producto_o_servicio')['monto_transaccion'].agg(['sum', 'count']).sort_values('sum', ascending=False)

        comercio_str = f"en **{comercio}**" if comercio else ""

        respuesta = f"Los productos que más ingresos generan {comercio_str} son:\n\n"
        for producto, row in productos.head(5).iterrows():
            respuesta += f"• **{producto}**: ${row['sum']:,.2f} ({int(row['count'])} ventas)\n"

        return ChatResponse(
            respuesta=respuesta,
            tipo="productos_top",
            datos=productos.head(5).to_dict()
        )

    def _resp_tendencias(self, df: pd.DataFrame, comercio: Optional[str]) -> ChatResponse:
        ventas_mensuales = df.groupby('mes')['monto_transaccion'].sum()

        if len(ventas_mensuales) > 1:
            tendencia = "subiendo 📈" if ventas_mensuales.iloc[-1] > ventas_mensuales.iloc[0] else "bajando 📉"
        else:
            tendencia = "estable ➡️"

        comercio_str = f"en **{comercio}**" if comercio else ""

        return ChatResponse(
            respuesta=f"Las ventas {comercio_str} están {tendencia}. El mejor mes fue el mes {ventas_mensuales.idxmax()} con ${ventas_mensuales.max():,.2f}.",
            tipo="tendencias",
            datos=ventas_mensuales.to_dict()
        )

    def _resp_clientes(self, df: pd.DataFrame, comercio: Optional[str]) -> ChatResponse:
        clientes_unicos = df['id_cliente'].nunique()
        clientes_recurrentes = df['id_cliente'].value_counts()
        top_clientes = clientes_recurrentes.head(3)

        comercio_str = f"en **{comercio}**" if comercio else ""

        respuesta = f"Tienes **{clientes_unicos:,} clientes únicos** {comercio_str}.\n\nLos más frecuentes son:\n"
        for cliente_id, compras in top_clientes.items():
            respuesta += f"• Cliente {cliente_id}: {compras} compras\n"

        return ChatResponse(
            respuesta=respuesta,
            tipo="clientes",
            datos={"clientes_unicos": clientes_unicos, "top_clientes": top_clientes.to_dict()}
        )

    def _resp_dia_semana(self, df: pd.DataFrame, comercio: Optional[str]) -> ChatResponse:
        dias = df['dia_semana'].value_counts()
        top_dia = dias.index[0]
        count = dias.iloc[0]

        comercio_str = f"en **{comercio}**" if comercio else ""

        return ChatResponse(
            respuesta=f"El día con más ventas {comercio_str} es **{top_dia}** con {count:,} transacciones. 📅",
            tipo="dia_semana",
            datos=dias.to_dict()
        )

    def _resp_hora_pico(self, df: pd.DataFrame, comercio: Optional[str]) -> ChatResponse:
        horas = df['hora'].value_counts().sort_index()
        hora_pico = horas.idxmax()
        count = horas.max()

        comercio_str = f"en **{comercio}**" if comercio else ""

        return ChatResponse(
            respuesta=f"La hora pico {comercio_str} es a las **{hora_pico}:00** con {count:,} transacciones. ⏰",
            tipo="hora_pico",
            datos=horas.to_dict()
        )

    def _resp_comparacion(self, df: pd.DataFrame, mensaje: str) -> ChatResponse:
        return ChatResponse(
            respuesta="Para hacer comparaciones, necesito que especifiques qué dos períodos o comercios quieres comparar. Por ejemplo: 'Compara las ventas de enero vs febrero' o 'Compara SuperFresh vs ModaMundo'. 📊",
            tipo="comparacion",
            datos={}
        )

    def _resp_general(self, df: pd.DataFrame, comercio: Optional[str]) -> ChatResponse:
        total_ventas = df['monto_transaccion'].sum()
        total_trans = len(df)
        ticket_prom = df['monto_transaccion'].mean()

        comercio_str = f"de **{comercio}**" if comercio else "totales"

        return ChatResponse(
            respuesta=f"Resumen {comercio_str}:\n• Ventas: **${total_ventas:,.2f}**\n• Transacciones: **{total_trans:,}**\n• Ticket promedio: **${ticket_prom:.2f}**\n\n¿Qué te gustaría saber más a detalle? 🤔",
            tipo="resumen",
            datos={"ventas": round(total_ventas, 2), "transacciones": total_trans, "ticket_promedio": round(ticket_prom, 2)}
        )

    def _periodo_str(self, periodo: Optional[str]) -> str:
        """Convierte el período a texto legible."""
        if not periodo:
            return ""
        mapping = {
            'ultimo_mes': 'en el último mes',
            'ultimo_trimestre': 'en el último trimestre',
            'mes_actual': 'este mes',
            'hoy': 'hoy',
            'ayer': 'ayer',
            'semana': 'esta semana',
            'mes': 'este mes',
        }
        return mapping.get(periodo, "")

    def generar_alerta_proactiva(self) -> AlertaProactiva:
        """Genera una alerta proactiva basada en tendencias."""
        # Calcular ventas del mes actual vs anterior
        ventas_mensuales = self.df.groupby('mes')['monto_transaccion'].sum()

        if len(ventas_mensuales) >= 2:
            mes_actual = ventas_mensuales.iloc[-1]
            mes_anterior = ventas_mensuales.iloc[-2]
            cambio = ((mes_actual - mes_anterior) / mes_anterior) * 100

            if cambio > 10:
                return AlertaProactiva(
                    titulo="¡Buenas noticias! 📈",
                    descripcion=f"Tus ventas subieron un {cambio:.1f}% respecto al mes pasado. ¡Sigue así!",
                    tipo="positiva"
                )
            elif cambio < -10:
                return AlertaProactiva(
                    titulo="Alerta de ventas 📉",
                    descripcion=f"Tus ventas bajaron un {abs(cambio):.1f}% respecto al mes pasado. ¿Necesitas ideas para mejorar?",
                    tipo="negativa"
                )

        # Alerta de día pico
        dia_pico = self.df['dia_semana'].value_counts().index[0]
        return AlertaProactiva(
            titulo="Consejo del día 💡",
            descripcion=f"Los {dia_pico}s son tus días con más ventas. Considera hacer promociones especiales ese día.",
            tipo="consejo"
        )


# Inicializar analizador
analizador = AnalizadorNegocio(df_completo)


# ==================== ENDPOINTS ====================

@app.get("/")
async def root():
    """Sirve el index.html"""
    return FileResponse("index.html")


@app.get("/api/health")
async def health():
    """Endpoint de salud para verificar que el servidor está funcionando."""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "datos": {
            "transacciones": len(df_transacciones),
            "clientes": len(df_clientes),
            "comercios": len(df_comercios)
        }
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Endpoint principal para el chatbot.
    Recibe un mensaje del usuario y devuelve una respuesta analítica.
    """
    try:
        respuesta = analizador.responder(request.mensaje, request.id_comercio)
        return respuesta
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error procesando la consulta: {str(e)}")


@app.get("/api/alerta-proactiva")
async def alerta_proactiva():
    """Genera una alerta proactiva basada en tendencias del negocio."""
    return analizador.generar_alerta_proactiva()


@app.get("/api/comercios")
async def get_comercios():
    """Devuelve la lista de comercios disponibles."""
    return df_comercios.to_dict('records')


@app.get("/api/resumen/{id_comercio}")
async def get_resumen(id_comercio: str):
    """Devuelve un resumen completo de un comercio específico."""
    df_comercio = df_completo[df_completo['id_comercio'] == id_comercio]

    if len(df_comercio) == 0:
        raise HTTPException(status_code=404, detail="Comercio no encontrado")

    info_comercio = df_comercios[df_comercios['id_comercio'] == id_comercio].iloc[0]

    # Calcular métricas
    ventas_totales = df_comercio['monto_transaccion'].sum()
    transacciones = len(df_comercio)
    ticket_promedio = df_comercio['monto_transaccion'].mean()
    clientes_unicos = df_comercio['id_cliente'].nunique()

    # Ventas por mes
    ventas_mensuales = df_comercio.groupby('mes')['monto_transaccion'].sum().to_dict()

    # Top productos
    top_productos = df_comercio.groupby('descripcion_producto_o_servicio')['monto_transaccion'].sum().sort_values(ascending=False).head(5).to_dict()

    return {
        "comercio": {
            "id": id_comercio,
            "nombre": info_comercio['nombre_comercio'],
            "rubro": info_comercio['rubro'],
            "ciudad": info_comercio['ciudad']
        },
        "metricas": {
            "ventas_totales": round(ventas_totales, 2),
            "transacciones": transacciones,
            "ticket_promedio": round(ticket_promedio, 2),
            "clientes_unicos": clientes_unicos
        },
        "ventas_mensuales": ventas_mensuales,
        "top_productos": top_productos
    }


@app.get("/api/transacciones")
async def get_transacciones(limit: int = 100, comercio: Optional[str] = None):
    """Devuelve transacciones recientes, opcionalmente filtradas por comercio."""
    df_result = df_transacciones.copy()

    if comercio:
        comercio_info = df_comercios[df_comercios['nombre_comercio'] == comercio]
        if len(comercio_info) > 0:
            id_com = comercio_info.iloc[0]['id_comercio']
            df_result = df_result[df_result['id_comercio'] == id_com]

    return df_result.head(limit).to_dict('records')


# ==================== INICIAR SERVIDOR ====================

if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*60)
    print("🚀 Mi Contador de Bolsillo - Servidor de Testing")
    print("="*60)
    print("\n📍 URLs disponibles:")
    print("   • Frontend: http://localhost:8000")
    print("   • API Docs: http://localhost:8000/docs")
    print("   • Health:   http://localhost:8000/api/health")
    print("\n💡 Ejemplos de preguntas que puedes hacer:")
    print("   • '¿Cuáles son mis ventas totales?'")
    print("   • '¿Cuál es el ticket promedio en SuperFresh?'")
    print("   • '¿Qué métodos de pago usan mis clientes?'")
    print("   • '¿Cuáles son mis productos más vendidos?'")
    print("   • '¿En qué día de la semana vendo más?'")
    print("\n" + "="*60 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8000)
