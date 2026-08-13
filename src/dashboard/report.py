"""Gera um dashboard HTML estático (sem servidor) a cada execução."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.analysis.route_options import RouteOptionResult
from src.dashboard.links import google_flights_url

OUT_DIR = Path(__file__).resolve().parents[2] / "data"
CONFIG_DIR = Path(__file__).resolve().parents[2] / "config" / "destinations"

LABEL_PT = {"optimistic": "Otimista", "realistic": "Realista", "conservative": "Conservador"}


def _route_options_table_html(results: list[RouteOptionResult], best_route_id: str | None) -> str:
    rows = []
    for r in results:
        star = " ⭐" if r.route_id == best_route_id else ""
        note = f"<div class='note'>{r.notes}</div>" if r.notes else ""
        cells = "".join(
            f"<td>R$ {r.flight_totals[l]:,.2f}</td><td>R$ {r.transfer_totals[l]:,.2f}</td>"
            f"<td><b>R$ {r.grand_total(l):,.2f}</b></td>"
            for l in ["optimistic", "realistic", "conservative"]
        )
        rows.append(f"<tr><td>{r.label}{star}{note}</td>{cells}</tr>")
    return f"""
    <table class="tbl">
      <thead>
        <tr>
          <th rowspan="2">Rota</th>
          <th colspan="3">Otimista</th><th colspan="3">Realista</th><th colspan="3">Conservador</th>
        </tr>
        <tr>
          <th>Aéreo</th><th>Traslado</th><th>Total</th>
          <th>Aéreo</th><th>Traslado</th><th>Total</th>
          <th>Aéreo</th><th>Traslado</th><th>Total</th>
        </tr>
      </thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    <p class="hint">Totais de aéreo/traslado são pro casal (2 pessoas), ida e volta. Comida e passeios
    (iguais pra qualquer rota) somam à parte — ver seção de orçamento total.</p>
    """


def _fixed_costs_table_html(results: list[RouteOptionResult]) -> str:
    if not results:
        return ""
    f = results[0].fixed_totals
    return f"""
    <table class="tbl">
      <thead><tr><th></th><th>Otimista</th><th>Realista</th><th>Conservador</th></tr></thead>
      <tbody>
        <tr><td>Comida + passeios (casal, estadia toda)</td>
        <td>R$ {f['optimistic']:,.2f}</td><td>R$ {f['realistic']:,.2f}</td><td>R$ {f['conservative']:,.2f}</td></tr>
      </tbody>
    </table>
    """


def _best_days_table_html(ranked_days: list[dict], origin_city: str, destination_city: str) -> str:
    rows = []
    for r in ranked_days:
        depart = date.fromisoformat(r["depart_date"])
        ret = depart + timedelta(days=r["nights"])
        link = google_flights_url(origin_city, destination_city, depart, ret)
        source_tag = " ✅" if r.get("has_real_check") else ""
        rows.append(
            f"<tr><td>{r['depart_date']}</td><td>{r['nights']}</td>"
            f"<td>R$ {r['min_price']:,.2f}{source_tag}</td><td>R$ {r['avg_price']:,.2f}</td>"
            f"<td>{r['samples']}</td>"
            f"<td><a href=\"{link}\" target=\"_blank\" rel=\"noopener\">ver no Google Voos ↗</a></td></tr>"
        )
    return f"""
    <table class="tbl">
      <thead><tr><th>Data de ida</th><th>Noites</th><th>Menor preço visto</th><th>Preço médio</th><th>Amostras</th><th>Conferir</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    <p class="hint">✅ = já conferido de verdade no Google Voos via SerpApi (não é só Amadeus/estimativa).</p>
    """


def _guide_html(tenant_id: str) -> str:
    path = CONFIG_DIR / f"{tenant_id}_guide.html"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "<p>Sem guia cultural/turístico ainda para este destino.</p>"


def generate_report(
    tenant_id: str,
    display_name: str,
    origin_city: str,
    destination_city: str,
    quotes: list[dict],
    route_results: list[RouteOptionResult],
    best_route_id: str | None,
    ranked_days: list[dict],
    weekday_avg: dict[str, float],
    nights: int,
    has_real_data: bool,
) -> Path:
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=("Histórico de preço coletado ao longo do tempo", "Preço médio por dia da semana de ida"),
        vertical_spacing=0.18,
    )

    if quotes:
        by_date: dict[str, float] = {}
        for q in quotes:
            key = q["collected_at"][:10]
            by_date[key] = min(by_date.get(key, float("inf")), q["price"])
        xs = sorted(by_date.keys())
        ys = [by_date[x] for x in xs]
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines+markers", name="Menor preço do dia"), row=1, col=1)

    wk_x = [k for k, v in weekday_avg.items() if v is not None]
    wk_y = [v for v in weekday_avg.values() if v is not None]
    if wk_x:
        fig.add_trace(go.Bar(x=wk_x, y=wk_y, name="Preço médio"), row=2, col=1)

    fig.update_layout(height=700, showlegend=False, margin=dict(t=60, b=40))

    chart_html = fig.to_html(full_html=False, include_plotlyjs=True)

    data_warning = "" if has_real_data else """
      <div class="warn">
        ⚠️ Nenhuma cotação real (Amadeus/SerpApi) ainda foi coletada — os valores abaixo usam a
        <b>estimativa de pesquisa inicial</b>, não preços de mercado ao vivo. Configure as chaves
        de API no .env pra isso virar dado real.
      </div>"""

    html = f"""<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<title>Travel Radar — {display_name}</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Arial, sans-serif; max-width: 1050px; margin: 30px auto; padding: 0 16px; color: #1b1b1f; }}
  h1 {{ font-size: 22px; }}
  h2 {{ font-size: 17px; margin-top: 36px; border-bottom: 1px solid #ddd; padding-bottom: 6px; }}
  .meta {{ color: #666; font-size: 13px; margin-bottom: 20px; }}
  .warn {{ background: #fff4e5; border: 1px solid #f0c36d; padding: 12px 16px; border-radius: 8px; margin: 16px 0; font-size: 14px; }}
  .hint {{ color: #666; font-size: 12px; }}
  .note {{ color: #666; font-size: 12px; font-weight: normal; max-width: 260px; margin-top: 4px; }}
  .guide {{ background: #f8f7f4; border-radius: 8px; padding: 4px 20px; font-size: 14px; line-height: 1.6; }}
  .guide ul {{ padding-left: 20px; }}
  table.tbl {{ border-collapse: collapse; width: 100%; font-size: 13px; margin-top: 8px; }}
  table.tbl th, table.tbl td {{ border: 1px solid #ddd; padding: 7px 9px; text-align: left; }}
  table.tbl th {{ background: #f5f5f7; text-align: center; }}
</style>
</head>
<body>
  <h1>Travel Radar — {display_name}</h1>
  <div class="meta">Tenant: {tenant_id} · Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} · Duração alvo: {nights} noites · Origem: {origin_city}</div>
  {data_warning}

  <h2>Comparação de rotas (avião direto vs. avião + traslado)</h2>
  {_route_options_table_html(route_results, best_route_id) if route_results else "<p>Sem rotas configuradas.</p>"}

  <h2>Custos fixos (independem da rota)</h2>
  {_fixed_costs_table_html(route_results)}

  <h2>Melhores dias já observados (rota recomendada)</h2>
  {_best_days_table_html(ranked_days, origin_city, destination_city) if ranked_days else "<p>Ainda sem cotações suficientes.</p>"}

  <h2>Contexto cultural e sugestão de roteiro</h2>
  <div class="guide">{_guide_html(tenant_id)}</div>

  <h2>Tendência de preço</h2>
  {chart_html}
</body>
</html>"""

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"dashboard_{tenant_id}.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path
