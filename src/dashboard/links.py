"""Gera link clicável pro Google Flights pra conferência/compra manual.

Não existe API oficial do Google Flights (fechada desde 2018), então isso
NÃO é uma chamada de API — é só montar a URL de busca deles, que aceita uma
query em linguagem natural (`?q=`) e abre a busca já preenchida no navegador.
"""
from __future__ import annotations

from datetime import date
from urllib.parse import quote


def google_flights_url(
    origin_city: str, destination_city: str, depart_date: date, return_date: date | None = None
) -> str:
    query = f"Flights from {origin_city} to {destination_city} on {depart_date.isoformat()}"
    if return_date:
        query += f" through {return_date.isoformat()}"
    return "https://www.google.com/travel/flights?q=" + quote(query)
