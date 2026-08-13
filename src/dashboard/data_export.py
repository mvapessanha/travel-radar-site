"""Monta o JSON que alimenta o dashboard interativo (site/data.json).

O front-end (templates/dashboard_app.html) é estático e não muda a cada
execução — só esse JSON é regravado, o que mantém a publicação leve e rápida.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from src.analysis.route_options import RouteOptionResult

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config" / "destinations"


def _price_history(quotes: list[dict]) -> list[dict]:
    by_date: dict[str, float] = {}
    for q in quotes:
        key = q["collected_at"][:10]
        by_date[key] = min(by_date.get(key, float("inf")), q["price"])
    return [{"date": d, "price": by_date[d]} for d in sorted(by_date.keys())]


def build_dashboard_data(
    tenant_id: str,
    display_name: str,
    origin_city: str,
    destination_city: str,
    quotes: list[dict],
    route_results: list[RouteOptionResult],
    winner_route_id: str | None,
    ranked_days: list[dict],
    weekday_avg: dict[str, float],
    nights: int,
    has_real_data: bool,
) -> dict:
    guide_path = CONFIG_DIR / f"{tenant_id}_guide.html"
    guide_html = guide_path.read_text(encoding="utf-8") if guide_path.exists() else ""

    return {
        "tenant_id": tenant_id,
        "display_name": display_name,
        "origin_city": origin_city,
        "destination_city": destination_city,
        "generated_at": datetime.now().isoformat(timespec="minutes"),
        "target_nights": nights,
        "has_real_data": has_real_data,
        "routes": [
            {
                "id": r.route_id,
                "label": r.label,
                "notes": r.notes,
                "flight": r.flight_totals,
                "transfer": r.transfer_totals,
                "fixed": r.fixed_totals,
                "grand": {s: r.grand_total(s) for s in ["optimistic", "realistic", "conservative"]},
            }
            for r in route_results
        ],
        "winner_route_id": winner_route_id,
        "best_days": ranked_days,
        "weekday_avg": weekday_avg,
        "price_history": _price_history(quotes),
        "guide_html": guide_html,
    }


def write_data_json(data: dict, out_path: Path) -> None:
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
