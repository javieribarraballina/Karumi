# Atlas: pitch de 3 minutos

Karumi × Comillas · Track 1 · Javier, Juan, Blanca, Nacho, Andrés

| Tiempo | Quién | Parte |
|---|---|---|
| 0:00–0:30 | Javier | Qué hemos construido |
| 0:30–1:15 | Juan + Nacho | Demo en directo |
| 1:15–1:50 | Andrés | Qué demuestra |
| 1:50–2:30 | Blanca | La parte más débil |
| 2:30–3:00 | Javier | Una semana más |

## Javier: qué hemos construido (0:00–0:30)
"Un agente de demo aterriza en una app que nunca ha visto. Antes de poder enseñar nada, necesita saber dónde está y cómo llegar a otro sitio. Hemos construido Atlas. Le das una URL: explora la app por su cuenta, agrupa las páginas en pantallas y construye un mapa. Las pantallas son nodos y los clics son aristas. Después responde a dos preguntas: ¿dónde estoy? y ¿cómo llego a X?"

## Juan + Nacho: demo en directo (0:30–1:15)
**Juan:** "Mi explorador abre el sitio en un navegador sin interfaz y sigue los enlaces del mismo dominio. Visita como máximo dos páginas por patrón de URL, así que una tienda con mil libros cuesta dos visitas, no mil."

**Nacho** (en directo, con el mapa precalculado y una captura probada de antemano): "Esto es the-internet.herokuapp.com, mapeado en unos quince segundos. Subo una captura que no ha visto y resalta la pantalla. Ahora le pido Checkboxes: aquí están los clics, paso a paso."

## Andrés: qué demuestra (1:15–1:50)
"Hemos medido en dos sitios públicos, con capturas nuevas a otro tamaño de ventana y sin clave de API:
- Mapeo: 12 páginas se convirtieron en 6 pantallas en books.toscrape, y 15 en 14 en the-internet, en 15 a 17 segundos.
- Rutas encontradas desde la pantalla inicial: 5 de 5 y 13 de 13.
- ¿Dónde estoy?: 50% de acierto top-1 y 71% top-3 en the-internet; 17% y 50% en books."

## Blanca: la parte más débil (1:50–2:30)
"Nuestra parte más débil es reconocer páginas que comparten diseño. Todas las páginas de libros se ven igual, así que las huellas de imagen por sí solas aciertan solo un 17%. Atlas necesita el modelo de visión para distinguirlas, y hemos medido sin él. Fusionar fue la otra trampa: las páginas blancas lisas se parecen todas, así que ahora dos páginas se fusionan solo si se ven parecidas y su texto coincide. Atlas tampoco inicia sesión, y las aplicaciones de una sola página cuya URL nunca cambia no se exploran."

## Javier: una semana más (2:30–3:00)
"Con una semana más: medir con el modelo de visión activado, explorar detrás de un login con una cuenta de prueba, hacer clic en botones además de enlaces para las apps de una sola página, y confirmar cada ruta repitiendo sus clics. Ese es el mapa que el agente de Karumi necesita antes de su primera demo."
