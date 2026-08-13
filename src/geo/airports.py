"""Busca de país/cidade/aeroporto usando o dataset aberto da OurAirports
(domínio público, https://ourairports.com/data/, ~86 mil aeródromos).

Isso cobre TODOS os países e praticamente toda cidade do mundo com aeroporto
com serviço regular — sem precisar de API paga de geocoding.
"""
from __future__ import annotations

import csv
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def _normalize(text: str) -> str:
    """Remove acentos e baixa a caixa, pra 'Ilheus' bater com 'Ilhéus'."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()

REF_DIR = Path(__file__).resolve().parents[2] / "data" / "reference"
AIRPORTS_CSV = REF_DIR / "airports.csv"
COUNTRIES_CSV = REF_DIR / "countries.csv"

# aeroportos "reais" pra fins de passagem comercial (exclui heliponto, pista de fazenda etc.)
COMMERCIAL_TYPES = {"large_airport", "medium_airport", "small_airport"}
TYPE_RANK = {"large_airport": 0, "medium_airport": 1, "small_airport": 2}


@dataclass
class Airport:
    iata: str
    name: str
    municipality: str
    country_code: str
    country_name: str
    type: str
    scheduled_service: bool


@lru_cache(maxsize=1)
def _country_names() -> dict[str, str]:
    with open(COUNTRIES_CSV, encoding="utf-8") as f:
        return {row["code"]: row["name"] for row in csv.DictReader(f)}


@lru_cache(maxsize=1)
def _load_airports() -> list[Airport]:
    countries = _country_names()
    out = []
    with open(AIRPORTS_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["type"] not in COMMERCIAL_TYPES:
                continue
            if not row["iata_code"]:
                continue
            out.append(
                Airport(
                    iata=row["iata_code"],
                    name=row["name"],
                    municipality=row["municipality"] or "",
                    country_code=row["iso_country"],
                    country_name=countries.get(row["iso_country"], row["iso_country"]),
                    type=row["type"],
                    scheduled_service=row["scheduled_service"] == "yes",
                )
            )
    return out


def list_countries() -> list[str]:
    """Todos os países que têm ao menos um aeroporto comercial."""
    names = {a.country_name for a in _load_airports()}
    return sorted(names)


def list_cities(country_name: str) -> list[str]:
    """Todas as cidades com aeroporto comercial num país (nome exato, ver search_countries pra achar o nome certo)."""
    q = _normalize(country_name)
    cities = {
        a.municipality
        for a in _load_airports()
        if _normalize(a.country_name) == q and a.municipality
    }
    return sorted(cities)


def search_countries(query: str) -> list[str]:
    q = _normalize(query)
    return sorted({c for c in list_countries() if q in _normalize(c)})


def find_airports(country: str | None = None, city: str | None = None) -> list[Airport]:
    """Retorna aeroportos que batem com país e/ou cidade (substring, sem acento,
    case-insensitive), ordenados do maior pro menor (large > medium > small) e
    priorizando quem tem voo regular (scheduled_service)."""
    results = []
    country_q = _normalize(country) if country else None
    city_q = _normalize(city) if city else None
    for a in _load_airports():
        if country_q and country_q not in _normalize(a.country_name):
            continue
        if city_q and city_q not in _normalize(a.municipality):
            continue
        results.append(a)
    results.sort(key=lambda a: (not a.scheduled_service, TYPE_RANK.get(a.type, 9)))
    return results


def best_airport_for_city(country: str, city: str) -> Airport | None:
    """Aeroporto mais provável pra representar uma cidade (o maior com voo regular)."""
    matches = find_airports(country=country, city=city)
    return matches[0] if matches else None


def airport_by_iata(iata: str) -> Airport | None:
    for a in _load_airports():
        if a.iata == iata.upper():
            return a
    return None
