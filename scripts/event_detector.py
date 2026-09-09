# -*- coding: utf-8 -*-
"""
Detector de eventos + radar de oportunidades comerciais do Portal Ao Vivo.

Fluxo:
  detectar_evento() -> identifica se a noticia contem um evento concreto
                       (nome, cidade, data, organizador, tipo, porte, publico,
                       patrocinadores, redes sociais), o momento do evento
                       (passado/hoje/em breve/futuro) e o potencial de
                       transmissao.

  registrar_lead()   -> grava em data/commercial_leads.json uma oportunidade
                       comercial (lead) combinando evento + organizacao, com
                       lead_score (0-10) para priorizar a prospeccao.

  listar_top_leads() -> TOP N oportunidades por lead_score (radar comercial).

Regras:
  - Nunca inventa informacao: campos ausentes ficam vazios/None.
  - Evita duplicacoes: identifica por (nome do evento + cidade + data).
  - Consolidacao: mesmo evento em varias fontes completa os campos vazios.
  - Status comercial simples (nao e CRM): novo -> monitorando -> contatado ->
    proposta_enviada -> fechado/perdido.

lead_score (0-10, 1 casa decimal) pondera, em pesos configuraveis:
  commercial_score, proximidade da data (days_until_event), tamanho estimado,
  tipo do evento, cidade, recorrencia, presenca de patrocinadores,
  organizador identificavel, potencial de transmissao e potencial de conteudo.
"""
import json
import os
import re
import unicodedata
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEADS_FILE = os.path.join(BASE_DIR, "data", "commercial_leads.json")

BRT = timezone(timedelta(hours=-3))

MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "março": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
    "outubro": 10, "novembro": 11, "dezembro": 12,
}

DIAS_SEMANA = {
    "segunda": 0, "segunda-feira": 0, "terca": 1, "terça": 1, "terca-feira": 1,
    "quarta": 2, "quarta-feira": 2, "quinta": 3, "quinta-feira": 3,
    "sexta": 4, "sexta-feira": 4, "sabado": 5, "sábado": 5,
    "domingo": 6,
}

# Ciclo de vida comercial do lead. "novo" e o status inicial.
STATUS_SIMPLES = ["novo", "monitorando", "contatado", "proposta_enviada",
                  "fechado", "perdido"]
STATUS_ATIVO = ("novo", "monitorando", "contatado", "proposta_enviada")

# Pesos do lead_score (soma = 1.0)
LEAD_WEIGHTS = {
    "commercial": 0.30,   # comercial_score / 10
    "proximidade": 0.25,  # dias ate o evento (janela ideal 1-15 dias)
    "porte": 0.15,        # publico esperado / porte do evento
    "tipo": 0.08,         # tipo do evento (campeonato, festival...)
    "cidade": 0.05,       # cidade monitorada da regiao
    "recorrencia": 0.05,  # evento tradicional/recorrente
    "patrocinio": 0.05,   # patrocinadores presentes
    "organizador": 0.02,  # existe organizador identificavel
    "transmissao": 0.03,  # potencial de transmissao
    "conteudo": 0.02,     # potencial de conteudo (instagram/editorial)
}

TIPO_PESO = {
    "campeonato": 1.0, "torneio": 0.9, "corrida": 0.8, "festival": 0.9,
    "show": 0.9, "feira": 0.85, "exposicao": 0.75, "congresso": 0.8,
    "evento empresarial": 0.8, "conferencia": 0.8, "agropecuaria": 0.8,
    "rodeio": 0.7, "festa": 0.7, "formatura": 0.7, "romaria": 0.6,
    "festa religiosa": 0.6, "encontro cultural": 0.6, "inauguracao": 0.5,
    "cavalgada": 0.7,
}

RECORRENCIA_KEYWORDS = [
    "tradicional", "anual", "todo ano", "todos os anos", "edicao", "edição",
    "aniversario da cidade", "aniversário da cidade", "jubileu", "festa do padroeiro",
    "festa anual", "festa tradicional", "festa do cafe", "festa do café",
    "semana cultural", "rota do cafe", "rota do café", "exposicao anual",
    "evento anual", "concurso anual",
]


def _norm(texto):
    """Remove acentos e normaliza para comparacao sem variacao de maiusculas."""
    if not texto:
        return ""
    texto = unicodedata.normalize("NFKD", texto or "")
    return u"".join(c for c in texto if not unicodedata.combining(c)).lower()


def agora_brt():
    return datetime.now(BRT)


CONECTIVOS = re.compile(
    r"\s(?:para|em|no|na|nos|neste|nesta|neste|recebeu|recebe|acontece|"
    r"acontecer[áa]|vai|ter[áa]|tem|anuncia|anunciou|ser[áa]|com|durante|"
    r"abre|ter|que|reuniu|movimenta|movimentou|daqui)\b",
    re.IGNORECASE,
)


def _limpar_nome(nome):
    nome = re.sub(r"\s+", " ", nome).strip(" .!?;,")
    m = CONECTIVOS.search(nome)
    if m:
        nome = nome[:m.start()].strip()
    if len(nome) > 50:
        corte = nome.rfind(" ", 0, 50)
        if corte > 0:
            nome = nome[:corte].strip()
    nome = nome.strip(" .!?;,")
    return nome[:1].upper() + nome[1:] if nome else nome


def _capturar_grupo_frase(titulo, texto):
    """Extrai uma frase contendo um nome de evento apos palavra-chave."""
    alvo = (titulo or "") + ". " + (texto or "")
    padrao = (
        r"(Festa|Festival|Feira|Show|Congresso|Campeonato|Torneio|Rodeio|"
        r"Romaria|Encontro|Exposição|Exposicao|Copa|Semana Cultural|Convenção|"
        r"Convencao|Maratona|Carreata|Desfile|Corrida|Quermesse|Formatura|"
        r"Jubileu|Simpósio|Simposio|Leilão|Leilao)\b[^.!?;]{2,70}"
    )
    m = re.search(padrao, alvo, re.IGNORECASE)
    if m:
        nome = _limpar_nome(m.group(0))
        if 3 <= len(nome) <= 90:
            return nome
    return None


def detectar_event_name(titulo, texto):
    nome = _capturar_grupo_frase(titulo, texto)
    if nome:
        return nome
    # Fallback: titulo com palavra-chave de evento, cortado nos conectivos
    alvo = (titulo or "").strip()
    if 4 <= len(alvo) <= 90:
        return _limpar_nome(alvo)
    return None


def detectar_city(texto, themes):
    """Acha a primeira cidade regional mencionada."""
    t = texto or ""
    cidades = []
    if themes:
        cidades = list(themes.get("cidades", []))
    for c in sorted(cidades, key=len, reverse=True):
        if _norm(c) in _norm(t):
            return c
    return None


def detectar_organizer(texto, city):
    t = (texto or "")
    tn = _norm(t)

    if "prefeitura" in tn:
        return f"Prefeitura de {city}" if city else "Prefeitura Municipal"

    if "camara municipal" in tn:
        return f"Câmara Municipal de {city}" if city else "Câmara Municipal"

    m = re.search(r"(Secretaria\s+(?:Municipal\s+)?de\s+[A-ZÀ-Ú][\wÀ-úºª\'\-]+)", t)
    if m:
        return m.group(1)

    m = re.search(r"(Liga\s+[A-ZÀ-Ú][\wÀ-úºª\'\-]+(?:\s+[A-ZÀ-Ú][\wÀ-úºª\'\-]+)?)", t)
    if m:
        return m.group(1)

    m = re.search(r"(Clube\s+[A-ZÀ-Ú][\wÀ-úºª\'\-]+(?:\s+[A-ZÀ-Ú][\wÀ-úºª\'\-]+)?)", t)
    if m:
        return m.group(1)

    if "sindicato" in tn or "associacao" in tn or "associação" in tn:
        return "Associação/Sindicato local"

    return None


def _data_proxima(ano, mes, dia):
    try:
        d = datetime(ano, mes, dia)
    except ValueError:
        return None
    if d.date() < datetime.now(BRT).date():
        d = datetime(ano + 1, mes, dia)
    return d.date().isoformat()


def detectar_date(titulo, texto):
    alvo = (titulo or "") + ". " + (texto or "")
    t = _norm(alvo)
    hoje = datetime.now(BRT).date()

    # 15 de outubro de 2026 | 15 de outubro
    m = re.search(r"(\d{1,2})\s+de\s+([a-zç]+)(?:\s+de\s+(\d{4}))?", t)
    if m:
        dia = int(m.group(1))
        mes = MESES.get(m.group(2))
        if mes and 1 <= dia <= 31:
            if m.group(3):
                return _data_proxima(int(m.group(3)), mes, dia)
            ano = hoje.year if (mes, dia) >= (hoje.month, hoje.day) else hoje.year + 1
            return _data_proxima(ano, mes, dia)

    # 15/10 ou 15/10/2026
    m = re.search(r"(\d{1,2})/(\d{1,2})(?:/(\d{4}))?", t)
    if m:
        dia, mes = int(m.group(1)), int(m.group(2))
        if 1 <= dia <= 31 and 1 <= mes <= 12:
            if m.group(3):
                return _data_proxima(int(m.group(3)), mes, dia)
            ano = hoje.year if (mes, dia) >= (hoje.month, hoje.day) else hoje.year + 1
            return _data_proxima(ano, mes, dia)

    # daqui a N dias
    m = re.search(r"daqui\s+a\s+(\d+)\s+dias?", t)
    if m:
        from datetime import timedelta as td
        return (hoje + td(days=int(m.group(1)))).isoformat()

    # proxima segunda/terca/... ou proximo sabado/domingo
    m = re.search(r"prox[io]ma?\s+([a-zç-]+)", t)
    if m:
        dia_cv = DIAS_SEMANA.get(m.group(1))
        if dia_cv is not None:
            delta = (dia_cv - hoje.weekday()) % 7
            if delta == 0:
                delta = 7
            from datetime import timedelta as td
            return (hoje + td(days=delta)).isoformat()

    # "no mes de X", "em outubro" ou "para outubro"
    m = re.search(r"(?:no\s+mes\s+de\s+|em\s+|para\s+(?:o\s+mes\s+de\s+|o\s+)?)([a-zç]+)", t)
    if m and m.group(1) in MESES:
        mes = MESES[m.group(1)]
        ano = hoje.year if mes > hoje.month else hoje.year + 1
        return _data_proxima(ano, mes, 1)

    # "acontece domingo", "sera neste sabado", "realiza-se na quinta"
    for nome_dia, val in DIAS_SEMANA.items():
        if re.search(r"(acontece\b|acontecer[áa]\b|ser[áa]\b|neste|nesta|no dia|realiza)",
                     t) and re.search(r"(^|[\s,;])" + re.escape(nome_dia) + r"\b", t):
            delta = (val - hoje.weekday()) % 7
            if delta == 0:
                delta = 7
            from datetime import timedelta as td
            return (hoje + td(days=delta)).isoformat()

    return None


def detectar_publico_esperado(titulo, texto):
    alvo = (titulo or "") + ". " + (texto or "")
    t = _norm(alvo)
    m = re.search(r"(\d+(?:\.\d{3})*(?:[.,]\d+)?)\s*(mil)?\s*"
                  r"(pessoas|visitantes|participantes|espectadores|publico|ingressos)",
                  t)
    if not m:
        return None
    valor = float(m.group(1).replace(".", "").replace(",", "."))
    if m.group(2):
        valor *= 1000
    return int(valor)


def detectar_porte(publico_esperado):
    if not publico_esperado:
        return None
    if publico_esperado < 1000:
        return "pequeno"
    if publico_esperado < 5000:
        return "medio"
    return "grande"


def detectar_patrocinadores(titulo, texto):
    alvo = (titulo or "") + ". " + (texto or "")
    t = _norm(alvo)
    nomes = re.findall(r"patrocinad\w+", t)
    if not nomes:
        return (0, None)
    # Conta mencoes indiretas: "15 patrocinadores" / "patrocinado por X"
    m = re.search(r"(\d+)\s*patrocinad", t)
    total = int(m.group(1)) if m else len(nomes)
    m2 = re.search(r"patrocinad\w+\s+(?:por|pelo|pela)\s+([A-Za-zÀ-ÿºª][\w Á-ÿºª\'\-]{2,40})", alvo)
    nomes_lista = [m2.group(1)] if m2 else None
    return (total, nomes_lista)


def detectar_redes(titulo, texto):
    alvo = (titulo or "") + " " + (texto or "")
    resultado = {"website": "", "instagram": ""}
    m = re.search(r"https?://[^\s\"'\)]+", alvo)
    if m:
        resultado["website"] = m.group(0)
    m = re.search(r"(instagram\.com/[A-Za-z0-9_.]+|@[A-Za-z0-9_]{2,30})", alvo)
    if m:
        resultado["instagram"] = m.group(1)
    return resultado


def detectar_recorrencia(titulo, texto):
    """Detecta se o evento e recorrente/tradicional (ex.: Festa do Cafe anual)."""
    alvo = _norm((titulo or "") + " " + (texto or ""))
    edicao = None
    m = re.search(r"(\d{1,3})\s*[a-zªº]*\s*edicao", alvo)
    if m:
        edicao = int(m.group(1))
    if any(_norm(k) in alvo for k in RECORRENCIA_KEYWORDS):
        return (True, edicao)
    return (False, edicao)


FUTURO_PADRAO = re.compile(
    r"(acontecer[áa]|ser[áa] realizado|vai (acontecer|ocorrer|ter|ser)|"
    r"ser[áa] (no|na|em|realizado)|acontece (em|no|na|neste|nesta|dia)|"
    r"realiza-se|est[áa] previsto|previst[oa] para|marcad[oa] para|prev[êe]|"
    r"expectativa|confirmad|agendad|est[áa] chegando|abre em|ser[áa] aberto)",
    re.IGNORECASE)

PASSADO_PADRAO = re.compile(
    r"(aconteceu|realizou|foi realizado|foi marcad|bateu|quebrou recorde|"
    r"registrou recorde|reuniu|movimentou|ocorreu|realizou-se|se encerrou|"
    r"encerrou|foi sucesso|passou|fez a abertura|recebeu (mil|muitas)|"
    r"veio recheado|baixou a cortina|terminou|terminou no|no [a-zç]+ passad)",
    re.IGNORECASE)


def classificar_temporal(titulo, texto, event_date):
    """Classifica momento do evento e calcula dias ate ele.

    Retorna {"timing": str, "days_until": int|None}.
    timing: "passado" | "hoje" | "em_breve" | "futuro" | "sem_data"
    """
    alvo = (titulo or "") + ". " + (texto or "")
    hoje = datetime.now(BRT).date()

    if event_date:
        try:
            data_evento = datetime.strptime(event_date, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            data_evento = None
        if data_evento:
            dias = (data_evento - hoje).days
            if dias < 0:
                return {"timing": "passado", "days_until": dias}
            if dias == 0:
                return {"timing": "hoje", "days_until": 0}
            if dias <= 14:
                return {"timing": "em_breve", "days_until": dias}
            return {"timing": "futuro", "days_until": dias}

    if FUTURO_PADRAO.search(alvo):
        return {"timing": "futuro", "days_until": None}
    if PASSADO_PADRAO.search(alvo):
        return {"timing": "passado", "days_until": None}
    if re.search(r"mil\s*(pessoas|visitantes|espectadores)", _norm(alvo)):
        # publico realizado normalmente indica evento que ja aconteceu
        return {"timing": "passado", "days_until": None}
    return {"timing": "sem_data", "days_until": None}


# ============================================================
# LEAD SCORE
# ============================================================

def _proximidade(dias, timing):
    if dias is None:
        if timing == "passado":
            return 0.1
        if timing == "em_breve":
            return 1.0
        if timing == "futuro":
            return 0.5
        return 0.35
    if timing == "passado":
        return 0.1
    if dias <= 0:
        return 0.5
    if dias <= 15:
        return 1.0
    if dias <= 30:
        return 0.9
    if dias <= 45:
        return 0.8
    if dias <= 60:
        return 0.7
    if dias <= 90:
        return 0.6
    if dias <= 180:
        return 0.45
    return 0.3


def _porte_score(publico, porte):
    if publico:
        if publico >= 50000:
            return 1.0
        if publico >= 20000:
            return 0.9
        if publico >= 10000:
            return 0.8
        if publico >= 5000:
            return 0.7
        if publico >= 1000:
            return 0.5
        if publico >= 300:
            return 0.3
        return 0.2
    mapa = {"grande": 0.85, "medio": 0.55, "pequeno": 0.25}
    return mapa.get(porte, 0.4)


def _tipo_score(event_type):
    tipo = (event_type or "")
    if isinstance(tipo, list):
        tipo = tipo[0] if tipo else ""
    return TIPO_PESO.get(str(tipo).strip(), 0.5)


def _cidade_score(city, themes, rules):
    if not city:
        return 0.5
    regioes = []
    if themes:
        regioes.extend(themes.get("cidades", []))
    regioes.extend((rules or {}).get("regional", {}).get("cities", []))
    if any(_norm(c) and _norm(c) == _norm(city) for c in regioes):
        return 1.0
    return 0.6


def _organizador_score(organizer):
    return 1.0 if organizer else 0.4


def calcular_lead_score(evento, analise, rules=None, themes=None):
    """Calcula o lead_score (0-10) a partir do evento + analise.

    Pondera: commercial, proximidade, porte, tipo, cidade, recorrencia,
    patrocinio, organizador, transmissao e conteudo.
    """
    analise = analise or {}
    evento = evento or {}
    rules = rules or {}
    themes = themes or {}

    comercial = max(0, min(10, int(analise.get("commercial_score", 0) or 0)))
    timing = evento.get("event_timing", "sem_data")
    dias = evento.get("days_until")
    publico = evento.get("publico_esperado")
    porte = evento.get("porte")
    tipo = evento.get("event_type") or (analise.get("event_type") or [])
    city = evento.get("event_city")
    recurring, edicao = evento.get("recurring", False), evento.get("edition")
    patrocinadores = evento.get("patrocinadores") or []
    n_patro = int(evento.get("patrocinadores_count") or 0)
    organizador = evento.get("organizer")
    transm = min(10, int(evento.get("transmission_opportunity") or 1))
    conteudo = max(int(analise.get("instagram_score", 5) or 0),
                   int(analise.get("editorial_score", 5) or 0))

    w = LEAD_WEIGHTS
    total = (w["commercial"] * (comercial / 10.0)
             + w["proximidade"] * _proximidade(dias, timing)
             + w["porte"] * _porte_score(publico, porte)
             + w["tipo"] * _tipo_score(tipo)
             + w["cidade"] * _cidade_score(city, themes, rules)
             + w["recorrencia"] * (1.0 if recurring else 0.4)
             + w["patrocinio"] * (1.0 if (n_patro >= 1 or patrocinadores
                                          or analise.get("sponsorship_related")) else 0.35)
             + w["organizador"] * _organizador_score(organizador)
             + w["transmissao"] * (transm / 10.0)
             + w["conteudo"] * (conteudo / 10.0))
    return round(max(0.0, min(10.0, total * 10.0)), 1)


def _label_lead_score(score):
    if not score:
        return "BAIXA"
    if score >= 9:
        return "MUITO FORTE"
    if score >= 7.5:
        return "FORTE"
    if score >= 6:
        return "MEDIA"
    return "BAIXA"


def detectar_evento(item, analise, themes, rules=None):
    """Detecta um evento concreto na noticia.

    Retorna dict com event_detected e todos os campos do evento
    (incluindo event_timing, days_until, recurring/edition).
    Nunca inventa: campos ausentes ficam None/"".
    """
    titulo = item.get("titulo", "")
    texto = item.get("texto", "")
    analise = analise or {}
    rules = rules or {}

    if not analise.get("event_related"):
        return {
            "event_detected": False,
            "event_name": None,
            "event_city": None,
            "event_date": None,
            "event_type": None,
            "organizer": None,
            "website": "",
            "instagram": "",
            "transmission_opportunity": 0,
            "event_timing": "sem_data",
            "days_until": None,
            "recurring": False,
            "edition": None,
        }

    event_name = detectar_event_name(titulo, texto)
    city = detectar_city(titulo + " " + texto, themes)
    date = detectar_date(titulo, texto)
    organizer = detectar_organizer(titulo + " " + texto, city)
    tipo = (analise.get("event_type") or [])
    event_type = tipo[0] if tipo else None
    publico = detectar_publico_esperado(titulo, texto)
    porte = detectar_porte(publico)
    n_patro, patrocinadores = detectar_patrocinadores(titulo, texto)
    redes = detectar_redes(titulo, texto)
    recurring, edicao = detectar_recorrencia(titulo, texto)
    temporal = classificar_temporal(titulo, texto, date)

    # Se publico realizado foi noticiado e o texto nao marca futuro,
    # o evento provavelmente ja aconteceu (classificacao mais precisa).
    if temporal["timing"] == "futuro" and publico and PASSADO_PADRAO.search(texto or ""):
        temporal = {"timing": "passado", "days_until": None}

    comerc = int(analise.get("commercial_score", 0) or 0)
    opportunity = min(10, comerc + 1) if analise.get("event_related") else 0

    return {
        "event_detected": True,
        "event_name": event_name,
        "event_city": city,
        "event_date": date,
        "event_type": event_type,
        "organizer": organizer,
        "porte": porte,
        "publico_esperado": publico,
        "patrocinadores_count": n_patro,
        "patrocinadores": patrocinadores,
        "website": redes.get("website", ""),
        "instagram": redes.get("instagram", ""),
        "transmission_opportunity": opportunity,
        "event_timing": temporal["timing"],
        "days_until": temporal["days_until"],
        "recurring": recurring,
        "edition": edicao,
    }


# ============================================================
# LEADS
# ============================================================

def load_leads():
    if os.path.exists(LEADS_FILE):
        try:
            with open(LEADS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "leads" in data:
                return data["leads"]
            return dict(data) if isinstance(data, dict) else {"leads": {}}
        except Exception:
            return {}
    return {}


def save_leads(leads):
    os.makedirs(os.path.dirname(LEADS_FILE), exist_ok=True)
    with open(LEADS_FILE, "w", encoding="utf-8") as f:
        json.dump({"leads": leads, "atualizado": agora_brt().isoformat()},
                  f, ensure_ascii=False, indent=2)


def _chave_lead(event_name, city, date):
    return (event_name or "evento") + "|" + (city or "") + "|" + (date or "")


def _norm_chave_leads():
    """Agrupamento auxiliar para consolidar leads do mesmo evento/cidade."""
    return {}


def _encontrar_existente(leads, event_name, city, date):
    """Acha lead existente do mesmo evento (mesmo nome+cidade), consolidando datas."""
    if not event_name:
        return None
    base_nome = _norm(event_name)
    base_city = _norm(city or "")
    for chave, lead in leads.items():
        nome_atual = _norm(lead.get("event_name") or "")
        cidade_atual = _norm(lead.get("city") or "")
        if nome_atual != base_nome:
            continue
        if base_city and cidade_atual and base_city != cidade_atual:
            continue
        data_atual = lead.get("event_date") or ""
        # Mesma data, ou uma delas sem data -> consolida
        if (not date) or (not data_atual) or data_atual == date:
            return (chave, lead)
    return None


def _mesclar_lead(existente, novo):
    if not existente:
        return novo
    for campo, valor in novo.items():
        if valor and not existente.get(campo):
            existente[campo] = valor
        if campo in ("commercial_score", "transmission_opportunity",
                     "lead_score", "instagram_score", "days_until_event"):
            try:
                if float(valor or 0) > float(existente.get(campo, 0) or 0):
                    existente[campo] = valor
            except (TypeError, ValueError):
                pass
    return existente


def _lead_completo(item, analise, evento, rules, themes):
    """Monta o lead no schema padrao (sem status/detected_at)."""
    analise = analise or {}
    evento = evento or {}
    regras = rules or {}

    event_name = evento.get("event_name") or item.get("titulo", "Evento identificado")[:60]
    city = evento.get("event_city") or ""
    date = evento.get("event_date") or ""
    publico = evento.get("publico_esperado")
    timing = evento.get("event_timing", "sem_data")
    dias = evento.get("days_until")
    recurring = bool(evento.get("recurring"))
    edicao = evento.get("edition")
    comerc = int(analise.get("commercial_score", 0) or 0)

    lead = {
        "lead_score": calcular_lead_score(evento, analise, rules, themes),
        "priority": "",
        "event_name": event_name,
        "event_type": evento.get("event_type") or "",
        "city": city,
        "event_date": date,
        "days_until_event": dias,
        "event_timing": timing,
        "organizer": evento.get("organizer") or "",
        "estimated_audience": publico,
        "porte": evento.get("porte") or "",
        "recurring": recurring,
        "edition": edicao,
        "sponsors": list(evento.get("patrocinadores") or []),
        "sponsors_count": int(evento.get("patrocinadores_count") or 0),
        "source": item.get("fonte", ""),
        "source_url": item.get("link", ""),
        "commercial_angle": analise.get("commercial_angle") or "",
        "suggested_services": list(analise.get("suggested_service") or []),
        "target_customer": list(analise.get("target_customer") or []),
        "commercial_score": comerc,
        "instagram_score": int(analise.get("instagram_score", 5) or 5),
        "transmission_opportunity": int(evento.get("transmission_opportunity") or 0),
        "status": "novo",
    }
    lead["priority"] = _label_lead_score(lead["lead_score"])
    if recurring and edicao and event_name:
        lead["event_name"] = event_name
    return lead


def registrar_lead(item, analise, evento, rules=None, themes=None):
    """Registra/consolida um lead comercial em data/commercial_leads.json.

    So cria lead quando event_detected e commercial_score >= lead.min_score.
    Apos salvar/atualizar, enriquece o lead com a inteligencia de prospeccao
    (commercial_prospecting): potencial cliente, servico, dor, janela,
    prioridade, motivo e rascunho de abordagem.
    Retorna dict com status e lead.
    """
    analise = analise or {}
    evento = evento or {}
    if not evento.get("event_detected"):
        return {"status": "sem_evento", "lead": None}

    regras = rules or {}
    min_score = (regras.get("lead") or {}).get("min_score", 5)
    comerc = int(analise.get("commercial_score", 0) or 0)
    if comerc < min_score:
        return {"status": "score_baixo", "lead": None}

    novo = _lead_completo(item, analise, evento, rules, themes)
    chave = _chave_lead(novo["event_name"][:60], novo["city"], novo["event_date"])

    leads = load_leads()
    achado = _encontrar_existente(leads, novo["event_name"], novo["city"],
                                  novo["event_date"])
    agora = agora_brt().isoformat()
    novo["updated_at"] = agora

    # Import lazy: evita ciclo (commercial_prospecting importa event_detector)
    try:
        from commercial_prospecting import enriquecer_lead
    except Exception as e:
        print(f"[PROSPECCAO] camada de prospeccao indisponivel: {e}")
        enriquecer_lead = None

    if achado:
        chave_old, existente = achado
        # Nao regressar status comercial: mantem o ciclo de vida do lead
        status_atual = existente.get("status")
        if status_atual and status_atual not in STATUS_SIMPLES:
            status_atual = "novo"
        novo["status"] = status_atual or "novo"
        if novo["status"] == "novo" and novo["source_url"] != existente.get("source_url"):
            pass  # continua "novo"; datas/fontes adicionais sao consolidadas

        _mesclar_lead(existente, novo)
        # Registrar fonte adicional sem duplicar
        sources = existente.setdefault("sources", [])
        if existente["source_url"] != novo["source_url"]:
            sources.append({
                "source_url": novo["source_url"],
                "fonte": novo["source"],
                "detected_at": agora,
            })
        existente["updated_at"] = agora
        if enriquecer_lead:
            ex_prose = enriquecer_lead(existente, leads=leads)
            if ex_prose is not None:
                existente = ex_prose
        leads[chave_old] = existente
        save_leads(leads)
        return {"status": "atualizado", "lead": existente}

    novo["detected_at"] = agora
    novo["status"] = "novo"
    if enriquecer_lead:
        novo_enriq = enriquecer_lead(novo, leads=leads)
        if novo_enriq is not None:
            novo = novo_enriq
    leads[chave] = novo
    save_leads(leads)
    return {"status": "novo", "lead": novo}


def listar_leads():
    return list(load_leads().values())


def listar_top_leads(limite=10, apenas_ativos=True):
    """TOP N oportunidades por lead_score (ordem decrescente)."""
    leads = listar_leads()
    if apenas_ativos:
        leads = [l for l in leads if l.get("status") in STATUS_ATIVO]
    return sorted(leads, key=lambda l: float(l.get("lead_score") or 0),
                  reverse=True)[:limite]


def print_top_leads(limite=10):
    """Imprime o ranking de oportunidades (usado no log do pipeline e CI)."""
    topo = listar_top_leads(limite)
    print("\n" + "=" * 60)
    print(f"RADAR COMERCIAL - TOP {len(topo)} OPORTUNIDADES")
    print("=" * 60)
    if not topo:
        print("Nenhuma oportunidade registrada ainda.")
        return topo
    for i, l in enumerate(topo, 1):
        nome = (l.get("event_name") or "?")[:45]
        cidade = l.get("city") or "-"
        score = float(l.get("lead_score") or 0)
        dias = l.get("days_until_event")
        quando = f"em {dias}d" if dias is not None and l.get("event_timing") != "passado" else (l.get("event_timing") or "-")
        print(f"{i:>2}. {nome} [{cidade}] - {score:.1f} ({quando}, {l.get('status')})")
    return topo


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import collect
    from analyze_article import analisar_noticia, load_themes, load_commercial_rules

    themes = load_themes()
    rules = load_commercial_rules()
    teste = {
        "titulo": "Prefeitura anuncia grande festival para outubro com expectativa de 30 mil pessoas",
        "texto": "A Prefeitura de Patos de Minas anunciou um grande festival para outubro no parque de exposições. A expectativa é de 30 mil pessoas durante os quatro dias de programação, com shows e praça de alimentação.",
        "tema": "Local e Cidades",
        "fonte": "Prefeitura de Patos de Minas",
        "link": "https://patosdeminas.mg.gov.br/noticia/x",
    }
    analise = analisar_noticia(teste, api_key=os.environ.get("GEMINI_API_KEY", ""),
                               themes=themes, rules=rules)
    evento = detectar_evento(teste, analise, themes, rules)
    print(json.dumps(evento, ensure_ascii=False, indent=2))
    res = registrar_lead(teste, analise, evento, rules, themes)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    print_top_leads()