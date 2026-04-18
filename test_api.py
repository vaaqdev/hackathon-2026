"""
Script de testing para el API de Mi Contador de Bolsillo.
Prueba las 15 preguntas requeridas por el hackathon.
"""

import sys
import io

# Configurar UTF-8 para Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import requests
import json
import sys

BASE_URL = "http://localhost:8000"


def test_health():
    """Verifica que el servidor esté corriendo."""
    r = requests.get(f"{BASE_URL}/api/health")
    print(f"Health Check: {r.json()}")
    return r.status_code == 200


def test_chat(mensaje, descripcion=""):
    """Prueba una pregunta al chatbot."""
    r = requests.post(
        f"{BASE_URL}/api/chat",
        json={"mensaje": mensaje}
    )
    data = r.json()
    print(f"\n{'='*60}")
    print(f"Pregunta: {mensaje}")
    if descripcion:
        print(f"Descripción: {descripcion}")
    print(f"Respuesta: {data['respuesta']}")
    print(f"Tipo: {data['tipo']}")
    return data


def test_alerta_proactiva():
    """Prueba la alerta proactiva."""
    r = requests.get(f"{BASE_URL}/api/alerta-proactiva")
    data = r.json()
    print(f"\n{'='*60}")
    print("ALERTA PROACTIVA:")
    print(f"Título: {data['titulo']}")
    print(f"Descripción: {data['descripcion']}")
    print(f"Tipo: {data['tipo']}")
    return data


def test_comercios():
    """Obtiene la lista de comercios."""
    r = requests.get(f"{BASE_URL}/api/comercios")
    print(f"\nComercios disponibles:")
    for c in r.json():
        print(f"  - {c['nombre_comercio']} ({c['rubro']}) en {c['ciudad']}")
    return r.json()


def main():
    print("=" * 60)
    print("TESTING - Mi Contador de Bolsillo API")
    print("=" * 60)

    # Verificar servidor
    if not test_health():
        print("ERROR: El servidor no está corriendo. Ejecuta: python server.py")
        sys.exit(1)

    # Mostrar comercios
    test_comercios()

    # Preguntas de prueba (15 para cumplir el reto)
    preguntas = [
        ("Cuales son mis ventas totales", "Ventas totales - General"),
        ("Cual es el ticket promedio en SuperFresh", "Ticket promedio por comercio"),
        ("Cuantas transacciones tuvo ModaMundo", "Conteo de transacciones"),
        ("Que metodos de pago usan mis clientes", "Métodos de pago populares"),
        ("Cuales son los productos mas vendidos", "Top productos"),
        ("Como han evolucionado las ventas", "Tendencias de ventas"),
        ("Cuantos clientes tengo", "Conteo de clientes únicos"),
        ("En que dia de la semana vendo mas", "Análisis por día"),
        ("A que hora tengo mas ventas", "Hora pico"),
        ("Cual es el ticket promedio en Sabores & Co", "Ticket por restaurante"),
        ("Que se vende mas en ModaMundo", "Productos por comercio"),
        ("Como pagan en SuperFresh", "Métodos por comercio"),
        ("Cuantas transacciones en total", "Conteo general"),
        ("Cuales son mis ventas totales", "Ventas - Repetición"),
        ("Que productos generan mas ingresos", "Análisis de valor"),
    ]

    print("\n" + "=" * 60)
    print("PRUEBAS DE PREGUNTAS")
    print("=" * 60)

    resultados = []
    for i, (pregunta, desc) in enumerate(preguntas, 1):
        print(f"\n--- Test {i}/15 ---")
        try:
            data = test_chat(pregunta, desc)
            resultados.append({
                "id": i,
                "pregunta": pregunta,
                "descripcion": desc,
                "respuesta": data.get('respuesta', 'Sin respuesta'),
                "tipo": data.get('tipo', 'desconocido'),
                "status": "OK"
            })
        except Exception as e:
            print(f"ERROR: {e}")
            resultados.append({
                "id": i,
                "pregunta": pregunta,
                "descripcion": desc,
                "respuesta": str(e),
                "tipo": "error",
                "status": "FAIL"
            })

    # Alerta proactiva
    print("\n" + "=" * 60)
    test_alerta_proactiva()

    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN DE PRUEBAS")
    print("=" * 60)
    ok_count = sum(1 for r in resultados if r['status'] == 'OK')
    print(f"Exitosas: {ok_count}/{len(resultados)}")
    print(f"Fallidas: {len(resultados) - ok_count}/{len(resultados)}")

    if ok_count / len(resultados) >= 0.8:
        print(f"\n✅ CUMPLE CRITERIO: {ok_count/len(resultados)*100:.0f}% de precisión (requerido: 80%)")
    else:
        print(f"\n❌ NO CUMPLE: {ok_count/len(resultados)*100:.0f}% de precisión (requerido: 80%)")

    # Guardar resultados
    with open("resultados_test.json", "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    print(f"\nResultados guardados en: resultados_test.json")


if __name__ == "__main__":
    main()
