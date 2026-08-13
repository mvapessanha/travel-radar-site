"""Coletor de fallback: NÃO é preço real de mercado.

Gera uma estimativa a partir da pesquisa que fizemos (faixa R$1.040-2.800
ida/volta na rota RJ-Ilhéus, fevereiro historicamente mais barato que
janeiro, fins de semana mais caros). Serve para o dashboard não ficar vazio
antes de você configurar uma API real (Amadeus/Kiwi). Assim que houver
cotações reais no banco, a análise passa a priorizar elas automaticamente.
"""
from __future__ import annotations

from datetime import date

from src.collectors.base import Collector
from src.storage.db import PriceQuote

BASE_ROUND_TRIP_PER_PERSON = {
    1: 1500,  # janeiro
    2: 1250,  # fevereiro (historicamente mais barato nessa rota)
}
WEEKEND_SURCHARGE = 1.12


class SeedEstimateCollector(Collector):
    source_name = "seed_estimate"

    @property
    def is_configured(self) -> bool:
        return True  # sempre disponível como último recurso

    def fetch(self, origin: str, destination: str, depart_date: date, return_date: date) -> list[PriceQuote]:
        nights = (return_date - depart_date).days
        base = BASE_ROUND_TRIP_PER_PERSON.get(depart_date.month, 1400)
        factor = WEEKEND_SURCHARGE if depart_date.weekday() >= 4 else 1.0
        price_per_person = base * factor
        total = round(price_per_person * 2, 2)  # 2 viajantes
        return [
            self._quote(origin, destination, depart_date, return_date, nights, total, "BRL", "ESTIMATIVA")
        ]
