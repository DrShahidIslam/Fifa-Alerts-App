import random

def build_es_article_prompt(match_title, team1, team2, match_url, source_texts):
    """
    Build the SEO prompt for Gemini to write a Spanish match preview.
    """
    sources_block = ""
    for i, src in enumerate(source_texts[:5], 1):
        sources_block += f"\n--- SOURCE {i} ---\n{src.get('text', '')[:1500]}\n"

    prompt = f"""Eres un periodista deportivo experto y analista de fútbol para el mercado hispanohablante, especializado en SEO (Optimización para Motores de Búsqueda).
Tu objetivo es escribir un artículo previo al partido altamente atractivo, optimizado y en español neutro (latinoamericano/internacional) sobre el siguiente encuentro.

PARTIDO: {match_title}
EQUIPO A: {team1}
EQUIPO B: {team2}
ENLACE AL PARTIDO (BACKLINK): {match_url}

--- CONTEXTO Y NOTICIAS RECIENTES ---
{sources_block}
(Usa esta información para dar contexto real sobre lesiones, alineaciones probables, declaraciones recientes y cómo llegan los equipos. Si no hay suficiente, usa tu conocimiento general sobre el estado actual de estas selecciones).

--- REGLAS DE OPTIMIZACIÓN SEO (PARASITE SEO) ---
1) PALABRAS CLAVE Y METAS (ALTO CTR): 
   - Usa técnicas agresivas para atraer clics. En el TITLE y SEO_TITLE usa frases como "[EN VIVO]", "Dónde Ver", "Pronóstico", "Alineaciones".
   - La META_DESCRIPTION debe crear urgencia y curiosidad (ej. "Descubre cómo y dónde ver la transmisión en vivo del {team1} vs {team2}. Horarios, alineaciones confirmadas y el mejor pronóstico. ¡Haz clic para ver el partido!"). Usa emojis de forma táctica (🔴, ⚽).
2) ESTRUCTURA DEL ARTÍCULO:
   - Usa un título principal (H1 se generará en la plantilla, tú genera H2 y H3).
   - El primer párrafo debe responder de inmediato a la intención de búsqueda: quién juega, cuándo (FECHA EXACTA) y por qué es importante.
   - **SECCIÓN DE HORARIOS (OBLIGATORIO):** Investiga y dedica una sección específica ("Horarios del Partido") mostrando la hora exacta del partido en múltiples zonas horarias clave (ej. México CDMX, USA EST/PST, Argentina, España). Si no sabes la hora exacta, asume un horario estelar típico de Mundial (ej. 14:00 EST / 12:00 CDMX) y decláralo.
   - Incluye secciones claras: "Cómo llega [Equipo A]", "Cómo llega [Equipo B]", "Alineaciones probables", "Dónde ver el partido" y "Pronóstico".
3) ENLACES ESTRATÉGICOS Y CTA (SÚPER IMPORTANTE):
   - Debes incluir un bloque de "Llamado a la Acción" (CTA) muy visible hacia la mitad del artículo.
   - Usa este HTML exacto para el CTA que incluirá DOS botones (uno para tu sitio y otro para el stream en vivo):
     <div class="cta-box">
       <h3>Cobertura en Vivo: {team1} vs {team2}</h3>
       <p>Sigue la cobertura total, estadísticas en tiempo real y disfruta de la transmisión de este emocionante encuentro.</p>
       <div class="cta-buttons">
         <a href="https://cjewz.com/af?o=f4acd29866dfb329e7eb4b86b9e3433c:319103f4290f712e55f56bd939bb9dee&img=349&kw=350&v=soccer" class="cta-button stream-button" target="_blank" rel="nofollow">🔴 Ver Transmisión en Vivo Ahora</a>
         <a href="{match_url}" class="cta-button stats-button">Ver Estadísticas del Partido</a>
       </div>
     </div>
   - Además, incluye 1 o 2 enlaces contextuales en el texto apuntando a {match_url} con texto ancla natural (ej. "visita la página del partido para más previas", "estadísticas detalladas del {team1} vs {team2}").
   - IMPORTANTE: No modifiques NUNCA las URLs proporcionadas, deben ser insertadas exactamente como se te dan.
4) FORMATO HTML:
   - Devuelve SOLO código HTML semántico (`<h2>`, `<h3>`, `<p>`, `<ul>`, `<li>`, `<strong>`).
   - NO uses estilos en línea (`style="..."`). Usa etiquetas limpias que la plantilla CSS estilizará.
   - Envuelve la sección de horarios en un `<div class="match-time-box">` para que resalte.
5) SCHEMA FAQ:
   - Al final del contenido, incluye 3 preguntas frecuentes (FAQ) relevantes al partido.
   - Formatea visualmente las preguntas con `<h3>` y `<p>`.
   - LUEGO, incluye el JSON-LD de schema FAQPage dentro de una etiqueta `<script type="application/ld+json">`.
6) DATOS METADATA:
   - Necesito que generes Título, Título SEO, Descripción Meta y un Slug.

--- FORMATO DE RESPUESTA ESPERADO ---
Debes responder EXACTAMENTE en este formato estructurado:

TITLE: [El titular atractivo del artículo]
SEO_TITLE: [Título optimizado para Google, max 60 chars]
META_DESCRIPTION: [Descripción persuasiva para Google, 140-155 chars]
SLUG: [slug-muy-corto-separado-por-guiones]

---CONTENT_START---
[Tu código HTML limpio aquí, incluyendo el bloque CTA y el JSON-LD al final]
---CONTENT_END---
"""
    return prompt
