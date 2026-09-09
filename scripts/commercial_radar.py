# -*- coding: utf-8 -*-
"""
RADAR DE OPORTUNIDADES COMERCIAIS do Portal Ao Vivo.

Le data/commercial_leads.json e imprime o ranking das melhores
oportunidades por lead_score. Usado no pipeline e agendado no
GitHub Actions, para o diretor comercial abrir o log/JSON e saber
quais eventos prospectar primeiro.

Exemplo de saida:

    RADAR COMERCIAL - TOP 10 OPORTUNIDADES
    ============================================================
     1. Festa do Cafe [Patrocinio] - 9.7 (em 15d, novo)
     2. Campeonato Regional [Patos de Minas] - 9.5 (em 12d, novo)
     ...
"""
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "scripts"))

import event_detector


def top_leads(limite=10, apenas_ativos=True):
    return event_detector.listar_top_leads(limite=limite, apenas_ativos=apenas_ativos)


def print_top_leads(limite=10):
    return event_detector.print_top_leads(limite=limite)


def resumo_json(limite=10):
    """Resumo compacto para o log do CI (uma linha por lead)."""
    topo = top_leads(limite)
    linhas = []
    for i, l in enumerate(topo, 1):
        nome = (l.get("event_name") or "?")[:45]
        cidade = l.get("city") or "-"
        score = float(l.get("lead_score") or 0)
        dias = l.get("days_until_event")
        quando = f"em {dias}d" if dias is not None and l.get("event_timing") != "passado" else (l.get("event_timing") or "-")
        linhas.append({"rank": i, "event_name": nome, "city": cidade,
                       "lead_score": score, "days_until_event": dias,
                       "event_timing": l.get("event_timing"),
                       "organizer": l.get("organizer"),
                       "status": l.get("status")})
    return linhas


if __name__ == "__main__":
    print_top_leads(limite=10)
    resumo = resumo_json(10)
    if resumo:
        print("\n[COMPACT] " + json.dumps(resumo, ensure_ascii=False))