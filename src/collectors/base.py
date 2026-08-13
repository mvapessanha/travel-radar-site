"""Interface comum para qualquer fonte de preço de passagem."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime

from src.storage.db import PriceQuote


class Collector(ABC):
    source_name: str = "base"

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """True se as credenciais necessárias estão presentes no ambiente."""

    @abstractmethod
    def fetch(
        self, origin: str, destination: str, depart_date: date, return_date: date
    ) -> list[PriceQuote]:
        """Retorna 0+ cotações para o par de datas informado."""

    def _quote(self, origin, destination, depart_date, return_date, nights, price, currency, airline) -> PriceQuote:
        return PriceQuote(
            tenant_id=self.tenant_id,
            source=self.source_name,
            origin=origin,
            destination=destination,
            depart_date=depart_date,
            return_date=return_date,
            nights=nights,
            price=price,
            currency=currency,
            airline=airline,
            collected_at=datetime.now(),
        )
