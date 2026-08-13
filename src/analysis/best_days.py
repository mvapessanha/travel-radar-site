"""Ranking dos melhores dias/duração pra voar dentro da janela permitida."""
from __future__ import annotations

from datetime import date, timedelta


def in_blackout(d: date, blackout_dates: list[dict]) -> bool:
    for period in blackout_dates:
        start = date.fromisoformat(period["start"])
        end = date.fromisoformat(period["end"])
        if start <= d <= end:
            return True
    return False


def candidate_dates(search_window: dict, blackout_dates: list[dict]) -> list[date]:
    start = date.fromisoformat(search_window["start"])
    end = date.fromisoformat(search_window["end"])
    days = []
    d = start
    while d <= end:
        if not in_blackout(d, blackout_dates):
            days.append(d)
        d += timedelta(days=1)
    return days


def rank_best_days(quotes: list[dict], top_n: int = 10) -> list[dict]:
    """Agrupa cotações por (depart_date, nights) e retorna as combinações
    mais baratas observadas até agora, ordenadas por menor preço."""
    grouped: dict[tuple[str, int], list[float]] = {}
    for q in quotes:
        key = (q["depart_date"], q["nights"])
        grouped.setdefault(key, []).append(q["price"])

    ranked = [
        {
            "depart_date": key[0],
            "nights": key[1],
            "min_price": min(prices),
            "avg_price": round(sum(prices) / len(prices), 2),
            "samples": len(prices),
        }
        for key, prices in grouped.items()
    ]
    ranked.sort(key=lambda r: r["min_price"])
    return ranked[:top_n]


def weekday_effect(quotes: list[dict]) -> dict[str, float]:
    """Preço médio por dia da semana de partida (0=segunda ... 6=domingo)."""
    buckets: dict[int, list[float]] = {i: [] for i in range(7)}
    for q in quotes:
        d = date.fromisoformat(q["depart_date"])
        buckets[d.weekday()].append(q["price"])
    names = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    return {
        names[i]: round(sum(v) / len(v), 2) if v else None
        for i, v in buckets.items()
    }
