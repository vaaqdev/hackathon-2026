# Interact2Hack 2026: Mi Contador de Bolsillo (Deuna)

## Resumen del Reto

Deuna busca crear un asistente conversacional (Mi Contador de Bolsillo) para micro-comerciantes ecuatorianos.  El objetivo es  democratizar la inteligencia de negocio, permitiendo a los comerciantes comprender mejor su negocio y tomar decisiones informadas sin necesidad de formación financiera.  El asistente, basado en un dataset sintético de transacciones, debe responder preguntas en lenguaje natural, proporcionando respuestas accionables, precisas y visualmente claras en menos de cinco segundos.

## 1. Nombre del Reto

Mi Contador de Bolsillo — Asistente conversacional de negocio para el comerciante

## 2. Línea del Reto

Inteligencia Artificial

## 3. Problema de Negocio

Los micro-comerciantes no utilizan la información disponible en la app de Deuna debido a la complejidad de los dashboards y reportes. Esto limita la capacidad de Deuna de convertirse en su asesor de confianza, y el dueño del negocio toma decisiones basadas en intuición.

## 4. Usuario o Segmento Objetivo

Dueños de micro-comercios ecuatorianos que usan Deuna como medio de cobro, sin formación contable ni financiera, con preguntas frecuentes sobre ventas, clientes, tendencias y desempeño.

## 5. Contexto y Oportunidad

La madurez de la IA conversacional permite interfaces naturales sobre datos estructurados.  Deuna, con acceso a los datos transaccionales y la relación directa con el usuario, tiene una ventaja competitiva.  Un asistente útil posicionaría a Deuna como el primer asesor financiero conversacional para micro-comercios en Ecuador.

## 6. Objetivo Principal

Construir un agente conversacional funcional que responda al menos 10 tipos de preguntas de negocio sobre un dataset sintético de transacciones, con respuestas correctas, en español natural y en menos de 5 segundos.

## 7. Objetivos Secundarios

*   Incorporar visualizaciones simples (gráficos o tablas) dentro de las respuestas, cuando aporten claridad.
*   Manejar al menos un flujo proactivo donde el asistente alerte al comerciante sobre una tendencia relevante sin que este lo pregunte.

## 8. Pregunta del Reto

¿Cómo podría Deuna construir un asistente conversacional accesible para micro-comerciantes sin formación financiera, considerando que las respuestas deben ser confiables, interpretables y entregadas en segundos sobre datos transaccionales reales?

## 9. Restricciones

*   El asistente debe operar exclusivamente sobre un dataset sintético provisto; no puede consultar fuentes externas ni datos reales de Deuna.
*   Las respuestas deben estar en español neutro, comprensible para un adulto sin formación financiera.
*   El tiempo de respuesta por consulta no debe exceder 5 segundos en la demo.
*   El asistente no puede inventar datos: si la respuesta no está en el dataset, debe indicarlo con claridad.

## 10. Data o Insumos Disponibles

*   Dataset sintético de 3 comercios con 12 meses de historia transaccional (aprox. 2000 transacciones por comercio).
*   Catálogo simulado de clientes con identificadores anónimos y frecuencia de visita.
*   Glosario de términos de negocio en español neutro para orientar las respuestas.
*   Ejemplos de 20 preguntas típicas que los equipos pueden usar como referencia inicial.

## 11.  Qué deben construir, demostrar, prototipar o validar los equipos

Un agente conversacional ejecutable que reciba preguntas en lenguaje natural, consulte el dataset sintético y devuelva respuestas correctas y comprensibles. La solución debe incluir:

*   (a) el agente funcional con al menos 10 tipos de pregunta soportados;
*   (b) una interfaz mínima para interactuar con el agente (chat web o móvil);
*   (c) evidencia de que las respuestas son correctas en al menos 80% de los casos probados; y
*   (d) al menos un ejemplo de alerta proactiva.

## 12. Entregables Esperados

*   Agente conversacional funcional con interfaz de chat.
*   Set de 15 preguntas de prueba con sus respuestas esperadas y obtenidas.
*   Documentación breve del enfoque técnico (arquitectura, modelo, prompts o lógica).
*   Pitch final de 5 minutos con demo en vivo.
*   Resumen ejecutivo de una página.

## 13. Formato de Entrega Final del Equipo

Pitch de 5 minutos con demo en vivo del asistente + repositorio de código + documento técnico breve + tabla de resultados de las 15 preguntas de prueba.

## 14. Criterios de Éxito para Deuna

*   El asistente responde correctamente al menos el 80% de las preguntas de prueba.
*   El tiempo de respuesta promedio es inferior a 5 segundos.
*   Las respuestas son comprensibles sin necesidad de explicación adicional por parte del equipo.

## 15. Qué Evaluará el Jurado

*   Relevancia para el negocio de Deuna y el comerciante.
*   Calidad técnica del agente y precisión de las respuestas.
*   Claridad y naturalidad del lenguaje utilizado.
*   Robustez del manejo de errores y casos borde.
*   Uso adecuado de IA aplicada a un problema concreto.
*   Potencial de implementación real.

## 16. Supuestos

*   El equipo puede usar cualquier modelo LLM disponible (Claude, OpenAI, modelos open source, etc.).
*   Se asume que en producción la respuesta tendría acceso a datos reales vía APIs internas de Deuna; para el reto se usa el dataset sintético.
*   No se requiere despliegue productivo ni infraestructura escalable.