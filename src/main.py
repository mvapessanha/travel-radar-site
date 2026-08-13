"""Orquestrador: roda uma vez por dia (via Task Scheduler) e faz tudo:
busca preços (por rota alternativa), salva histórico, compara rotas,
rankeia melhores dias, confere as melhores no Google Voos de verdade
(SerpApi, só se o roteiro estiver "active"), gera dashboard, dispara alerta."""
from __future__ import annotations

import argparse
import sys
import time
import webbrowser
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.alerts.email_alert import send_email_alert
from src.alerts.messages import build_daily_digest, build_offer_alert
from src.alerts.telegram import send_telegram_alert
from src.analysis.best_days import candidate_dates, rank_best_days, weekday_effect
from src.analysis.route_options import best_route, evaluate_route_options
from src.collectors.seed_estimate import SeedEstimateCollector
from src.collectors.serpapi_google_flights import SerpApiGoogleFlightsCollector
from src.collectors.travelpayouts import TravelpayoutsCollector
from src.dashboard.data_export import build_dashboard_data
from src.dashboard.report import generate_report
from src.geo.airports import airport_by_iata
from src.publish.github_pages import publish as publish_to_pages
from src.storage.db import (
    PriceQuote,
    digest_sent_today,
    fetch_all_quotes,
    insert_quotes,
    min_price_ever,
    record_alert,
    record_digest,
)

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config" / "destinations"


def load_config(tenant_id: str) -> dict:
    path = CONFIG_DIR / f"{tenant_id}.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _check_new_low_and_alert(
    tenant_id: str, cfg: dict, new_quotes: list[PriceQuote], origin_city: str, destination_city: str
) -> None:
    """Notificação tipo 'oferta': dispara a qualquer hora que rodar, sempre com link."""
    for q in new_quotes:
        if q.source == "seed_estimate":
            continue
        prev_min = min_price_ever(tenant_id, q.depart_date.isoformat(), q.nights)
        is_new_low = prev_min is None or q.price < prev_min
        if is_new_low and cfg["alerts"]["always_alert_new_low"]:
            msg = build_offer_alert(
                cfg["display_name"], origin_city, destination_city,
                q.depart_date, q.return_date, q.nights, q.price, q.source, q.airline,
            )
            send_telegram_alert(msg)
            send_email_alert(f"[Travel Radar] Oferta — {cfg['display_name']}", msg)
            record_alert(tenant_id, q.depart_date.isoformat(), q.return_date.isoformat(), q.price, "new_low")


def _send_daily_digest_if_due(
    tenant_id: str, cfg: dict, origin_city: str, destination_city: str,
    winner, ranked_days: list[dict], nights: int,
) -> None:
    """Notificação tipo 'atualização': no máximo 1x/dia, mesmo rodando de hora em hora."""
    today = date.today().isoformat()
    if digest_sent_today(tenant_id, today):
        return
    msg = build_daily_digest(cfg["display_name"], origin_city, destination_city, winner, ranked_days, nights)
    send_telegram_alert(msg)
    send_email_alert(f"[Travel Radar] Atualização diária — {cfg['display_name']}", msg)
    record_digest(tenant_id, today)


def run(tenant_id: str, max_dates: int, open_browser: bool, scheduled: bool) -> None:
    load_dotenv()
    cfg = load_config(tenant_id)
    is_active = cfg.get("status", "draft") == "active"

    if scheduled and not is_active:
        print(
            f"[main] Execução automática pulada: roteiro '{tenant_id}' ainda é 'draft' "
            "(sem status: active, o job horário não gasta cota de API à toa). "
            "Rode manualmente (sem --scheduled) quando quiser testar filtros."
        )
        return

    # Amadeus fechou self-service (17/07/2026) e Duffel exige verificação de
    # negócio pra sair do modo teste (inviável pra pessoa física, testado e
    # confirmado) — por isso NÃO ficam na lista ativa, mesmo que sobre chave
    # no .env (evita rodar chamada inútil toda hora). Travelpayouts (Aviasales
    # Data API) é a espinha dorsal real hoje: grátis, sem esse tipo de barreira.
    free_collectors = [
        TravelpayoutsCollector(tenant_id),
        SeedEstimateCollector(tenant_id),
        # DuffelCollector(tenant_id),   # descartado: modo teste só dá dado fictício, "Go live" pede verificação de negócio
        # AmadeusCollector(tenant_id),  # self-service fechado pra devs novos desde 17/07/2026
        # KiwiCollector(tenant_id),     # Tequila API hoje é só por convite
    ]
    active_free = [c for c in free_collectors if c.is_configured]
    has_real_data_source = any(c.source_name != "seed_estimate" for c in active_free)
    print(f"[main] Coletores grátis ativos: {[c.source_name for c in active_free]} | roteiro ativo: {is_active}")

    days = candidate_dates(cfg["search_window"], cfg["blackout_dates"])
    step = max(1, len(days) // max_dates)
    sampled_days = days[::step][:max_dates]

    target_nights = cfg["trip_length"]["target_nights"]
    compare_nights = cfg["trip_length"]["compare_range"]
    route_options = cfg["route_options"]

    # 1) varredura: a estimativa (grátis) explora toda a faixa de durações;
    #    fontes pagas/limitadas (Duffel etc.) só testam a duração alvo, pra
    #    não estourar cota/rate-limit. Pequeno intervalo entre chamadas pagas
    #    evita bater no rate-limit em vez de só reagir a ele depois.
    METERED_SOURCES = {"duffel", "amadeus", "kiwi"}
    all_new_quotes: list[PriceQuote] = []
    for opt in route_options:
        dest = opt["destination_airport"]
        for depart in sampled_days:
            for nights in compare_nights:
                ret = depart + timedelta(days=nights)
                if ret > date.fromisoformat(cfg["search_window"]["end"]) + timedelta(days=14):
                    continue
                for origin in cfg["origin_airports"]:
                    for collector in active_free:
                        if collector.source_name in METERED_SOURCES and nights != target_nights:
                            continue
                        try:
                            quotes = collector.fetch(origin, dest, depart, ret)
                        except Exception as exc:
                            print(f"[main] {collector.source_name} falhou para {origin}->{dest} {depart}: {exc}")
                            continue
                        all_new_quotes.extend(quotes)
                        if collector.source_name in METERED_SOURCES:
                            time.sleep(0.8)
    insert_quotes(all_new_quotes)
    print(f"[main] {len(all_new_quotes)} novas cotações salvas.")

    # 2) análise preliminar com o que já temos, pra saber quais datas valem
    #    gastar cota da SerpApi (só se o roteiro estiver "active")
    all_quotes = fetch_all_quotes(tenant_id)
    quotes_for_target = [q for q in all_quotes if q["nights"] == target_nights] or all_quotes
    quotes_by_destination: dict[str, list[dict]] = {}
    for q in quotes_for_target:
        quotes_by_destination.setdefault(q["destination"], []).append(q)

    route_results = evaluate_route_options(route_options, quotes_by_destination, cfg["extra_costs"], target_nights)
    winner = best_route(route_results, "realistic")
    best_dest = winner.destination_airport if winner else route_options[0]["destination_airport"]

    origin_city = cfg.get("origin_city", cfg["origin_airports"][0])
    dest_airport = airport_by_iata(best_dest)
    destination_city = dest_airport.municipality if dest_airport else best_dest

    dest_quotes = [q for q in all_quotes if q["destination"] == best_dest]
    ranked_days = rank_best_days(dest_quotes, top_n=15)

    # 3) conferência real no Google Voos (SerpApi) só pras top-N datas da rota
    #    vencedora, e só se o roteiro estiver definido (status: active)
    serpapi = SerpApiGoogleFlightsCollector(tenant_id)
    serpapi_new_quotes: list[PriceQuote] = []
    if is_active and serpapi.is_configured:
        top_n = cfg["alerts"].get("serpapi_top_n_check", 3)
        origin = cfg["origin_airports"][0]
        for row in ranked_days[:top_n]:
            depart = date.fromisoformat(row["depart_date"])
            ret = depart + timedelta(days=row["nights"])
            try:
                quotes = serpapi.fetch(origin, best_dest, depart, ret)
            except Exception as exc:
                print(f"[main] serpapi falhou para {origin}->{best_dest} {depart}: {exc}")
                continue
            serpapi_new_quotes.extend(quotes)
        insert_quotes(serpapi_new_quotes)
        print(f"[main] {len(serpapi_new_quotes)} cotações reais do Google Voos (SerpApi) salvas.")
    elif is_active and not serpapi.is_configured:
        print("[main] Roteiro ativo mas SERPAPI_KEY não configurada — pulando conferência real no Google Voos.")

    _check_new_low_and_alert(tenant_id, cfg, all_new_quotes + serpapi_new_quotes, origin_city, destination_city)

    # 4) análise final já incluindo eventuais cotações da SerpApi
    all_quotes = fetch_all_quotes(tenant_id)
    quotes_for_target = [q for q in all_quotes if q["nights"] == target_nights] or all_quotes
    quotes_by_destination = {}
    for q in quotes_for_target:
        quotes_by_destination.setdefault(q["destination"], []).append(q)
    route_results = evaluate_route_options(route_options, quotes_by_destination, cfg["extra_costs"], target_nights)
    winner = best_route(route_results, "realistic")
    best_dest = winner.destination_airport if winner else best_dest

    dest_quotes = [q for q in all_quotes if q["destination"] == best_dest]
    ranked_days = rank_best_days(dest_quotes, top_n=15)
    checked_keys = {(q["depart_date"], q["nights"]) for q in dest_quotes if q["source"] == "google_flights_serpapi"}
    for row in ranked_days:
        row["has_real_check"] = (row["depart_date"], row["nights"]) in checked_keys
    weekday_avg = weekday_effect(dest_quotes)

    dest_airport = airport_by_iata(best_dest)
    destination_city = dest_airport.municipality if dest_airport else best_dest

    _send_daily_digest_if_due(tenant_id, cfg, origin_city, destination_city, winner, ranked_days, target_nights)

    report_path = generate_report(
        tenant_id=tenant_id,
        display_name=cfg["display_name"],
        origin_city=origin_city,
        destination_city=destination_city,
        quotes=dest_quotes,
        route_results=route_results,
        best_route_id=winner.route_id if winner else None,
        ranked_days=ranked_days,
        weekday_avg=weekday_avg,
        nights=target_nights,
        has_real_data=has_real_data_source and len([q for q in all_quotes if q["source"] != "seed_estimate"]) > 0,
    )
    print(f"[main] Dashboard local gerado em: {report_path}")

    dashboard_data = build_dashboard_data(
        tenant_id=tenant_id,
        display_name=cfg["display_name"],
        origin_city=origin_city,
        destination_city=destination_city,
        quotes=dest_quotes,
        route_results=route_results,
        winner_route_id=winner.route_id if winner else None,
        ranked_days=ranked_days,
        weekday_avg=weekday_avg,
        nights=target_nights,
        has_real_data=has_real_data_source and len([q for q in all_quotes if q["source"] != "seed_estimate"]) > 0,
    )
    publish_to_pages(dashboard_data)

    if open_browser:
        webbrowser.open(report_path.as_uri())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", default="marau")
    parser.add_argument("--max-dates", type=int, default=20, help="quantas datas de ida testar por execução")
    parser.add_argument("--open", action="store_true", help="abrir o dashboard no navegador ao final")
    parser.add_argument(
        "--scheduled",
        action="store_true",
        help="marca que essa execução veio do agendador automático (Task Scheduler) - "
        "só roda de fato se o roteiro estiver status: active. Não use isso pra rodar manualmente.",
    )
    args = parser.parse_args()

    if args.scheduled:
        # rodando via Task Scheduler com pythonw.exe (sem console) -> não tem
        # stdout de verdade pra imprimir, e não pode abrir nenhuma janela.
        # Redireciona tudo pra um log em arquivo, sempre em segundo plano.
        log_dir = Path(__file__).resolve().parents[1] / "data"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = open(log_dir / "run.log", "a", encoding="utf-8")
        sys.stdout = log_file
        sys.stderr = log_file
        print(f"\n=== execução agendada {datetime.now().isoformat(timespec='seconds')} ===")

    run(args.tenant, args.max_dates, args.open, args.scheduled)
