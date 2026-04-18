import pandas as pd
import random
from datetime import datetime, timedelta
import os

# Configuración inicial
NUM_TRANSACCIONES = 6000
COMERCIOS = ["COM001", "COM002", "COM003"]
CLIENTES = [f"CLI{str(i).zfill(4)}" for i in range(1, 401)] # CLI0001 a CLI0400
METODOS_PAGO = ["Efectivo", "Transferencia (Deuna)", "Tarjeta de débito", "Tarjeta de crédito"]
PESOS_PAGO = [0.45, 0.35, 0.15, 0.05] # Alta preferencia por efectivo y Deuna en micro-comercios

# Categorías macro, rangos de ticket promedio (USD) y rotación
categorias_generales = [
    {"categoria": "Bebidas y Gaseosas", "rango": (0.50, 3.50), "peso": 0.20},
    {"categoria": "Víveres Básicos", "rango": (1.00, 6.00), "peso": 0.15},
    {"categoria": "Snacks Salados", "rango": (0.40, 2.00), "peso": 0.12},
    {"categoria": "Lácteos y Huevos", "rango": (0.50, 3.00), "peso": 0.12},
    {"categoria": "Cervezas y Licores", "rango": (1.25, 8.00), "peso": 0.10},
    {"categoria": "Agua Embotellada", "rango": (0.40, 1.50), "peso": 0.08},
    {"categoria": "Dulces y Galletas", "rango": (0.25, 1.50), "peso": 0.08},
    {"categoria": "Bebidas Energéticas", "rango": (1.00, 3.00), "peso": 0.05},
    {"categoria": "Limpieza e Higiene", "rango": (0.50, 4.00), "peso": 0.05},
    {"categoria": "Cigarrillos", "rango": (0.25, 5.00), "peso": 0.05}
]

cat_nombres = [item["categoria"] for item in categorias_generales]
cat_pesos = [item["peso"] for item in categorias_generales]
cat_rangos = [item["rango"] for item in categorias_generales]

def generar_fecha_aleatoria(inicio, fin):
    """Genera una fecha y hora aleatoria entre dos fechas."""
    delta = fin - inicio
    segundos_aleatorios = random.randint(0, int(delta.total_seconds()))
    fecha_base = inicio + timedelta(seconds=segundos_aleatorios)
    
    # Forzar la hora para que tenga sentido comercial (7 AM a 9 PM)
    hora_comercial = random.choices(
        population=list(range(7, 22)),
        # Pesos: Picos al mediodía (12-13) y en la tarde/noche (17-19)
        weights=[2, 3, 4, 4, 5, 8, 8, 5, 5, 4, 7, 8, 8, 6, 4],
        k=1
    )[0]
    
    fecha_final = fecha_base.replace(hour=hora_comercial)
    return fecha_final

def generar_dataset():
    fecha_inicio = datetime(2023, 5, 1)
    fecha_fin = datetime(2024, 4, 30) # Un año completo de datos
    
    transacciones = []
    
    print("Generando transacciones...")
    for i in range(NUM_TRANSACCIONES):
        fecha = generar_fecha_aleatoria(fecha_inicio, fecha_fin)
        
        # Producto y monto realista
        idx_cat = random.choices(range(len(categorias_generales)), weights=cat_pesos, k=1)[0]
        min_p, max_p = cat_rangos[idx_cat]
        monto = round(random.uniform(min_p, max_p), 2)
        monto = max(0.25, round(monto * 4) / 4) # Redondeo a cuartos (0.25, 0.50, etc.)
        
        transaccion = {
            "id_transaccion": f"TXN{str(i+1).zfill(6)}",
            "fecha_transaccion": fecha.strftime("%Y-%m-%d"),
            "hora_transaccion": fecha.strftime("%H:%M:%S"),
            "id_comercio": random.choice(COMERCIOS),
            "id_cliente": random.choice(CLIENTES),
            "monto_transaccion": monto,
            "descripcion_producto_o_servicio": cat_nombres[idx_cat],
            "categoria_producto_o_servicio": cat_nombres[idx_cat],
            "metodo_pago": random.choices(METODOS_PAGO, weights=PESOS_PAGO, k=1)[0]
        }
        transacciones.append(transaccion)

    df = pd.DataFrame(transacciones)
    
    # Crear carpeta si no existe
    os.makedirs("dataset", exist_ok=True)
    ruta_archivo = "dataset/transacciones.csv"
    
    df.to_csv(ruta_archivo, index=False)
    print(f"✅ ¡Listo! Se generó el archivo '{ruta_archivo}' con {len(df)} registros.")

if __name__ == "__main__":
    generar_dataset()
    