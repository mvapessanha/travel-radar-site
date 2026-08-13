"""Coletor via Kiwi.com (Tequila API).

AVISO: em 2026 a Kiwi fechou o cadastro self-service da Tequila API pra
desenvolvedores novos — hoje é só por convite/parceria. Deixei o coletor
pronto pro caso de você já ter (ou conseguir) acesso, mas não conte com essa
fonte por padrão. A espinha dorsal real do sistema é a Amadeus.
"""
from __future__ import annotations

import os
from datetime import date

import requests

from src.collectors.base import Collector
from src.storage.db import PriceQuote

SEARCH_URL = "https://api.tequila.kiwi.com/v2/search"


class KiwiCollector(Collector):
    source_name = "kiwi"

    def __init__(self, tenant_id: str):
        super().__init__(tenant_id)
        self.api_key = os.getenv("KIWI_API_KEY")

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def fetch(self, origin: str, destination: str, depart_date: date, return_date: date) -> list[PriceQuote]:
        if not self.is_configured:
            return []
        nights = (return_date - depart_date).days
        resp = requests.get(
            SEARCH_URL,
            headers={"apikey": self.api_key},
            params={
                "fly_from": origin,
                "fly_to": destination,
                "date_from": depart_date.strftime("%d/%m/%Y"),
                "date_to": depart_date.strftime("%d/%m/%Y"),
                "return_from": return_date.strftime("%d/%m/%Y"),
                "return_to": return_date.strftime("%d/%m/%Y"),
                "adults": 2,
                "curr": "BRL",
                "limit": 5,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            return []
        data = resp.json().get("data", [])
        quotes = []
        for offer in data:
            price = float(offer["price"])
            airline = ",".join(offer.get("airlines", [])) or None
            quotes.append(
                self._quote(origin, destination, depart_date, return_date, nights, price, "BRL", airline)
            )
        return quotes
