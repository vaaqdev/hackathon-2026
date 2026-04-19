import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

np.random.seed(42)
OUTPUT_DIR = "/mnt/user-data/outputs/dataset_deuna"
os.makedirs(OUTPUT_DIR, exist_ok=True)

START_DATE = datetime(2025, 4, 19)
END_DATE   = datetime(2026, 4, 19)
TOTAL_DAYS = (END_DATE - START_DATE).days

COMERCIOS = {
    "COM001": {"nombre":"Tienda La Esquina de Doña Rosa","categoria":"Tienda","ciudad":"Quito","zona":"Norte","apertura":"07:00","cierre":"20:00","hora_open":7,"hora_close":20,"ticket_min":0.50,"ticket_max":8.00,"productos":["Víveres básicos","Snacks y confites","Lácteos y huevos","Bebidas","Granos y harinas","Artículos de limpieza"]},
    "COM002": {"nombre":"Botica Don Jacinto","categoria":"Farmacia","ciudad":"Quito","zona":"Centro","apertura":"08:00","cierre":"21:00","hora_open":8,"hora_close":21,"ticket_min":1.50,"ticket_max":25.00,"productos":["Medicamentos OTC","Antibióticos y receta","Higiene personal","Vitaminas y suplementos","Material de curación","Cosméticos básicos"]},
    "COM003": {"nombre":"Cevichería El Rincón Costeño","categoria":"Restaurante","ciudad":"Guayaquil","zona":"Sur","apertura":"10:00","cierre":"16:00","hora_open":10,"hora_close":16,"ticket_min":3.00,"ticket_max":15.00,"productos":["Ceviche de camarón","Ceviche mixto","Arroz con menestra","Almuerzo del día","Mariscos al vapor","Bebidas y jugos"]},
}

METODOS_PAGO = ["QR Deuna","Pago a Contacto","Link de Pago Deuna"]
CANALES      = ["Presencial","WhatsApp/Redes"]
ESTADOS      = ["Completada","Pendiente","Anulada"]
ESTADO_BASE  = [0.92, 0.04, 0.04]

# ── CLIENTES ─────────────────────────────────────────────────────────────────
N_CLIENTES = 350
segmentos   = ["Frecuente","Ocasional","Nuevo","Inactivo"]
seg_pesos   = [0.25,0.40,0.20,0.15]
vis_seg     = {"Frecuente":(8,20),"Ocasional":(2,7),"Nuevo":(1,3),"Inactivo":(0,1)}
ciudades_c  = ["Quito","Guayaquil","Cuenca"]
cp          = [0.55,0.30,0.15]

cli_ids  = [f"CLI{str(i).zfill(3)}" for i in range(1, N_CLIENTES+1)]
cli_segs = np.random.choice(segmentos, N_CLIENTES, p=seg_pesos)

clientes_data = []
for i,cid in enumerate(cli_ids):
    seg = cli_segs[i]
    v0,v1 = vis_seg[seg]
    clientes_data.append({
        "cliente_id":cid,"segmento":seg,
        "visitas_por_mes":np.random.randint(v0,v1+1),
        "canal_preferido":np.random.choice(["Presencial","WhatsApp/Redes"],p=[0.60,0.40]),
        "rango_edad":np.random.choice(["18-24","25-34","35-44","45-54","55+"]),
        "genero":np.random.choice(["M","F"]),
        "ciudad":np.random.choice(ciudades_c,p=cp),
        "fecha_registro":(START_DATE-timedelta(days=int(np.random.randint(0,730)))).strftime("%Y-%m-%d"),
        "nps_score":int(np.random.randint(0,11)),
    })
df_clientes = pd.DataFrame(clientes_data)
seg_map = dict(zip(df_clientes.cliente_id, df_clientes.segmento))

# ── PESOS DE FECHA ────────────────────────────────────────────────────────────
def build_weights(n):
    w = np.ones(n)
    for d in range(n):
        dt = START_DATE + timedelta(days=d)
        if dt.month == 12: w[d] *= 1.80
        if dt.month == 3:  w[d] *= 0.80
        if dt.weekday()>=5:w[d] *= 1.15
    return w / w.sum()

DATE_W = build_weights(TOTAL_DAYS)

# ── GENERADOR ────────────────────────────────────────────────────────────────
def generar(cid, n=2000):
    info = COMERCIOS[cid]
    rows = []
    day_idx = np.random.choice(TOTAL_DAYS, size=n, p=DATE_W)
    for idx, di in enumerate(sorted(day_idx)):
        fecha = START_DATE + timedelta(days=int(di))
        mes   = fecha.month
        dow   = fecha.weekday()
        finde = dow >= 5

        h0,h1 = info["hora_open"],info["hora_close"]
        if cid=="COM003":
            if np.random.rand()<0.80:
                mt = np.random.randint(12*60, 14*60+31)
            else:
                fuera = list(range(h0*60,12*60))+list(range(14*60+31,h1*60))
                mt = int(np.random.choice(fuera)) if fuera else 12*60
        else:
            mt = np.random.randint(h0*60, h1*60)
        hora_str = f"{mt//60:02d}:{mt%60:02d}"

        pw = 0.55 if finde else 0.35
        canal = np.random.choice(CANALES, p=[1-pw, pw])

        if canal=="Presencial":
            metodo = np.random.choice(METODOS_PAGO, p=[0.70,0.20,0.10])
        else:
            metodo = np.random.choice(METODOS_PAGO, p=[0.05,0.15,0.80])

        if finde and np.random.rand()<0.25:
            metodo="Link de Pago Deuna"; canal="WhatsApp/Redes"

        pc,pp,pa = ESTADO_BASE
        if cid=="COM001" and mes==10: pc,pp,pa = 0.60,0.05,0.35
        elif cid=="COM003" and mes==1: pc,pp,pa = 0.78,0.18,0.04
        estado = np.random.choice(ESTADOS, p=[pc,pp,pa])

        t0,t1 = info["ticket_min"],info["ticket_max"]
        monto  = round(float(np.random.triangular(t0, t0+(t1-t0)*0.35, t1)), 2)
        if mes==12: monto = round(min(monto*1.15, t1), 2)

        cli = np.random.choice(cli_ids)
        seg = seg_map[cli]
        cat = np.random.choice(info["productos"])
        n_i = int(np.random.randint(1,6))

        rows.append({
            "transaccion_id":f"TXN-{cid}-{str(idx+1).zfill(5)}",
            "comercio_id":cid,"comercio_nombre":info["nombre"],
            "fecha":fecha.strftime("%Y-%m-%d"),"hora":hora_str,
            "dia_semana":fecha.strftime("%A"),"mes":fecha.strftime("%B"),
            "trimestre":f"Q{(mes-1)//3+1}",
            "cliente_id":cli,"segmento_cliente":seg,
            "categoria_producto":cat,"n_items":n_i,"monto_usd":monto,
            "metodo_pago":metodo,"estado":estado,"canal":canal,
        })
    return pd.DataFrame(rows)

print("Generando COM001..."); df1=generar("COM001",2000)
print("Generando COM002..."); df2=generar("COM002",2000)
print("Generando COM003..."); df3=generar("COM003",2000)

df_txn = pd.concat([df1,df2,df3],ignore_index=True)
df_txn = df_txn.sample(frac=1,random_state=99).reset_index(drop=True)

# ── COMERCIOS ────────────────────────────────────────────────────────────────
df_com = pd.DataFrame([{
    "comercio_id":k,"nombre":v["nombre"],"categoria":v["categoria"],
    "ciudad":v["ciudad"],"zona":v["zona"],"apertura":v["apertura"],"cierre":v["cierre"]
} for k,v in COMERCIOS.items()])

# ── GUARDAR ───────────────────────────────────────────────────────────────────
df_txn.to_csv(f"{OUTPUT_DIR}/transacciones.csv",     index=False, encoding="utf-8-sig")
df_clientes.to_csv(f"{OUTPUT_DIR}/clientes.csv",     index=False, encoding="utf-8-sig")
df_com.to_csv(f"{OUTPUT_DIR}/comercios.csv",         index=False, encoding="utf-8-sig")

# ── VERIFICACIONES ────────────────────────────────────────────────────────────
oct_c1 = df_txn[(df_txn.comercio_id=="COM001")&(df_txn.mes=="October")]
ene_c3 = df_txn[(df_txn.comercio_id=="COM003")&(df_txn.mes=="January")]
c3_all  = df_txn[df_txn.comercio_id=="COM003"]
c3_pico = c3_all[(c3_all.hora>="12:00")&(c3_all.hora<="14:30")]
dic     = df_txn[df_txn.mes=="December"]
mar     = df_txn[df_txn.mes=="March"]
resto   = df_txn[~df_txn.mes.isin(["December","March"])]
finde   = df_txn[df_txn.dia_semana.isin(["Saturday","Sunday"])]
semana  = df_txn[~df_txn.dia_semana.isin(["Saturday","Sunday"])]

print(f"\n{'='*60}")
print(f"  TOTAL TRANSACCIONES : {len(df_txn):,}")
for c in ["COM001","COM002","COM003"]:
    print(f"    {c}: {(df_txn.comercio_id==c).sum():,}")
print(f"\n  ANOMALÍAS")
print(f"    COM001 Oct - Anuladas   : {(oct_c1.estado=='Anulada').mean()*100:.1f}%  (objetivo 35%)")
print(f"    COM003 Ene - Pendientes : {(ene_c3.estado=='Pendiente').mean()*100:.1f}%  (objetivo 18%)")
print(f"    COM003 Pico 12-14:30    : {len(c3_pico)/len(c3_all)*100:.1f}%  (objetivo 80%)")
print(f"    Dic txn/día vs resto    : {len(dic)/31:.1f} vs {len(resto)/303:.1f}  ratio={len(dic)/31/(len(resto)/303):.2f}x")
print(f"    Mar txn/día vs resto    : {len(mar)/31:.1f}  ratio={len(mar)/31/(len(resto)/303):.2f}x")
print(f"    Link Pago finde/semana  : {(finde.metodo_pago=='Link de Pago Deuna').mean()*100:.1f}% / {(semana.metodo_pago=='Link de Pago Deuna').mean()*100:.1f}%")
print(f"\n  MÉTODOS DE PAGO")
print(df_txn.metodo_pago.value_counts(normalize=True).mul(100).round(1).to_string())
print(f"\n  ESTADOS")
print(df_txn.estado.value_counts(normalize=True).mul(100).round(1).to_string())
print(f"{'='*60}")
print("DATASET GUARDADO OK")
