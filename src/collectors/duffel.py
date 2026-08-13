"""Coletor via Duffel (https://duffel.com) — GDS/NDC/LCC, self-serve.

Entrou no lugar da Amadeus como espinha dorsal: a Amadeus fechou o cadastro
self-service pra devs novos em 17/07/2026 (ver README). A Duffel segue
aceitando cadastro self-serve normalmente; cobra por uso (pricing por busca é
bem barato, tipicamente frações de centavo — não há taxa de reserva porque
este projeto só PESQUISA preço, nunca compra passagem).

Cadastro: https://duffel.com/ -> "Sign up" -> pegue o access token de teste
(sandbox, pra validar que o código funciona) ou de produção (dados reais).
"""
from __future__ import annotations

import os
import time
from datetime import date

import requests

from src.collectors.base import Collector
from src.storage.db import PriceQuote

API_URL = "https://api.duffel.com/air/offer_requests?return_offers=true"
MAX_RETRIES = 3


class DuffelCollector(Collector):
    source_name = "duffel"

    def __init__(self, tenant_id: str):
        super().__init__(tenant_id)
        self.token = os.getenv("DUFFEL_ACCESS_TOKEN")

    @property
    def is_configured(self) -> bool:
        return bool(self.token)

    def fetch(self, origin: str, destination: str, depart_date: date, return_date: date) -> list[PriceQuote]:
        if not self.is_configured:
            return []
        nights = (return_date - depart_date).days
        body = {
            "data": {
                "slices": [
                    {"origin": origin, "destination": destination, "departure_date": depart_date.isoformat()},
                    {"origin": destination, "destination": origin, "departure_date": return_date.isoformat()},
                ],
                "passengers": [{"type": "adult"}, {"type": "adult"}],
                "cabin_class": "economy",
            }
        }
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Duffel-Version": "v2",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        resp = None
        for attempt in range(MAX_RETRIES):
            resp = requests.post(API_URL, json=body, headers=headers, timeout=30)
            if resp.status_code == 429:
                wait = 2 ** (attempt + 1)  # 2s, 4s, 8s
                print(f"[{self.source_name}] rate limit, aguardando {wait}s (tentativa {attempt + 1}/{MAX_RETRIES})")
                time.sleep(wait)
                continue
            break
        if resp is None or resp.status_code not in (200, 201):
            status = resp.status_code if resp else "sem resposta"
            body_preview = resp.text[:200] if resp else ""
            print(f"[{self.source_name}] HTTP {status}: {body_preview}")
            return []
        offers = (resp.json().get("data") or {}).get("offers") or []
        quotes = []
        skipped_currency = 0
        for offer in offers[:10]:  # a busca pode devolver dezenas de ofertas; guarda só as 10 melhores
            price = offer.get("total_amount")
            currency = offer.get("total_currency")
            if not price:
                continue
            if currency != "BRL":
                # o resto do sistema assume BRL (dashboard, alertas); sem conversão de câmbio
                # confiável aqui, é mais seguro descartar do que misturar moeda no orçamento.
                skipped_currency += 1
                continue
            airline = None
            slices = offer.get("slices") or []
            if slices and slices[0].get("segments"):
                airline = (slices[0]["segments"][0].get("marketing_carrier") or {}).get("name")
            quotes.append(
                self._quote(origin, destination, depart_date, return_date, nights, float(price), currency, airline)
            )
        if skipped_currency:
            print(f"[{self.source_name}] {skipped_currency} oferta(s) ignorada(s) por não estar em BRL.")
        return quotes
