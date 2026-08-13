"""Cálculo do preço de passagem em 3 cenários: otimista / realista / conservador.

Regra: com dados reais (Amadeus/SerpApi) acumulados, usamos percentis
observados. Sem dados reais suficientes (menos de MIN_REAL_SAMPLES cotações
não-estimadas), caímos para a estimativa de pesquisa (seed_estimate).
"""
from __future__ import annotations

from statistics import median

MIN_REAL_SAMPLES = 5


def _percentile(values: list[float], pct: float) -> float:
    values = sorted(values)
    if not values:
        return 0.0
    k = (len(values) - 1) * pct
    f, c = int(k), min(int(k) + 1, len(values) - 1)
    if f == c:
        return values[f]
    return values[f] + (values[c] - values[f]) * (k - f)


def flight_scenarios(quotes: list[dict]) -> dict[str, float]:
    real = [q["price"] for q in quotes if q["source"] != "seed_estimate"]
    pool = real if len(real) >= MIN_REAL_SAMPLES else [q["price"] for q in quotes]
    if not pool:
        return {"optimistic": 0.0, "realistic": 0.0, "conservative": 0.0}
    return {
        "optimistic": round(_percentile(pool, 0.10), 2),
        "realistic": round(median(pool), 2),
        "conservative": round(_percentile(pool, 0.90), 2),
    }
