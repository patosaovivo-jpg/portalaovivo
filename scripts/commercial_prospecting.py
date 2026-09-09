# -*- coding: utf-8 -*-
"""
PROSPECÇÃO INTELIGENTE do Portal Ao Vivo (ETAPA 3).

Os campos são ADITIVOS à Inteligência Comercial existente
(event_detector / commercial_radar): NADA remove nem substitui o
fluxo atual. O prospecting_priority NÃO substitui o status do lead:
status = ciclo de vida comercial (novo->monitorando->contatado->...),
priority = momento/oportunidade de prospectar.

O que esta camada enriquece em cada lead registrado:

  - lead_id / event_id            : IDs estaveis (preparacao para CRM)
  - potential_client_type         : QUEM pode contratar (lista)
  - recommended_services          : serviço mais provável de vender
  - commercial_need               : a "dor" que a transmissão resolve
  - recommended_contact_window    : QUANDO prospectar (texto humano)
  - contact_window / prospecting_priority
                                  : janela e prioridade (reguas)
  - recurring_event / recurrence_pattern / previous_event_detected
                                  : recorrência e histórico
  - organizer_type / organizer_source / organizer_url
                                  : contato (só o que existe em fonte)
  - sponsors_detected (bool)      : evidência TEXTUAL de patrocínio
  - contact_reason                : MOTIVO de prospectar (frase)
  - suggested_outreach            : rascunho de abordagem (NUNCA enviado)
  - contact_history (lista)       : histórico pronto para o CRM
  - notes                         : campo livre futuro

REGRAS QUE NÃO PODEM SER QUEBRADAS:
  1. NUNCA envia mensagem automaticamente (WhatsApp/e-mail/DM).
     suggested_outreach é APENAS um rascunho para o diretor comercial.
  2. NUNCA inventa contato: organizer/organizer_url/organizer_source
     apenas quando há evidência na notícia.
  3. sponsors_detected somente com evidência textual extraída
     ("patrocinado por X", "X patrocina", "patrocinadores").
  4. Manual > automático: o painel apenas recomenda prioridade.

PRIORIDADES (prospecting_priority):
  monitorar < baixo < médio < alto < urgente < muito_urgente
Reordenadas a cada rodada usando data, dias até o evento,
recorrência, histórico, patrocinadores e lead_score. Eventos já
realizados ficam em "não prospectar para transmissão" (monitorar).

JANELAS DE CONTATO (recommended_contact_window) por tipo de evento:
  configuráveis em config/prospecting_rules.json (ex.: default
  monitoring 90d / prospectar até 60d / prioridade até 30d /
  urgente até 7d). Overshoot por grupo: esporte 45d, festival 90d,
  corporativo 60d, educação 50d, religioso 75d.
"""
import hashlib
import json
import os
import re
import sys
import unicodedata

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "scripts"))

PROSPECTING_RULES_FILE = os.path.join(BASE_DIR, "config", "prospecting_rules.json")

import event_detector as ed  # noqa: E402

LADDER = ["monitorar", "baixo", "médio", "alto", "urgente", "muito_urgente"]

DEFAULT_WINDOWS = {
    "monitoring_days": 90,
    "prospecting_start": 60,
    "priority_days": 30,
    "urgent_high_days": 20,
    "urgent_days": 7,
    "too_late_days": 2,
}

WINDOW_TEXTO = {
    "monitorar": "Monitorar (evento ainda distante ou sem data)",
    "prospectar": "Prospectar (janela ideal: até {prospecting_start} dias antes)",
    "prospectar_prioridade": "Prospectar com prioridade (janela: {urgent_high} a {priority_days} dias antes)",
    "urgente": "Urgente — contactar imediatamente (a menos de {urgent_high} dias)",
    "muito_tarde": "Muito tarde — apenas ação de emergência",
    "nao_prospectar": "Não prospectar para transmissão (evento já aconteceu)",
}


def _norm(texto):
    if not texto:
        return ""
    texto = unicodedata.normalize("NFKD", str(texto))
    return u"".join(c for c in texto if not unicodedata.combining(c)).lower()


def _load_rules():
    try:
        with open(PROSPECTING_RULES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _janela_do_tipo(event_type, rules):
    jan = dict(DEFAULT_WINDOWS)
    cfg = rules.get("windows") or {}
    jan.update(cfg.get("default") or {})
    grupos = rules.get("type_groups") or {}
    grupo = grupos.get(event_type or "", "default")
    jan.update(cfg.get(grupo) or {})
    return jan


# ============================================================
# ORGANIZADOR / CONTATO
# ============================================================

def _organizer_type(organizer):
    """Infere o tipo de organizador apenas por palavras-chave do nome.

    NUNCA inventa nome/URL de contato: apenas classifica o tipo."""
    o = _norm(organizer or "")
    if not o:
        return ""
    if "prefeitura" in o:
        return "prefeitura"
    if "camara" in o:
        return "camara municipal"
    if "secretaria" in o:
        return "secretaria municipal"
    if "liga" in o:
        return "liga esportiva"
    if "clube" in o:
        return "clube esportivo"
    if "sindicato" in o:
        return "sindicato"
    if "associa" in o:
        return "associacao"
    if any(k in o for k in ("igreja", "paroquia", "capela")):
        return "igreja/comunidade"
    if any(k in o for k in ("escola", "universidade", "faculdade", "colegio",
                            "centro universitario", "instituto federal")):
        return "instituicao de ensino"
    if o.startswith("empresa"):
        return "empresa"
    return ""


# ============================================================
# POTENCIAL CLIENTE / SERVIÇO / DOR
# ============================================================

def _clientes_provaveis(event_type, organizer, rules):
    base = list((rules.get("client_types") or {}).get(event_type or "", []) or [])
    ot = _organizer_type(organizer)
    if ot:
        if ot in base:
            base.remove(ot)
        base.insert(0, ot)
    if not base:
        base = ["organizador de eventos"]
    dedup = []
    for b in base:
        if b not in dedup:
            dedup.append(b)
    return dedup


def _servicos_recomendados(event_type, rules):
    servicos = list((rules.get("services") or {}).get(event_type or "", []) or [])
    if not servicos:
        servicos = ["transmissao ao vivo", "cobertura audiovisual"]
    return servicos


def _dor(event_type, rules, lead):
    dor = (rules.get("needs") or {}).get(event_type or "", "")
    if not dor:
        dor = (rules.get("needs") or {}).get("default",
                                             "Ampliar o alcance do evento alem do publico presente.")
    extras = []
    if (lead or {}).get("sponsors_count"):
        extras.append("Ampliar a visibilidade dos patrocinadores.")
    if extras:
        dor = dor + " " + " ".join(extras)
    return dor


# ============================================================
# RECORRÊNCIA / HISTÓRICO
# ============================================================

def _padrao_recorrencia(event_name, recurring, edition):
    if not recurring:
        return ""
    texto = _norm(event_name or "")
    if edition and edition >= 2:
        return f"edição {edition}"
    if any(k in texto for k in ("anual", "ano a ano", "todos os anos")):
        return "anual"
    if "tradicional" in texto:
        return "tradicional"
    return "recorrente"


def _buscar_historico(lead, leads):
    """True se o mesmo evento (nome+cidade) já apareceu antes em outra data."""
    nome = _norm(lead.get("event_name") or "")
    cidade = _norm(lead.get("city") or "")
    data = lead.get("event_date") or ""
    if not nome:
        return False
    for k, outro in (leads or {}).items():
        if outro is lead:
            continue
        if _norm(outro.get("event_name") or "") != nome:
            continue
        if cidade and _norm(outro.get("city") or "") and \
                _norm(outro.get("city") or "") != cidade:
            continue
        if (outro.get("event_date") or "") == data:
            continue  # mesmo registro (self)
        return True
    return False


# ============================================================
# CLASSIFICAÇÃO DE PROSPECÇÃO (janela + prioridade)
# ============================================================

def classificar_prospeccao(dias, timing, jan):
    """Retorna (contact_window, prospecting_priority).

    Ordem monotônica: quanto mais perto, mais urgente.
      >= monitoring_days   -> monitorar
      <= too_late          -> muito_tarde
      <= urgent_days       -> urgente (última chamada)
      <= urgent_high_days  -> urgente
      <= priority_days     -> prospectar_prioridade
      <  prospecting_start -> prospectar
    """
    if dias is None:
        if timing == "passado":
            return "nao_prospectar", "monitorar"
        if timing == "hoje":
            return "urgente", "muito_urgente"
        return "monitorar", "monitorar"
    if dias < 0 or timing == "passado":
        return "nao_prospectar", "monitorar"
    if dias == 0:
        return "urgente", "muito_urgente"
    if dias >= jan["monitoring_days"]:
        return "monitorar", "monitorar"
    if dias <= jan["too_late_days"]:
        return "muito_tarde", "urgente"
    if dias <= jan["urgent_days"]:
        return "urgente", "urgente"
    if dias <= jan["urgent_high_days"]:
        return "urgente", "urgente"
    if dias <= jan["priority_days"]:
        return "prospectar_prioridade", "alto"
    return "prospectar", "baixo"


def _aplicar_boost(prio, recorrente, historico, score):
    """Evento recorrente/histórico ou score muito alto sobe um degrau."""
    if prio not in ("baixo", "médio", "alto"):
        return prio, False
    if recorrente or historico or (score or 0) >= 9:
        idx = LADDER.index(prio)
        if idx < len(LADDER) - 1:
            return LADDER[idx + 1], True
    return prio, False


def _window_texto(win, jan):
    template = WINDOW_TEXTO.get(win, win)
    try:
        return template.format(prospecting_start=jan["prospecting_start"],
                               urgent_high=jan["urgent_high_days"],
                               priority_days=jan["priority_days"])
    except Exception:
        return template


# ============================================================
# MOTIVO / RASCUNHO
# ============================================================

def _motivo(lead):
    partes = []
    tipo = lead.get("event_type")
    if tipo:
        partes.append(f"evento '{tipo}'")
    if lead.get("city"):
        partes.append("em " + str(lead["city"]))
    aud = lead.get("estimated_audience")
    if aud:
        partes.append(f"público estimado de {aud} pessoas")
    n_patro = int(lead.get("sponsors_count") or 0)
    if n_patro:
        partes.append(f"{n_patro} patrocinador(es)")
    dias = lead.get("days_until_event")
    if dias is not None and lead.get("event_timing") != "passado":
        partes.append(f"faltam {dias} dias")
    elif lead.get("event_timing") == "passado":
        partes.append("evento já realizado")
    org = lead.get("organizer")
    if org:
        partes.append("organizador em evidência")
    primeiro = ", ".join(partes) + "."
    dor = lead.get("commercial_need") or ""
    if dor and not any(piece in primeiro for piece in dor.split()):
        primeiro = primeiro + " " + dor
    motivo = re.sub(r"\s+", " ", primeira := primeiro.capitalize())
    return motivo or "Oportunidade comercial identificada."


def _rascunho(lead, rules):
    """Rascunho de abordagem. Só com lead_score >= 8 e evento futuro.

    É um rascunho para o diretor comercial — o sistema NUNCA envia."""
    if (lead.get("lead_score") or 0) < 8:
        return ""
    if lead.get("event_timing") in ("passado",):
        return ""
    templates = rules.get("outreach_templates") or {}
    clientes = lead.get("potential_client_type") or ["default"]
    templ = templates.get(clientes[0]) or templates.get("default") or ""
    if not templ:
        return ""
    cidade = lead.get("city") or "nossa região"
    return templ.format(evento=(lead.get("event_name") or "o evento"),
                        cidade=cidade).strip()


# ============================================================
# ENRIQUECIMENTO PRINCIPAL
# ============================================================

def _ids(lead):
    base = _norm((lead.get("event_name") or "") + "|" + (lead.get("city") or ""))
    ev = _norm((lead.get("event_name") or "") + "|" + (lead.get("city") or "")
               + "|" + (lead.get("event_date") or ""))
    lead_id = "lev-" + hashlib.md5(base.encode("utf-8")).hexdigest()[:10]
    event_id = "evt-" + hashlib.md5(ev.encode("utf-8")).hexdigest()[:10]
    return lead_id, event_id


def enriquecer_lead(lead, leads=None, rules=None):
    """Enriquece um lead com toda a inteligência de prospecção.

    Não altera status / lead_score / detected_at / source (ciclode vida).
    Retorna o mesmo lead (mutação + retorno).
    """
    if not lead or not isinstance(lead, dict):
        return lead
    rules = rules or _load_rules()
    leads = leads if leads is not None else ed.load_leads()

    event_type = lead.get("event_type") or ""
    timing = lead.get("event_timing") or "sem_data"
    dias = lead.get("days_until_event")
    jan = _janela_do_tipo(event_type, rules)

    # ---- IDs preparados para CRM ----
    lead_id, event_id = _ids(lead)
    lead["lead_id"] = lead.get("lead_id") or lead_id
    lead["event_id"] = lead.get("event_id") or event_id

    # ---- recorrência / histórico ----
    recorrente = bool(lead.get("recurring"))
    historico = _buscar_historico(lead, leads)
    if not historico and int(lead.get("edition") or 0) >= 2:
        historico = True
    lead["recurring_event"] = recorrente
    lead["recurrence_pattern"] = _padrao_recorrencia(
        lead.get("event_name"), recorrente, lead.get("edition"))
    lead["previous_event_detected"] = historico

    # ---- contato (só o que existe em fonte) ----
    organizador = lead.get("organizer") or ""
    lead["organizer_type"] = _organizer_type(organizador)
    if organizador:
        lead["organizer_source"] = f"Citado na notícia de {lead.get('source') or 'fonte'}"
    else:
        lead["organizer_source"] = ""
    lead["organizer_url"] = lead.get("organizer_url") or ""

    # ---- patrocinadores (evidência textual) ----
    n_patro = int(lead.get("sponsors_count") or 0)
    nomes_patro = list(lead.get("sponsors") or [])
    lead["sponsors_detected"] = bool(n_patro or nomes_patro)
    lead["sponsors_evidence"] = nomes_patro

    # ---- QUEM / O QUÊ / POR QUÊ ----
    lead["potential_client_type"] = _clientes_provaveis(event_type, organizador, rules)
    lead["recommended_services"] = _servicos_recomendados(event_type, rules)
    lead["commercial_need"] = _dor(event_type, rules, lead)

    # ---- QUANDO (janela + prioridade) ----
    janela, prio = classificar_prospeccao(dias, timing, jan)
    prio, _boost = _aplicar_boost(prio, recorrente, historico,
                                  lead.get("lead_score"))
    lead["contact_window"] = janela
    lead["prospecting_priority"] = prio
    lead["recommended_contact_window"] = _window_texto(janela, jan)

    # ---- motivo e rascunho ----
    lead["contact_reason"] = _motivo(lead)
    lead["suggested_outreach"] = _rascunho(lead, rules)

    # ---- CRM futuro ----
    lead.setdefault("contact_history", [])
    lead.setdefault("notes", "")

    lead["prospecting_score"] = prospecting_score(lead, rules)
    return lead


def enriquecer_leads(rules=None):
    """Aplica a inteligência de prospecção em todos os leads salvos."""
    regras = rules or _load_rules()
    leads = ed.load_leads()
    for lead in leads.values():
        enriquecer_lead(lead, leads=leads, rules=regras)
    if leads:
        ed.save_leads(leads)
    return len(leads)


# ============================================================
# SCORE DE PROSPECÇÃO (ranking separado do TOP OPORTUNIDADES)
# ============================================================

def _fator_cidade(city):
    if not city:
        return 0.5
    regioes = []
    try:
        import analyze_article
        themes = analyze_article.load_themes()
        regioes = list(themes.get("cidades", []))
        regioes.extend((analyze_article.load_commercial_rules()
                        .get("regional", {}).get("cities", [])))
    except Exception:
        pass
    if any(a and _norm(a) == _norm(city) for a in regioes):
        return 1.0
    return 0.6


def prospecting_score(lead, rules=None):
    """Score 0-10 usado no ranking de PROSPECÇÃO (≠ lead_score).

    Ponder a proximidade, o quão fácil é achar o responsável,
    o porte, a recorrência, patrocinadores, cidade e serviços."""
    regras = rules or _load_rules()
    w = regras.get("prospecting_weights") or {}
    def peso(nome, default):
        try:
            return float(w.get(nome, default))
        except (TypeError, ValueError):
            return default

    f_lead = min(10, float(lead.get("lead_score") or 0)) / 10.0
    f_prox = ed._proximidade(lead.get("days_until_event"),
                             lead.get("event_timing") or "sem_data")
    f_org = 1.0 if lead.get("organizer") else 0.35
    f_cli = 1.0 if lead.get("potential_client_type") else 0.5
    f_porte = ed._porte_score(lead.get("estimated_audience"),
                              lead.get("porte"))
    f_rec = 1.0 if (lead.get("recurring_event")
                    or lead.get("previous_event_detected")) else 0.4
    f_sp = 1.0 if lead.get("sponsors_detected") else 0.35
    f_cid = _fator_cidade(lead.get("city"))
    f_serv = 0.9 if lead.get("recommended_services") else 0.5

    total = (peso("lead_score", 0.30) * f_lead
             + peso("proximidade", 0.22) * f_prox
             + peso("organizer", 0.10) * f_org
             + peso("client_type", 0.10) * f_cli
             + peso("porte", 0.08) * f_porte
             + peso("recorrencia", 0.06) * f_rec
             + peso("sponsors", 0.06) * f_sp
             + peso("cidade", 0.05) * f_cid
             + peso("services", 0.03) * f_serv)
    return round(max(0.0, min(10.0, total * 10.0)), 1)


def ordenados_prioridade(leads):
    """Ordena por prospecting_score decrescente (ranking de prospecção)."""
    ordem_prio = {p: i for i, p in enumerate(LADDER)}
    return sorted(
        leads,
        key=lambda l: (float(l.get("prospecting_score") or 0),
                       -ordem_prio.get(l.get("prospecting_priority"), -1)),
        reverse=True)


def top_prospeccao(limite=10, apenas_ativos=True, incluir_passados=False):
    """TOP N de PROSPECÇÃO (só eventos futuros/em curso por padrão)."""
    leads = list(ed.load_leads().values())
    ativos = (leads if not apenas_ativos
              else [l for l in leads if l.get("status") in ed.STATUS_ATIVO])
    if not incluir_passados:
        ativos = [l for l in ativos
                  if l.get("event_timing") not in ("passado",)
                  or l.get("prospecting_priority") == "muito_urgente"]
    return ordenados_prioridade(ativos)[:limite]


# ============================================================
# PAINEL (GitHub Actions / pipeline)
# ============================================================

def _fmt_data(data_iso):
    try:
        import datetime
        d = datetime.datetime.strptime(str(data_iso), "%Y-%m-%d").date()
        return d.strftime("%d/%m/%Y")
    except Exception:
        return (data_iso or "-")


def _fmt_dias(lead):
    dias = lead.get("days_until_event")
    if dias is None:
        return lead.get("event_timing") or "-"
    if lead.get("event_timing") == "passado":
        return "já realizado"
    return f"faltam {dias} dias"


def print_painel_prospeccao(limite=10):
    """Painel do diretor comercial. NUNCA envia nada, apenas imprime."""
    enriquecer_leads()
    campos = ["prospecting_score", "prospecting_priority", "contact_window"]
    leads = [l for l in ed.load_leads().values()
             if l.get("status") in ed.STATUS_ATIVO]

    print("\n" + "=" * 60)
    print("PROSPECÇÃO INTELIGENTE — PORTAL AO VIVO")
    print("=" * 60)
    if not leads:
        print("Nenhum lead ativo para prospecção ainda.")
        return []

    # ---- TOP PROSPECÇÃO (futuros/em curso) ----
    futuro = [l for l in leads if l.get("event_timing") not in ("passado",)]
    if futuro:
        print("\nTOP PROSPECÇÃO")
        print("-" * 60)
        for i, l in enumerate(ordenados_prioridade(futuro)[:limite], 1):
            _print_cartao(i, l)
        print("-" * 60)

    # ---- Acompanhamento (inclui passados) ----
    print("\nACOMPANHAMENTO (todos os ativos)")
    print("-" * 60)
    for i, l in enumerate(ordenados_prioridade(leads)[:limite], 1):
        nome = (l.get("event_name") or "?")[:40]
        cidade = l.get("city") or "-"
        prio = l.get("prospecting_priority") or "-"
        score = float(l.get("prospecting_score") or 0)
        quando = _fmt_dias(l)
        org = l.get("organizer") or l.get("organizer_type") or "-"
        print(f"{i:>2}. {nome} [{cidade}] | {prio} | {score:.1f} | "
              f"{quando} | {org}")
    return leads


def _print_cartao(i, l):
    nome = l.get("event_name") or "?"
    print(f"{i:>2}. {nome[:50]}")
    print(f"    Cidade: {l.get('city') or '-'}")
    print(f"    Evento: {_fmt_data(l.get('event_date'))} | {_fmt_dias(l)}")
    clientes = l.get("potential_client_type") or []
    print(f"    Cliente provável: {clientes[0] if clientes else '-'}")
    servicos = l.get("recommended_services") or []
    print(f"    Serviço: {', '.join(servicos) if servicos else '-'}")
    print(f"    Prioridade: {str(l.get('prospecting_priority') or '-').upper()}"
          f" | Score: {float(l.get('prospecting_score') or 0):.1f}")
    motivo = l.get("contact_reason") or ""
    if motivo:
        print(f"    Motivo: {motivo[:160]}")
    rascunho = l.get("suggested_outreach") or ""
    if rascunho:
        print(f"    Abordagem (rascunho, não enviado): {rascunho[:120]}...")


def resumo_prospeccao_json(limite=10):
    enriquecer_leads()
    return [
        {
            "rank": i,
            "lead_id": l.get("lead_id"),
            "event_name": l.get("event_name"),
            "city": l.get("city"),
            "days_until_event": l.get("days_until_event"),
            "event_timing": l.get("event_timing"),
            "prospecting_priority": l.get("prospecting_priority"),
            "contact_window": l.get("contact_window"),
            "potential_client_type": (l.get("potential_client_type") or [])[:1],
            "recommended_services": l.get("recommended_services"),
            "prospecting_score": l.get("prospecting_score"),
            "contact_reason": l.get("contact_reason"),
        }
        for i, l in enumerate(ordenados_prioridade(
            [x for x in ed.load_leads().values()
             if x.get("status") in ed.STATUS_ATIVO
             and x.get("event_timing") not in ("passado",)]), 1)
    ][:limite]


if __name__ == "__main__":
    n = enriquecer_leads()
    print(f"[PROSPECCAO] {n} lead(s) enriquecidos com inteligência de prospecção.")
    print_painel_prospeccao(limite=10)
    resumo = resumo_prospeccao_json(10)
    if resumo:
        print("\n[PROSPECCAO-COMPACT] " + json.dumps(resumo, ensure_ascii=False))