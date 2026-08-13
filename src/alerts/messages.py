"""Monta o texto das duas notificações do Telegram/e-mail:

- "atualização": resumo diário (1x/dia) do status do roteiro — melhor rota,
  melhores dias, preço atual. Sempre inclui link do Google Voos.
- "oferta": disparada a qualquer hora que o job rodar, quando acha preço
  bem abaixo do normal (novo mínimo histórico). Também sempre com link.
"""
from __future__ import annotations

from datetime import date, timedelta

from src.analysis.route_options import RouteOptionResult
from src.dashboard.links import google_flights_url


def build_daily_digest(
    display_name: str,
    origin_city: str,
    destination_city: str,
    winner: RouteOptionResult | None,
    ranked_days: list[dict],
    nights: int,
    top_n: int = 3,
) -> str:
    lines = [f"📊 <b>Atualização diária — {display_name}</b>"]

    if winner:
        lines.append(f"Rota recomendada: {winner.label}")
        lines.append(
            f"Total estimado (casal, {nights} noites, cenário realista): "
            f"R$ {winner.grand_total('realistic'):,.2f}"
        )
    else:
        lines.append("Ainda sem dado suficiente pra comparar rotas.")

    if ranked_days:
        lines.append("\n<b>Melhores dias já observados:</b>")
        for row in ranked_days[:top_n]:
            depart = date.fromisoformat(row["depart_date"])
            ret = depart + timedelta(days=row["nights"])
            link = google_flights_url(origin_city, destination_city, depart, ret)
            lines.append(
                f"• {row['depart_date']} → {ret.isoformat()} ({row['nights']}n): "
                f"R$ {row['min_price']:,.2f} — <a href=\"{link}\">ver no Google Voos</a>"
            )
    else:
        lines.append("\nAinda sem cotações suficientes pra rankear dias.")

    return "\n".join(lines)


def build_offer_alert(
    display_name: str,
    origin_city: str,
    destination_city: str,
    depart_date: date,
    return_date: date,
    nights: int,
    price: float,
    source: str,
    airline: str | None,
) -> str:
    link = google_flights_url(origin_city, destination_city, depart_date, return_date)
    return (
        f"🔻 <b>Oferta — {display_name}</b>\n"
        f"Novo menor preço já visto para essa combinação!\n"
        f"Ida: {depart_date.isoformat()} · Volta: {return_date.isoformat()} ({nights} noites)\n"
        f"Preço (casal): R$ {price:,.2f} via {source} ({airline or '-'})\n"
        f"<a href=\"{link}\">Ver e conferir no Google Voos</a>"
    )
