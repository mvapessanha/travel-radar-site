"""Compara rotas alternativas até o destino final (ex: voo direto vs voo até
outro hub + traslado terrestre), somando aéreo + traslado + custos fixos."""
from __future__ import annotations

from dataclasses import dataclass

from src.analysis.scenarios import flight_scenarios

LABELS = ["optimistic", "realistic", "conservative"]
IDX = {"optimistic": 0, "realistic": 1, "conservative": 2}


@dataclass
class RouteOptionResult:
    route_id: str
    label: str
    destination_airport: str
    notes: str | None
    flight_totals: dict[str, float]
    transfer_totals: dict[str, float]
    fixed_totals: dict[str, float]  # comida + passeios, igual pra todas as rotas

    def grand_total(self, scenario: str) -> float:
        return round(
            self.flight_totals[scenario] + self.transfer_totals[scenario] + self.fixed_totals[scenario], 2
        )


def _fixed_costs_by_scenario(extra_costs: dict, nights: int) -> dict[str, float]:
    totals = {}
    for label in LABELS:
        i = IDX[label]
        food = extra_costs["food_per_person_per_day"][i] * 2 * nights
        passeios = extra_costs["local_transport_passeios_per_person_total"][i] * 2
        totals[label] = round(food + passeios, 2)
    return totals


def evaluate_route_options(
    route_options: list[dict],
    quotes_by_destination: dict[str, list[dict]],
    extra_costs: dict,
    nights: int,
) -> list[RouteOptionResult]:
    fixed = _fixed_costs_by_scenario(extra_costs, nights)
    results = []
    for opt in route_options:
        dest = opt["destination_airport"]
        quotes = quotes_by_destination.get(dest, [])
        flights = flight_scenarios(quotes)
        transfer = {
            label: round(opt["ground_transfer_per_person"][IDX[label]] * 2 * 2, 2)  # ida+volta, 2 pessoas
            for label in LABELS
        }
        results.append(
            RouteOptionResult(
                route_id=opt["id"],
                label=opt["label"],
                destination_airport=dest,
                notes=opt.get("notes"),
                flight_totals=flights,
                transfer_totals=transfer,
                fixed_totals=fixed,
            )
        )
    return results


def best_route(results: list[RouteOptionResult], scenario: str = "realistic") -> RouteOptionResult | None:
    valid = [r for r in results if r.flight_totals[scenario] > 0]
    if not valid:
        return None
    return min(valid, key=lambda r: r.grand_total(scenario))
