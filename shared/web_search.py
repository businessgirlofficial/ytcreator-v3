"""
Busqueda web compartida - YTCreator Studio
=============================================

Wrapper sobre DuckDuckGo (libreria 'ddgs', gratis y sin API key) para
que el Agente 1.1 (Investigador) pueda buscar que se esta publicando
realmente en un nicho antes de pedirle a Groq que sintetice patrones.

Si en el futuro quieres resultados de mas calidad, este es el unico
archivo que cambiarias por un proveedor de pago (Tavily, SerpAPI, etc).
"""

from ddgs import DDGS


def buscar(query: str, max_resultados: int = 8) -> list[dict]:
    """
    Devuelve una lista de resultados:
        [{"titulo": ..., "resumen": ..., "url": ...}, ...]

    No lanza excepcion silenciosamente: si DuckDuckGo falla (rate
    limit, sin internet, etc.) la excepcion sube tal cual para que el
    agente decida como degradarse.
    """
    resultados = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_resultados):
            resultados.append(
                {
                    "titulo": r.get("title", ""),
                    "resumen": r.get("body", ""),
                    "url": r.get("href", ""),
                }
            )
    return resultados
