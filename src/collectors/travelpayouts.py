"""Coletor via Travelpayouts / Aviasales Data API — preço real de mercado
(cache de buscas reais no Aviasales, não é dado fictício).

Substitui a Duffel como fonte de varredura ampla: Duffel exige verificação
de negócio pra sair do modo de teste (inviável pra pessoa física); esse
endpoint é grátis, sem exigência de volume/MAU (isso só se aplica à busca
"ao vivo" deles, não a este endpoint de dados).

Cadastro: https://www.travelpayouts.com/programs/100/tools/api -> pegar o
token (é grátis, não pede cartão).

Limitação honesta: é dado cacheado (até 7 dias) da menor tarifa vista pra
essa combinação, não uma cotação ao vivo garantida — por isso a SerpApi
ainda entra pra conferir de verdade as melhores datas antes de decidir.
"""
from __future__ import annotations

import os
from datetime import date

import requests

from src.collectors.base import Collector
from src.storage.db import PriceQuote

API_URL = "https://api.travelpayouts.com/v1/prices/cheap"


class TravelpayoutsCollector(Collector):
    source_name = "travelpayouts"

    def __init__(self, tenant_id: str):
        super().__init__(tenant_id)
        self.token = os.getenv("TRAVELPAYOUTS_TOKEN")

    @property
    def is_configured(self) -> bool:
        return bool(self.token)

    def fetch(self, origin: str, destination: str, depart_date: date, return_date: date) -> list[PriceQuote]:
        if not self.is_configured:
            return []
        nights = (return_date - depart_date).days
        resp = requests.get(
            API_URL,
            params={
                "origin": origin,
                "destination": destination,
                "depart_date": depart_date.isoformat(),
                "return_date": return_date.isoformat(),
                "currency": "BRL",
                "token": self.token,
            },
            timeout=20,
        )
        if resp.status_code != 200:
            print(f"[{self.source_name}] HTTP {resp.status_code}: {resp.text[:200]}")
            return []
        payload = resp.json()
        if not payload.get("success"):
            return []
        dest_offers = (payload.get("data") or {}).get(destination) or {}
        quotes = []
        for offer in dest_offers.values():
            price_one_adult = offer.get("price")
            if not price_one_adult:
                continue
            # esse endpoint retorna tarifa cacheada por 1 adulto; o resto do
            # sistema trabalha em total-por-casal, então dobramos aqui
            # (aproximação: assume tarifa linear por passageiro, sem taxas
            # fixas por reserva — razoável pra classe econômica).
            price = float(price_one_adult) * 2
            quotes.append(
                self._quote(
                    origin, destination, depart_date, return_date, nights,
                    price, "BRL", offer.get("airline"),
                )
            )
        return quotes
