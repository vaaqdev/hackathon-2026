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

class ChatMessage(BaseModel):
    role: str  # 'user' o 'assistant'
    content: str

class ChatRequest(BaseModel):
    mensaje: str
    id_comercio: Optional[str] = None
    historial: Optional[List[ChatMessage]] = []  # Historial de conversación

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
        # Almacenamiento temporal de historial por sesión (en producción usar Redis/DB)
        self.historiales: Dict[str, List[Dict]] = {}

    def _get_session_id(self, id_comercio: str) -> str:
        """Genera un ID de sesión único para el historial."""
        return f"session_{id_comercio}"

    def guardar_mensaje_historial(self, id_comercio: str, role: str, content: str):
        """Guarda un mensaje en el historial de la sesión."""
        session_id = self._get_session_id(id_comercio)
        if session_id not in self.historiales:
            self.historiales[session_id] = []
        self.historiales[session_id].append({"role": role, "content": content})
        # AUMENTADO: Guardamos hasta 60 mensajes para tener mucho más contexto sin romper el límite de tokens
        if len(self.historiales[session_id]) > 60:
            self.historiales[session_id] = self.historiales[session_id][-60:]

    def obtener_historial(self, id_comercio: str) -> List[Dict]:
        """Obtiene el historial de la sesión."""
        session_id = self._get_session_id(id_comercio)
        return self.historiales.get(session_id, [])

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

        # === ANÁLISIS TEMPORAL ===

        # 1. Ventas por día de la semana
        ventas_dia_semana = df_comercio.groupby('dia_semana').agg({
            'monto_usd': ['sum', 'count', 'mean']
        }).reset_index()
        ventas_dia_semana.columns = ['dia', 'ventas_total', 'transacciones', 'ticket_promedio']
        ventas_dia_dict = ventas_dia_semana.set_index('dia').to_dict('index')

        # Día con más ventas
        dia_mas_ventas = ventas_dia_semana.loc[ventas_dia_semana['ventas_total'].idxmax(), 'dia'] if len(ventas_dia_semana) > 0 else 'N/A'
        dia_menos_ventas = ventas_dia_semana.loc[ventas_dia_semana['ventas_total'].idxmin(), 'dia'] if len(ventas_dia_semana) > 0 else 'N/A'

        # 2. Análisis por franjas horarias (usando hora_dt que ya está parseada)
        df_comercio['hora_num'] = df_comercio['hora_dt'].dt.hour

        # Definir franjas horarias
        def get_franja(hora):
            if pd.isna(hora):
                return 'Desconocido'
            if 6 <= hora < 12:
                return 'Mañana (6h-12h)'
            elif 12 <= hora < 14:
                return 'Almuerzo (12h-14h)'
            elif 14 <= hora < 18:
                return 'Tarde (14h-18h)'
            elif 18 <= hora < 22:
                return 'Noche (18h-22h)'
            else:
                return 'Madrugada (22h-6h)'

        df_comercio['franja_horaria'] = df_comercio['hora_num'].apply(get_franja)

        ventas_franja = df_comercio.groupby('franja_horaria').agg({
            'monto_usd': ['sum', 'count', 'mean']
        }).reset_index()
        ventas_franja.columns = ['franja', 'ventas_total', 'transacciones', 'ticket_promedio']
        ventas_franja_dict = ventas_franja.set_index('franja').to_dict('index')

        # Mejor franja horaria
        mejor_franja = ventas_franja.loc[ventas_franja['ventas_total'].idxmax(), 'franja'] if len(ventas_franja) > 0 else 'N/A'

        # 3. Análisis por hora específica (top 5 horas)
        ventas_hora = df_comercio.groupby('hora_num').agg({
            'monto_usd': ['sum', 'count']
        }).reset_index()
        ventas_hora.columns = ['hora', 'ventas_total', 'transacciones']
        ventas_hora = ventas_hora.sort_values('ventas_total', ascending=False).head(5)
        horas_pico = ventas_hora.to_dict('records')

        # 4. Comparativa mes vs mes (si hay datos de múltiples meses)
        meses_disponibles = sorted(df_comercio['mes'].unique())
        tendencia_mensual = 'N/A'
        if len(meses_disponibles) >= 2:
            ventas_ultimo_mes = ventas_mensuales_dict.get(meses_disponibles[-1], {}).get('ventas_total', 0)
            ventas_penultimo_mes = ventas_mensuales_dict.get(meses_disponibles[-2], {}).get('ventas_total', 0)
            if ventas_penultimo_mes > 0:
                cambio_pct = ((ventas_ultimo_mes - ventas_penultimo_mes) / ventas_penultimo_mes) * 100
                tendencia_mensual = f"{'+' if cambio_pct > 0 else ''}{cambio_pct:.1f}%"

        # 5. Días del mes con más ventas
        if 'fecha' in df_comercio.columns:
            df_comercio['dia_mes'] = df_comercio['fecha'].dt.day
            ventas_por_dia_mes = df_comercio.groupby('dia_mes')['monto_usd'].sum().sort_values(ascending=False).head(5)
            dias_mas_ventas = ventas_por_dia_mes.to_dict()
        else:
            dias_mas_ventas = {}

        # Ya tenemos datos de clientes en df_completo desde el merge inicial
        genero_dist = df_comercio['genero'].value_counts().to_dict() if 'genero' in df_comercio.columns else {}
        segmento_dist = df_comercio['segmento_cliente'].value_counts().to_dict() if 'segmento_cliente' in df_comercio.columns else {}
        visitas_promedio = df_comercio['visitas_por_mes'].mean() if 'visitas_por_mes' in df_comercio.columns else 0

        # Estados de transacciones
        estados = df_comercio['estado'].value_counts().to_dict()

        # === ANÁLISIS DE PERÍODOS RECIENTES (hoy, ayer, semana, etc.) ===
        from datetime import datetime, timedelta

        # Fecha actual (usamos la fecha más reciente del dataset como "hoy")
        if 'fecha' in df_comercio.columns and len(df_comercio) > 0:
            fecha_max_dataset = df_comercio['fecha'].max()
            fecha_hoy = fecha_max_dataset
            fecha_ayer = fecha_hoy - timedelta(days=1)

            # Ventas de HOY (última fecha en dataset)
            ventas_hoy = df_comercio[df_comercio['fecha'].dt.date == fecha_hoy.date()]
            total_hoy = ventas_hoy['monto_usd'].sum()
            transacciones_hoy = len(ventas_hoy)

            # Ventas de AYER
            ventas_ayer = df_comercio[df_comercio['fecha'].dt.date == fecha_ayer.date()]
            total_ayer = ventas_ayer['monto_usd'].sum()
            transacciones_ayer = len(ventas_ayer)

            # Calcular cambio vs ayer
            cambio_vs_ayer_pct = 0
            if total_ayer > 0:
                cambio_vs_ayer_pct = ((total_hoy - total_ayer) / total_ayer) * 100

            # Esta semana (últimos 7 días desde fecha máxima)
            inicio_semana = fecha_hoy - timedelta(days=6)
            ventas_semana = df_comercio[df_comercio['fecha'] >= inicio_semana]
            total_semana = ventas_semana['monto_usd'].sum()
            transacciones_semana = len(ventas_semana)

            # Semana anterior (7 días antes)
            inicio_semana_ant = fecha_hoy - timedelta(days=13)
            fin_semana_ant = fecha_hoy - timedelta(days=7)
            ventas_semana_ant = df_comercio[(df_comercio['fecha'] >= inicio_semana_ant) & (df_comercio['fecha'] <= fin_semana_ant)]
            total_semana_ant = ventas_semana_ant['monto_usd'].sum()

            cambio_semana_pct = 0
            if total_semana_ant > 0:
                cambio_semana_pct = ((total_semana - total_semana_ant) / total_semana_ant) * 100

            # Este mes (desde el día 1 del mes de fecha_hoy)
            inicio_mes = fecha_hoy.replace(day=1)
            ventas_mes_actual = df_comercio[df_comercio['fecha'] >= inicio_mes]
            total_mes_actual = ventas_mes_actual['monto_usd'].sum()
            transacciones_mes = len(ventas_mes_actual)

            # Mes anterior completo
            import calendar
            mes_ant = fecha_hoy.month - 1 if fecha_hoy.month > 1 else 12
            anio_ant = fecha_hoy.year if fecha_hoy.month > 1 else fecha_hoy.year - 1
            ultimo_dia_mes_ant = calendar.monthrange(anio_ant, mes_ant)[1]
            inicio_mes_ant = datetime(anio_ant, mes_ant, 1)
            fin_mes_ant = datetime(anio_ant, mes_ant, ultimo_dia_mes_ant)

            ventas_mes_ant = df_comercio[(df_comercio['fecha'] >= inicio_mes_ant) & (df_comercio['fecha'] <= fin_mes_ant)]
            total_mes_ant = ventas_mes_ant['monto_usd'].sum()

            cambio_mes_pct = 0
            if total_mes_ant > 0:
                cambio_mes_pct = ((total_mes_actual - total_mes_ant) / total_mes_ant) * 100

            # Últimas 24 horas de transacciones (para mostrar actividad reciente)
            ultimas_24h = df_comercio[df_comercio['fecha'] >= (fecha_hoy - timedelta(days=1))]

            analisis_reciente = {
                "fecha_referencia": fecha_hoy.strftime("%Y-%m-%d"),
                "hoy": {
                    "ventas": round(total_hoy, 2),
                    "transacciones": int(transacciones_hoy),
                    "fecha": fecha_hoy.strftime("%Y-%m-%d")
                },
                "ayer": {
                    "ventas": round(total_ayer, 2),
                    "transacciones": int(transacciones_ayer),
                    "fecha": fecha_ayer.strftime("%Y-%m-%d")
                },
                "comparacion_hoy_vs_ayer": {
                    "diferencia_usd": round(total_hoy - total_ayer, 2),
                    "cambio_porcentaje": round(cambio_vs_ayer_pct, 1)
                },
                "esta_semana": {
                    "ventas": round(total_semana, 2),
                    "transacciones": int(transacciones_semana),
                    "dias_contados": 7
                },
                "semana_anterior": {
                    "ventas": round(total_semana_ant, 2)
                },
                "comparacion_semanal": {
                    "cambio_porcentaje": round(cambio_semana_pct, 1)
                },
                "este_mes": {
                    "ventas": round(total_mes_actual, 2),
                    "transacciones": int(transacciones_mes)
                },
                "mes_anterior": {
                    "ventas": round(total_mes_ant, 2)
                },
                "comparacion_mensual": {
                    "cambio_porcentaje": round(cambio_mes_pct, 1)
                },
                "ultimas_24h_transacciones": len(ultimas_24h)
            }
        else:
            analisis_reciente = {
                "nota": "No hay datos de fechas disponibles"
            }

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
            "analisis_temporal": {
                "ventas_por_dia_semana": ventas_dia_dict,
                "dia_mas_ventas": dia_mas_ventas,
                "dia_menos_ventas": dia_menos_ventas,
                "ventas_por_franja_horaria": ventas_franja_dict,
                "mejor_franja_horaria": mejor_franja,
                "horas_pico": horas_pico,
                "tendencia_mensual": tendencia_mensual,
                "meses_disponibles": meses_disponibles,
                "dias_mes_mas_ventas": dias_mas_ventas
            },
            "clientes": {
                "distribucion_genero": genero_dist,
                "distribucion_segmento": segmento_dist,
                "visitas_promedio_por_mes": round(visitas_promedio, 1)
            },
            "estados_transacciones": estados,
            "analisis_reciente": analisis_reciente
        }

    def generar_contexto_ia(self, datos: Dict) -> str:
        m = datos['metricas']
        c = datos['comercio']
        cl = datos['clientes']
        tmp = datos.get('analisis_temporal', {})
        rec = datos.get('analisis_reciente', {})

        contexto = f"""=== ESTADO FINANCIERO Y DATOS DEL NEGOCIO ===
Nombre del Comercio: {c['nombre']}
Categoría: {c['categoria']}
Ubicación: {c['ciudad']} - {c['zona']}

=== SALDO Y MÉTRICAS CLAVE ===
• SALDO ACTUAL GENERADO (Total de ventas completadas): ${m['saldo_actual']:,.2f}
• Total de transacciones realizadas: {m['total_transacciones']:,}
• Ticket promedio por compra: ${m['ticket_promedio']:.2f}
• Clientes únicos atendidos: {m['clientes_unicos']}

=== VENTAS RECIENTES (Períodos Actuales) ===
"""

        # Agregar datos de períodos recientes si existen
        if 'hoy' in rec:
            hoy = rec['hoy']
            ayer = rec['ayer']
            comp = rec.get('comparacion_hoy_vs_ayer', {})
            sem = rec.get('esta_semana', {})
            mes = rec.get('este_mes', {})

            contexto += f"""📊 HOY ({hoy.get('fecha', 'N/A')}):
• Ventas: ${hoy.get('ventas', 0):,.2f}
• Transacciones: {hoy.get('transacciones', 0)}

📊 AYER ({ayer.get('fecha', 'N/A')}):
• Ventas: ${ayer.get('ventas', 0):,.2f}
• Transacciones: {ayer.get('transacciones', 0)}

📈 Comparación Hoy vs Ayer:
• Diferencia: ${comp.get('diferencia_usd', 0):,.2f}
• Cambio: {'+' if comp.get('cambio_porcentaje', 0) > 0 else ''}{comp.get('cambio_porcentaje', 0)}%

📅 ESTA SEMANA (últimos 7 días):
• Ventas: ${sem.get('ventas', 0):,.2f}
• Transacciones: {sem.get('transacciones', 0)}
• Cambio vs semana anterior: {'+' if rec.get('comparacion_semanal', {}).get('cambio_porcentaje', 0) > 0 else ''}{rec.get('comparacion_semanal', {}).get('cambio_porcentaje', 0)}%

📆 ESTE MES:
• Ventas: ${mes.get('ventas', 0):,.2f}
• Transacciones: {mes.get('transacciones', 0)}
• Cambio vs mes anterior: {'+' if rec.get('comparacion_mensual', {}).get('cambio_porcentaje', 0) > 0 else ''}{rec.get('comparacion_mensual', {}).get('cambio_porcentaje', 0)}%

"""
        else:
            contexto += "• No hay datos de períodos recientes disponibles\n\n"

        contexto += """=== ANÁLISIS TEMPORAL Y PATRONES DE VENTA ===

📅 POR DÍA DE LA SEMANA:
"""
        for dia, vals in tmp.get('ventas_por_dia_semana', {}).items():
            contexto += f"• {dia}: ${vals.get('ventas_total', 0):,.2f} ({vals.get('transacciones', 0)} transacciones, ticket promedio ${vals.get('ticket_promedio', 0):.2f})\n"

        contexto += f"\n🕐 MEJOR DÍA: {tmp.get('dia_mas_ventas', 'N/A')} | DÍA MÁS BAJO: {tmp.get('dia_menos_ventas', 'N/A')}\n"

        contexto += f"\n⏰ POR FRANJA HORARIA:\n"
        for franja, vals in tmp.get('ventas_por_franja_horaria', {}).items():
            contexto += f"• {franja}: ${vals.get('ventas_total', 0):,.2f} ({vals.get('transacciones', 0)} transacciones)\n"

        contexto += f"\n🎯 MEJOR FRANJA HORARIA: {tmp.get('mejor_franja_horaria', 'N/A')}\n"

        contexto += f"\n🔥 TOP HORAS PICO:\n"
        for hora_data in tmp.get('horas_pico', [])[:3]:
            hora_str = f"{int(hora_data.get('hora', 0)):02d}:00"
            contexto += f"• {hora_str}: ${hora_data.get('ventas_total', 0):,.2f} ({hora_data.get('transacciones', 0)} ventas)\n"

        contexto += f"\n📈 TENDENCIA MENSUAL: {tmp.get('tendencia_mensual', 'N/A')}\n"
        contexto += f"📊 Meses disponibles en datos: {', '.join(tmp.get('meses_disponibles', []))}\n"

        contexto += f"\n=== VENTAS MENSUALES ===\n"
        for mes, vals in datos.get('ventas_mensuales', {}).items():
            contexto += f"• {mes}: ${vals.get('ventas_total', 0):,.2f} ({vals.get('transacciones', 0)} transacciones)\n"

        contexto += f"\n=== TOP CATEGORÍAS DE PRODUCTOS ===\n"
        for i, prod in enumerate(datos['productos_top'], 1):
            contexto += f"{i}. {prod['producto']}: ${prod['total_monto']:,.2f} ({prod['cantidad_ventas']} ventas)\n"

        contexto += f"\n=== MÉTODOS DE PAGO ===\n"
        metodos = datos.get('metodos_pago', {}).get('conteo', {})
        for metodo, cantidad in metodos.items():
            pct = datos.get('metodos_pago', {}).get('porcentajes', {}).get(metodo, 0)
            contexto += f"• {metodo}: {cantidad} transacciones ({pct}%)\n"

        contexto += f"\n=== PERFIL DE CLIENTES ===\n"
        contexto += f"• Visitas promedio por mes: {cl.get('visitas_promedio_por_mes', 0)}\n"
        contexto += f"• Distribución por género: {cl.get('distribucion_genero', {})}\n"
        contexto += f"• Segmentos de clientes: {cl.get('distribucion_segmento', {})}\n"

        contexto += f"\n=== ESTADOS DE TRANSACCIONES ===\n"
        for estado, cantidad in datos.get('estados_transacciones', {}).items():
            contexto += f"• {estado}: {cantidad}\n"

        return contexto

    def consultar_groq(self, mensaje: str, contexto: str, historial: List[Dict] = None) -> str:
        if not GROQ_API_KEY:
            return "Error: GROQ_API_KEY no configurada."

        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {GROQ_API_KEY}"}

        # PROMPT ACTUALIZADO PARA MARKDOWN Y GRÁFICAS VISUALES
        system_prompt = """Eres "Mi Contador de Bolsillo", el asistente financiero de Deuna.

TU PERSONALIDAD:
- Amigable, cálido, como un amigo que sabe de números.
- Usa español ecuatoriano natural: saluda con "¿Cómo estás?", "¿Qué tal tu día?", "¡Qué bueno verte!"
- Sé cálido, cercano y empático. Entiende que el usuario NO tiene formación financiera
- Usa emojis ocasionalmente para darle vida a las respuestas (máximo 2-3 por mensaje)

DATOS QUE TIENES DISPONIBLES:
- VENTAS DE HOY Y AYER con comparación directa (monto exacto y cambio %)
- Ventas de esta semana vs semana anterior (comparación %)
- Ventas del mes actual vs mes anterior (comparación %)
- Ventas por día de la semana (lunes a domingo) - para responder "¿qué día vendo más?"
- Franjas horarias (mañana, almuerzo, tarde, noche) - para responder "¿a qué hora tengo más ventas?"
- Horas pico específicas - para recomendar mejores horarios
- Tendencia mensual - para comparar si estás creciendo o bajando
- Productos más vendidos y categorías
- Métodos de pago más usados
- Perfil de clientes (género, segmento)

FORMATO OBLIGATORIO (MARKDOWN Y GRÁFICAS):
- TIENES PERMITIDO Y DEBES usar Markdown.
- Usa **negritas** para resaltar montos o ideas clave.
- Usa listas con viñetas (-) para separar puntos.
- SI TE PIDEN GRÁFICAS O COMPARATIVAS, no puedes generar imágenes, pero DEBES usar "Gráficas de Barras en Texto" o Tablas de Markdown.
  Ejemplo de gráfica de barras de texto:
  Lunes:   ████████ (80 ventas)
  Martes:  ████ (40 ventas)
  Jueves:  ███████████ (110 ventas)
- Usa Tablas Markdown para resúmenes financieros si te piden mucho detalle.

PARA PREGUNTAS DE VENTAS RECIENTES:
- Si preguntan "¿cuánto vendí hoy?" → Responde con el monto exacto de HOY y compara con ayer
- Si preguntan "¿cómo me fue hoy?" → Menciona ventas de hoy, comparación con ayer (subió/bajó X%)
- Si preguntan "¿vendí más que ayer?" → Compara directamente hoy vs ayer con porcentaje
- Si preguntan "¿cuánto he vendido esta semana?" → Usa los datos de "esta semana"
- Si preguntan "¿cómo va el mes?" → Usa ventas del mes actual vs mes anterior
- Si dicen "hoy vendí poco" → Responde con los datos reales y contexto (si es día bajo o normal)

PARA PREGUNTAS DE TIEMPO/AGENDA:
- Si preguntan "¿qué día vendo más?" → Responde con el día de la semana con más ventas (con gráfica de barras si es posible)
- Si preguntan "¿a qué hora debo abrir?" → Usa la franja horaria con más ventas
- Si preguntan "¿cuándo debería estar atento?" → Menciona horas pico y días más fuertes
- Si preguntan comparaciones entre meses → Usa la tendencia mensual (con tabla si es posible)

REGLAS:
- Responde claro y directo.
- Basa tu respuesta en el CONTEXTO DEL NEGOCIO. Si no sabes algo, dilo.
- SI NO SABES algo, di: "Para eso necesitaría revisar contigo otros datos, ¿te parece si vemos..."
- NUNCA inventes números. Si no hay dato, indícalo claramente.
- Usa únicamente la información del NEGOCIO proporcionada
- Si la pregunta no tiene que ver con el negocio, responde amablemente redirigiendo al tema"""

        # Construir mensajes con historial
        messages = [{"role": "system", "content": system_prompt}]

        # Agregar contexto de negocio como mensaje del sistema adicional
        messages.append({
            "role": "system",
            "content": f"=== DATOS ACTUALES DEL NEGOCIO ===\n{contexto}\n=== FIN DE DATOS ==="
        })

        # Agregar historial previo si existe
        if historial and len(historial) > 0:
            messages.extend(historial)

        # Agregar mensaje actual del usuario
        messages.append({"role": "user", "content": mensaje})

        data = {
            "model": GROQ_MODEL,
            "messages": messages,
            "max_tokens": 1000, # Aumentado para permitir tablas y gráficas grandes
            "temperature": 0.7,
            "top_p": 0.9,
            "frequency_penalty": 0.3,
            "presence_penalty": 0.2
        }

        try:
            r = requests.post(GROQ_API_URL, headers=headers, json=data, timeout=30)
            r.raise_for_status()
            respuesta = r.json()["choices"][0]["message"]["content"]
            return respuesta
        except Exception as e:
            return f"Ups, tuve un problemita técnico 😅 ¿Me lo preguntas de nuevo? Error: {str(e)}"

    def responder(self, mensaje: str, id_comercio: Optional[str] = None, historial: List[ChatMessage] = None) -> ChatResponse:
        if not id_comercio:
            return ChatResponse(respuesta="¡Hey! Primero selecciona un comercio para poder ayudarte mejor 👆", tipo="error")

        datos = self.get_comercio_data(id_comercio)
        if not datos:
            return ChatResponse(respuesta="No encontré ese comercio. ¿Está bien el ID? 🤔", tipo="error")

        # Obtener historial de sesión o usar el enviado desde frontend
        historial_sesion = []
        if historial and len(historial) > 0:
            historial_sesion = [{"role": m.role, "content": m.content} for m in historial]
        else:
            historial_sesion = self.obtener_historial(id_comercio)

        # Guardar mensaje del usuario
        self.guardar_mensaje_historial(id_comercio, "user", mensaje)

        # Generar respuesta
        respuesta = self.consultar_groq(mensaje, self.generar_contexto_ia(datos), historial_sesion)

        # Guardar respuesta del asistente
        self.guardar_mensaje_historial(id_comercio, "assistant", respuesta)

        return ChatResponse(respuesta=respuesta, tipo="ia_response")


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

@app.get("/styles.css")
async def get_styles(): return FileResponse(str(BASE_DIR / "public" / "style.css"))

@app.get("/script.js")
async def get_script(): return FileResponse(str(BASE_DIR / "public" / "script.js"))


@app.get("/api/comercios")
async def get_comercios():
    comercios_list = [analizador.get_comercio_data(c['comercio_id']) for _, c in df_comercios.iterrows() if analizador.get_comercio_data(c['comercio_id'])]
    return {"comercios": comercios_list, "total": len(comercios_list)}

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    return analizador.responder(request.mensaje, request.id_comercio, request.historial)


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