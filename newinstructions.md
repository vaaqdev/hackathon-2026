¡Entendido! Para que la IA tenga mucha más memoria (historial), use Markdown de forma nativa y pueda "dibujar" gráficas, tenemos que hacer ajustes tanto en tu Backend (Python) como en tu Frontend (HTML/JS).

Como los modelos de texto (como Llama-3) no generan archivos de imagen (PNG o JPG) directamente, la mejor forma de que la IA te muestre "gráficas" es usar tablas de Markdown y gráficos de barras hechos con caracteres/emojis. Con una pequeña librería en el frontend, esto se verá increíble.

Aquí tienes los pasos y los archivos actualizados:

1. El Backend (Python / FastAPI)
He modificado tu código para:

Aumentar el historial: Pasó de 20 a 60 mensajes. (Ojo: no lo subimos a 1000 porque el modelo de Groq tiene un límite de "tokens" por conversación y si le mandas demasiado texto de golpe, dará error).

Actualizar el system_prompt: Ahora la IA sabe que DEBE usar Markdown y sabe cómo crear "gráficas visuales" usando caracteres.

Reemplaza tu archivo Python con este:

Python
import sys
import io
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

# Configurar UTF-8 para Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Cargar variables de entorno
load_dotenv()

# Obtener el directorio base del proyecto
BASE_DIR = Path(__file__).parent.resolve()

# Configuración de Groq API
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant" 

app = FastAPI(
    title="Mi Contador de Bolsillo - API",
    description="API híbrida con soporte Markdown e historial extendido.",
    version="3.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "public")), name="static")

# Rutas de datasets
DATASET_DIR = Path("dataset")
TRANSACCIONES_CSV = DATASET_DIR / "transacciones.csv"
CLIENTES_CSV = DATASET_DIR / "clientes.csv"
COMERCIOS_CSV = DATASET_DIR / "comercios.csv"

print("📊 Cargando datasets...")
df_transacciones = pd.read_csv(TRANSACCIONES_CSV)
df_clientes = pd.read_csv(CLIENTES_CSV)
df_comercios = pd.read_csv(COMERCIOS_CSV)

df_transacciones['fecha'] = pd.to_datetime(df_transacciones['fecha'])
df_transacciones['hora_dt'] = pd.to_datetime(df_transacciones['hora'], format='%H:%M', errors='coerce')

df_completo = df_transacciones.merge(
    df_comercios[['comercio_id', 'nombre', 'categoria', 'ciudad', 'zona']],
    on='comercio_id',
    how='left'
).merge(
    df_clientes[['cliente_id', 'rango_edad', 'genero', 'visitas_por_mes', 'segmento', 'canal_preferido', 'nps_score']],
    on='cliente_id',
    how='left'
)
print(f"✅ Datos cargados: {len(df_transacciones):,} transacciones.")

# ==================== MODELOS ====================
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    mensaje: str
    id_comercio: Optional[str] = None
    historial: Optional[List[ChatMessage]] = []

class ChatResponse(BaseModel):
    respuesta: str
    tipo: str
    datos: Optional[Dict] = None

# ==================== MOTOR DE ANÁLISIS ====================
class AnalizadorNegocio:
    def __init__(self, df: pd.DataFrame, df_clientes: pd.DataFrame, df_comercios: pd.DataFrame):
        self.df = df
        self.df_clientes = df_clientes
        self.df_comercios = df_comercios
        self.historiales: Dict[str, List[Dict]] = {}

    def _get_session_id(self, id_comercio: str) -> str:
        return f"session_{id_comercio}"

    def guardar_mensaje_historial(self, id_comercio: str, role: str, content: str):
        session_id = self._get_session_id(id_comercio)
        if session_id not in self.historiales:
            self.historiales[session_id] = []
        self.historiales[session_id].append({"role": role, "content": content})
        
        # AUMENTADO: Guardamos hasta 60 mensajes para tener mucho más contexto sin romper el límite de tokens de Llama 3
        if len(self.historiales[session_id]) > 60:
            self.historiales[session_id] = self.historiales[session_id][-60:]

    def obtener_historial(self, id_comercio: str) -> List[Dict]:
        session_id = self._get_session_id(id_comercio)
        return self.historiales.get(session_id, [])

    def get_comercio_data(self, id_comercio: str) -> Dict:
        # [AQUÍ VA EXACTAMENTE TU MISMO CÓDIGO DEL MÉTODO get_comercio_data QUE YA TIENES]
        # (Lo omito para no hacer la respuesta gigante, pero pega tu código intacto aquí)
        pass 

    def generar_contexto_ia(self, datos: Dict) -> str:
        # [AQUÍ VA EXACTAMENTE TU MISMO CÓDIGO DEL MÉTODO generar_contexto_ia QUE YA TIENES]
        pass

    def consultar_groq(self, mensaje: str, contexto: str, historial: List[Dict] = None) -> str:
        if not GROQ_API_KEY: return "Error: GROQ_API_KEY no configurada."
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {GROQ_API_KEY}"}

        # PROMPT ACTUALIZADO PARA MARKDOWN Y GRÁFICAS VISUALES
        system_prompt = """Eres "Mi Contador de Bolsillo", el asistente financiero de Deuna.
TU PERSONALIDAD:
- Amigable, cálido, como un amigo que sabe de números.

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

REGLAS:
- Responde claro y directo.
- Basa tu respuesta en el CONTEXTO DEL NEGOCIO. Si no sabes algo, dilo.
"""
        messages = [{"role": "system", "content": system_prompt}]
        messages.append({
            "role": "system",
            "content": f"=== DATOS ACTUALES DEL NEGOCIO ===\n{contexto}\n=== FIN DE DATOS ==="
        })
        if historial and len(historial) > 0:
            messages.extend(historial)
        messages.append({"role": "user", "content": mensaje})

        data = {
            "model": GROQ_MODEL,
            "messages": messages,
            "max_tokens": 1000, # Aumentado un poco para permitir tablas grandes
            "temperature": 0.7,
        }

        try:
            r = requests.post(GROQ_API_URL, headers=headers, json=data, timeout=30)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"Ups, tuve un problemita técnico 😅 Error: {str(e)}"

    def responder(self, mensaje: str, id_comercio: Optional[str] = None, historial: List[ChatMessage] = None) -> ChatResponse:
        if not id_comercio: return ChatResponse(respuesta="¡Hey! Selecciona un comercio primero.", tipo="error")
        datos = self.get_comercio_data(id_comercio)
        if not datos: return ChatResponse(respuesta="No encontré ese comercio.", tipo="error")

        historial_sesion = [{"role": m.role, "content": m.content} for m in historial] if historial else self.obtener_historial(id_comercio)
        
        self.guardar_mensaje_historial(id_comercio, "user", mensaje)
        respuesta = self.consultar_groq(mensaje, self.generar_contexto_ia(datos), historial_sesion)
        self.guardar_mensaje_historial(id_comercio, "assistant", respuesta)

        return ChatResponse(respuesta=respuesta, tipo="ia_response")

# [EL RESTO DE TUS ENDPOINTS DE FASTAPI QUEDAN EXACTAMENTE IGUAL]
2. Actualizaciones en el Frontend (HTML, CSS y JS)
Para que el frontend entienda las tablas, las negritas y las gráficas visuales en Markdown que te mandará la IA, usaremos una librería ligerita llamada marked.js.

A) En tu index.html:
Agrega esta línea de script justo antes de tu styles.css (en el <head>):

HTML
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
B) En tu styles.css:
Agrega estas reglas al final de tu CSS para que las tablas y listas que genere la IA se vean bonitas dentro de la burbuja de chat:

CSS
/* ESTILOS PARA EL MARKDOWN DEL CHAT */
.message.bot p { margin-bottom: 10px; }
.message.bot p:last-child { margin-bottom: 0; }
.message.bot strong { color: var(--deuna-purple); font-weight: 700; }
.message.bot ul, .message.bot ol { padding-left: 20px; margin-bottom: 10px; }
.message.bot table { width: 100%; border-collapse: collapse; margin-top: 10px; margin-bottom: 10px; font-size: 13px; }
.message.bot th, .message.bot td { border: 1px solid var(--glass-border); padding: 8px; text-align: left; }
.message.bot th { background-color: var(--deuna-purple-light); color: var(--deuna-purple-rich); font-weight: 600; }
.message.bot pre { background: var(--bg-secondary); padding: 10px; border-radius: 8px; overflow-x: auto; font-family: monospace; }
C) En tu script.js:
Busca la función appendMessage (casi al final del archivo) y reemplázala por esta para que procese el Markdown solo cuando la IA hable:

JavaScript
function appendMessage(text, sender, chatArea, id = null) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${sender}`;
    if (id) msgDiv.id = id;
    
    // Si el mensaje es del bot y NO es el ícono de carga, convertimos de Markdown a HTML
    if (sender === 'bot' && !text.includes('fa-circle-notch')) {
        // Configuramos marked para que rompa líneas de forma natural
        marked.setOptions({ breaks: true });
        msgDiv.innerHTML = marked.parse(text);
    } else {
        // Si es el usuario o el loader, va como texto plano
        msgDiv.textContent = text;
        // Excepción para el HTML del loader
        if(text.includes('fa-circle-notch')) msgDiv.innerHTML = text;
    }
    
    chatArea.appendChild(msgDiv);
    
    // Usar scroll behavior smooth para que baje fluidamente
    chatArea.scrollTo({
        top: chatArea.scrollHeight,
        behavior: 'smooth'
    });
}
¡Con esto estás listo! Ahora, si le dices a la IA "Muéstrame una gráfica de mis ventas de esta semana", ella te generará algo similar a un gráfico de barras directamente en el chat y resaltará lo importante en negritas.