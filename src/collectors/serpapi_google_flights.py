"""Coletor que retorna preço REAL do Google Voos, via SerpApi.

Por quê não um scraper próprio: o Google Voos não tem API pública (fechada
desde 2018) e detecta/bloqueia automação (CAPTCHA, "tráfego incomum"). Um
scraper caseiro quebraria com frequência e violaria os termos de uso deles.
A SerpApi é uma empresa que roda uma sessão de navegador real contra o
Google Voos e devolve o resultado como JSON — é o jeito certo de fazer
"a busca retornar o valor" sem tentar burlar bloqueio/CAPTCHA.

Cadastro: https://serpapi.com/users/sign_up -> plano grátis dá 100
buscas/mês. Por isso este coletor só é chamado pras poucas datas já
rankeadas como melhores (ver `serpapi_top_n_check` no yaml do tenant) e só
quando o roteiro está com status "active" - pra não estourar a cota.
"""
from __future__ import annotations

import os
from datetime import date

import requests

from src.collectors.base import Collector
from src.storage.db import PriceQuote

SEARCH_URL = "https://serpapi.com/search.json"


class SerpApiGoogleFlightsCollector(Collector):
    source_name = "google_flights_serpapi"

    def __init__(self, tenant_id: str):
        super().__init__(tenant_id)
        self.api_key = os.getenv("SERPAPI_KEY")

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def fetch(self, origin: str, destination: str, depart_date: date, return_date: date) -> list[PriceQuote]:
        if not self.is_configured:
            return []
        nights = (return_date - depart_date).days
        resp = requests.get(
            SEARCH_URL,
            params={
                "engine": "google_flights",
                "departure_id": origin,
                "arrival_id": destination,
                "outbound_date": depart_date.isoformat(),
                "return_date": return_date.isoformat(),
                "currency": "BRL",
                "adults": 2,
                "type": 1,  # ida e volta
                "api_key": self.api_key,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            print(f"[{self.source_name}] HTTP {resp.status_code}: {resp.text[:200]}")
            return []
        data = resp.json()
        candidates = (data.get("best_flights") or []) + (data.get("other_flights") or [])
        quotes = []
        for offer in candidates:
            price = offer.get("price")
            if not price:
                continue
            airline = None
            legs = offer.get("flights") or []
            if legs:
                airline = legs[0].get("airline")
            quotes.append(
                self._quote(origin, destination, depart_date, return_date, nights, float(price), "BRL", airline)
            )
        return quotes
