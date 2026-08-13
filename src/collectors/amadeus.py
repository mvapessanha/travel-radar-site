"""Coletor via Amadeus for Developers (Self-Service Flight Offers Search).

Tier gratuito: https://developers.amadeus.com/ -> "Self-Service APIs" ->
"Flight Offers Search". Crie um app e pegue API Key + API Secret.
"""
from __future__ import annotations

import os
import time
from datetime import date

import requests

from src.collectors.base import Collector
from src.storage.db import PriceQuote

TOKEN_URL = "https://test.api.amadeus.com/v1/security/oauth2/token"
SEARCH_URL = "https://test.api.amadeus.com/v2/shopping/flight-offers"


class AmadeusCollector(Collector):
    source_name = "amadeus"

    def __init__(self, tenant_id: str):
        super().__init__(tenant_id)
        self.client_id = os.getenv("AMADEUS_CLIENT_ID")
        self.client_secret = os.getenv("AMADEUS_CLIENT_SECRET")
        self._token = None
        self._token_expires_at = 0

    @property
    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def _get_token(self) -> str:
        if self._token and time.time() < self._token_expires_at:
            return self._token
        resp = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=20,
        )
        resp.raise_for_status()
        payload = resp.json()
        self._token = payload["access_token"]
        self._token_expires_at = time.time() + payload.get("expires_in", 1700) - 60
        return self._token

    def fetch(self, origin: str, destination: str, depart_date: date, return_date: date) -> list[PriceQuote]:
        if not self.is_configured:
            return []
        token = self._get_token()
        nights = (return_date - depart_date).days
        resp = requests.get(
            SEARCH_URL,
            headers={"Authorization": f"Bearer {token}"},
            params={
                "originLocationCode": origin,
                "destinationLocationCode": destination,
                "departureDate": depart_date.isoformat(),
                "returnDate": return_date.isoformat(),
                "adults": 2,
                "currencyCode": "BRL",
                "max": 5,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            return []
        data = resp.json().get("data", [])
        quotes = []
        for offer in data:
            price = float(offer["price"]["total"])
            airline = (offer.get("validatingAirlineCodes") or [None])[0]
            quotes.append(
                self._quote(origin, destination, depart_date, return_date, nights, price, "BRL", airline)
            )
        return quotes
