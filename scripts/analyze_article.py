# -*- coding: utf-8 -*-
"""
INTELIGÊNCIA EDITORIAL + COMERCIAL do Portal Ao Vivo.

Filosofia editorial (obrigatória):
    "O Portal Ao Vivo é primeiro um portal de notícias e também uma
     empresa de transmissão audiovisual."

    NOTÍCIA > PROPAGANDA

A camada comercial existe para IDENTIFICAR oportunidades e inserir
contexto comercial apenas quando for editorialmente justificável.

Fluxo:
    NOTÍCIA -> CONTEXTO -> OPORTUNIDADE -> SERVIÇO

Este módulo:
  - analisar_noticia(): produz análise estruturada com 3 scores
    (editorial, comercial, Instagram), categoria, flags de assunto,
    ângulo comercial, serviços sugeridos e CTAs.
  - Usa IA (Gemini) quando disponível. Se a IA falhar, usa regras
    locais configuráveis (config/commercial_rules.json). Se nem as
    regras existirem, usa valores padrão e NUNCA quebra o pipeline.
  - gerar_conteudo_social(): gera Reel/Stories/Carousel quando o
    potencial social/comercial justificar.

Scores (0-10):
  editorial_score : valor da notícia como conteúdo jornalístico
  commercial_score: potencial de gerar demanda pelos serviços do portal
  instagram_score : potencial de virar Reel/Stories/carrossel

Regra de intensidade comercial:
  0-4 : não mencionar serviço nem fazer CTA
  5-6 : apenas conexão editorial natural
  7-8 : menção discreta ao serviço
  9-10: pode gerar CTA comercial direto (sem virar anúncio)
"""
import json
import os
import re
import unicodedata

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMMERCIAL_RULES_FILE = os.path.join(BASE_DIR, "config", "commercial_rules.json")
SOCIAL_RULES_FILE = os.path.join(BASE_DIR, "config", "social_rules.json")
THEMES_FILE = os.path.join(BASE_DIR, "themes.json")

CATEGORY_POR_TEMA = {
    "Esportes": "esportes",
    "Política": "politica",
    "Politica": "politica",
    "Local e Cidades": "cidades",
    "Geral": "geral",
    "Historia Regional": "cultura",
}

CATEGORY_POR_TRIGGER = {
    "campeonato": "esportes",
    "corrida": "esportes",
    "record_publico": "eventos",
    "recorde_publico": "eventos",
    "grande_evento": "eventos",
    "evento_municipal": "eventos",
    "evento_empresarial": "eventos",
    "evento_agropecuario": "geral",
    "formatura": "eventos",
    "evento_religioso": "eventos",
    "conferencia": "eventos",
    "inauguracao": "cidades",
    "streaming": "streaming",
    "recorde_audiencia": "streaming",
    "patrocinio": "marketing",
}


def _norm(texto):
    if not texto:
        return ""
    texto = unicodedata.normalize("NFKD", texto or "")
    return u"".join(c for c in texto if not unicodedata.combining(c)).lower()


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _carregar(filename):
    if os.path.exists(filename):
        try:
            return load_json(filename)
        except Exception as e:
            print(f"[ANALYZER] Config invalida em {filename}: {e}")
    return {}


def load_commercial_rules():
    return _carregar(COMMERCIAL_RULES_FILE)


def load_social_rules():
    return _carregar(SOCIAL_RULES_FILE)


def load_themes():
    return _carregar(THEMES_FILE)


# ============================================================
# ESTRUTURA PADRAO / NORMALIZACAO
# ============================================================

def _default_analise():
    return {
        "publish": True,
        "editorial_score": 5,
        "commercial_score": 0,
        "instagram_score": 5,
        "category": "geral",
        "event_related": False,
        "sports_related": False,
        "streaming_related": False,
        "technology_related": False,
        "sponsorship_related": False,
        "event_type": [],
        "commercial_angle": "",
        "target_customer": [],
        "suggested_service": [],
        "reason": "",
        "generate_reel": False,
        "generate_cta": False,
        "regional": False,
    }


def _coerce_bool(valor, default=False):
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, (int, float)):
        return bool(valor)
    if isinstance(valor, str):
        return valor.strip().lower() in ("true", "1", "sim", "yes")
    return default


def _coerce_score(valor, default=5):
    try:
        num = float(valor)
        return max(0, min(10, int(round(num))))
    except (TypeError, ValueError):
        return default


def _coerce_lista(valor):
    if isinstance(valor, list):
        return [str(x).strip() for x in valor if str(x).strip()]
    if isinstance(valor, str):
        return [x.strip() for x in valor.split(",") if x.strip()]
    return []


def normalizar_analise(dados):
    """Normaliza qualquer resposta (IA ou regras) para o formato padrao.

    Trata: JSON incompleto, campos ausentes, valores fora de 0-10,
    tipos errados.
    """
    d = dados or {}
    base = _default_analise()
    analise = {}
    for k, v_default in base.items():
        analise[k] = d.get(k, v_default)

    analise["publish"] = _coerce_bool(d.get("publish", True), True)
    analise["editorial_score"] = _coerce_score(
        d.get("editorial_score", base["editorial_score"]), base["editorial_score"])
    analise["commercial_score"] = _coerce_score(
        d.get("commercial_score", base["commercial_score"]), base["commercial_score"])
    analise["instagram_score"] = _coerce_score(
        d.get("instagram_score", base["instagram_score"]), base["instagram_score"])

    for flag in ("event_related", "sports_related", "streaming_related",
                 "technology_related", "sponsorship_related"):
        analise[flag] = _coerce_bool(d.get(flag, False), False)

    analise["category"] = (d.get("category") or base["category"] or "geral")
    analise["commercial_angle"] = (d.get("commercial_angle") or "").strip()
    analise["reason"] = (d.get("reason") or "").strip()
    analise["event_type"] = _coerce_lista(d.get("event_type"))
    analise["target_customer"] = _coerce_lista(d.get("target_customer"))
    analise["suggested_service"] = _coerce_lista(d.get("suggested_service"))

    analise["generate_reel"] = _coerce_bool(d.get("generate_reel"), False)
    analise["generate_cta"] = _coerce_bool(d.get("generate_cta"), False)

    # Garantir coerencia entre scores e flags de geracao
    if analise["instagram_score"] >= 8 or analise["commercial_score"] >= 8:
        analise["generate_reel"] = True
    if analise["commercial_score"] >= 7:
        analise["generate_cta"] = True
    return analise


# ============================================================
# ANALISE COM IA (Gemini)
# ============================================================

PROMPT_ANALISE = (
    "Você é o editor de inteligência editorial e comercial do 'Portal Ao Vivo', "
    "um portal de notícias regional que também presta serviços de transmissão ao "
    "vivo, cobertura audiovisual, produção multicâmera, transmissão esportiva e "
    "conteúdo para redes sociais.\n\n"
    "Filosofia: o Portal Ao Vivo é PRIMEIRO um portal de notícias e também uma "
    "empresa de transmissão audiovisual. NOTÍCIA > PROPAGANDA.\n\n"
    "Analise a notícia abaixo e responda APENAS com um JSON válido, sem markdown, "
    "sem comentários. Não invente informações que não estejam no texto.\n\n"
    "Esquema do JSON (use exatamente estas chaves):\n"
    "{\n"
    '  "publish": true/false,                      // vale publicar?\n'
    '  "editorial_score": 0-10,                    // valor jornalístico\n'
    '  "commercial_score": 0-10,                   // potencial de gerar demanda pelos serviços\n'
    '  "instagram_score": 0-10,                    // potencial de viralizar no Instagram\n'
    '  "category": "ex: eventos, esportes, cidades, politica, tecnologia, streaming, geral",\n'
    '  "event_related": true/false,                // fala de evento (festa, feira, competição...)\n'
    '  "sports_related": true/false,\n'
    '  "streaming_related": true/false,\n'
    '  "technology_related": true/false,\n'
    '  "sponsorship_related": true/false,          // fala de patrocínio/marcas\n'
    '  "event_type": ["ex: festival", "show"],     // tipos de evento detectados\n'
    '  "commercial_angle": "ex: alcance, audiencia, esporte, visibilidade, empresarial ou vazio",\n'
    '  "target_customer": ["ex: organizador de eventos", "prefeitura"],\n'
    '  "suggested_service": ["ex: transmissao ao vivo", "cobertura audiovisual"],\n'
    '  "reason": "frase curta explicando o potencial",\n'
    '  "generate_reel": true/false,\n'
    '  "generate_cta": true/false\n'
    "}\n\n"
    "Regras de pontuação:\n"
    "- Campeonato regional importante: editorial 10, comercial 10, instagram 10.\n"
    "- Prefeitura anuncia grande festival: editorial 10, comercial 10, instagram 9.\n"
    "- Festival bate recorde de público: editorial 9, comercial 9, instagram 10.\n"
    "- Nova câmera profissional lançada: editorial 5, comercial 4, instagram 7.\n"
    "- Notícia política sem eventos: editorial 8, comercial 1, instagram 4.\n"
    "- Celebridade lançou produto: editorial 3, comercial 1, instagram 7.\n\n"
    "IMPORTANTE: detectar eventos que indiquem NECESSIDADE de transmissão mesmo "
    "sem a palavra 'streaming' (ex: grande público, final de campeonato, festa "
    "municipal futura, congresso para milhares de participantes, evento com muitos "
    "patrocinadores).\n\n"
    "TÍTULO: {titulo}\n\nTEXTO:\n{texto}"
)


def _extrair_json(resposta):
    """Extrai o primeiro JSON válido de uma resposta (tolera markdown)."""
    if not resposta:
        return None
    texto = resposta.strip()
    if texto.startswith("```"):
        texto = re.sub(r"^```(?:json)?\s*", "", texto, flags=re.IGNORECASE)
        texto = re.sub(r"\s*```$", "", texto)
    try:
        return json.loads(texto)
    except Exception:
        pass
    inicio = texto.find("{")
    if inicio == -1:
        return None
    profundidade = 0
    em_string = False
    escape = False
    for i in range(inicio, len(texto)):
        c = texto[i]
        if escape:
            escape = False
            continue
        if c == "\\":
            escape = True
            continue
        if c == '"':
            em_string = not em_string
            continue
        if em_string:
            continue
        if c == "{":
            profundidade += 1
        elif c == "}":
            profundidade -= 1
            if profundidade == 0:
                try:
                    return json.loads(texto[inicio:i + 1])
                except Exception:
                    return None
    return None


def _analisar_ia(titulo, texto, api_key):
    import summarize
    prompt = PROMPT_ANALISE.format(
        titulo=(titulo or "")[:300],
        texto=(texto or "")[:9000],
    )
    resposta = summarize._gerar(prompt, api_key, temperature=0.2, max_tokens=900)
    dados = _extrair_json(resposta)
    if not dados:
        raise ValueError("IA não retornou JSON válido")
    return dados


# ============================================================
# ANALISE POR REGRAS (fallback sem IA)
# ============================================================

def _eh_regional(texto, themes, rules):
    alvo = _norm(texto)
    regras = rules or {}
    regioes = []
    if themes:
        regioes.extend(themes.get("cidades", []))
    regioes.extend((regras.get("regional") or {}).get("cities", []))
    for c in regioes:
        if c and _norm(c) in alvo:
            return True
    return False


def _detectar_tipos(tn):
    tipos = []
    mapa = {
        "festival": "festival", "festa": "festa", "feira": "feira",
        "show": "show", "rodeio": "rodeio", "romaria": "romaria",
        "corrida": "corrida", "maratona": "corrida",
        "congresso": "congresso", "campeonato": "campeonato",
        "torneio": "torneio", "exposicao": "exposicao",
        "cavalgada": "cavalgada",
        "agropecuaria": "agropecuaria", "agropecuária": "agropecuaria",
        "leilao": "agropecuaria", "leilão": "agropecuaria",
        "formatura": "formatura",
        "quermesse": "festa religiosa", "jubileu": "festa religiosa",
        "novena": "festa religiosa", "trezena": "festa religiosa",
        "missa campal": "festa religiosa",
        "conferencia": "conferencia", "conferência": "conferencia",
        "simposio": "conferencia", "simpósio": "conferencia",
        "inauguracao": "inauguracao", "inaugura": "inauguracao",
        "encontro": "encontro cultural",
    }
    for kw, tipo in mapa.items():
        if kw in tn and tipo not in tipos:
            tipos.append(tipo)
    return tipos


def analisar_regras(item, themes=None, rules=None):
    regras = rules or load_commercial_rules()
    themes = themes or load_themes()

    titulo = item.get("titulo", "")
    texto = item.get("texto", "")
    alvo = (titulo + " " + texto)
    tn = _norm(alvo)

    analise = _default_analise()

    fallback = (regras.get("fallback_scores") or {})
    analise["editorial_score"] = int(fallback.get("editorial_score", 5))
    analise["commercial_score"] = int(fallback.get("commercial_score", 0))
    analise["instagram_score"] = int(fallback.get("instagram_score", 5))

    triggers = regras.get("triggers") or []
    tech_keywords = regras.get("tech_keywords") or []
    streaming_keywords = regras.get("streaming_keywords") or []

    # ---- triggers comerciais ----
    matched = []
    for trig in triggers:
        if any(_norm(k) in tn for k in trig.get("keywords", [])):
            matched.append(trig)

    # ---- flags de assunto ----
    analise["event_related"] = any(
        t["name"] in ("recorde_publico", "grande_evento", "evento_municipal",
                      "evento_empresarial", "corrida", "evento_agropecuario",
                      "formatura", "evento_religioso", "conferencia",
                      "inauguracao") for t in matched)
    analise["sports_related"] = any(t["name"] == "campeonato" for t in matched)
    analise["streaming_related"] = any(t["name"] == "streaming" for t in matched) or \
        any(_norm(k) in tn for k in streaming_keywords)
    analise["technology_related"] = any(_norm(k) in tn for k in tech_keywords)
    analise["sponsorship_related"] = any(t["name"] == "patrocinio" for t in matched)
    analise["event_related"] = analise["event_related"] or bool(_detectar_tipos(tn))

    analise["event_type"] = _detectar_tipos(tn)

    # ---- tipo de evento tambem via trigger de campeonato ----
    if analise["sports_related"] and "campeonato" not in analise["event_type"]:
        analise["event_type"].append("campeonato")

    # ---- score comercial ----
    if matched:
        melhor = max(matched, key=lambda t: int(t.get("commercial_score", 0)))
        analise["commercial_score"] = int(melhor.get("commercial_score", 0))
    elif analise["technology_related"]:
        analise["commercial_score"] = 4

    # ---- score editorial ----
    editorial = analise["editorial_score"]
    if analise["event_related"] or analise["sports_related"]:
        editorial += 1
    if any(k in tn for k in ["prefeitura", "camara", "governo", "secretaria"]):
        editorial += 1
    if analise["regional"] or _eh_regional(alvo, themes, regras):
        editorial += 1
    if re.search(r"(mil\s*(pessoas|visitantes|espectadores)|milh[oõ]es|recorde)",
                 tn):
        editorial += 1
    analise["editorial_score"] = max(0, min(10, editorial))

    # ---- score instagram ----
    insta = analise["instagram_score"]
    if analise["event_related"] or analise["sports_related"]:
        insta += 1
    if analise["sports_related"]:
        insta += 1
    if analise["regional"] or _eh_regional(alvo, themes, regras):
        insta += 1
    if re.search(r"(mil\s*(pessoas|visitantes|espectadores)|milh[oõ]es|recorde)",
                 tn):
        insta += 1
    if analise["streaming_related"]:
        insta += 1
    if analise["technology_related"]:
        insta += 1
    analise["instagram_score"] = max(0, min(10, insta))

    # ---- angulo comercial + servicos ----
    if matched:
        melhor = max(matched, key=lambda t: int(t.get("commercial_score", 0)))
        analise["commercial_angle"] = melhor.get("angle", "")
        servicos = []
        for t in matched:
            for s in t.get("services", []):
                if s not in servicos:
                    servicos.append(s)
        analise["suggested_service"] = servicos

    # ---- target customer ----
    alvo_norm = tn
    alvo_original = alvo
    for mapeamento in (regras.get("target_mapping") or []):
        if any(_norm(k) in alvo_norm for k in mapeamento.get("keywords", [])):
            target = mapeamento["target"]
            if target not in analise["target_customer"]:
                analise["target_customer"].append(target)
    if analise["event_related"] and "organizador de eventos" not in analise["target_customer"]:
        analise["target_customer"].append("organizador de eventos")
    if analise["regional"] and "evento regional" not in analise["target_customer"]:
        analise["target_customer"].append("prefeituras e orgãos públicos da região")

    # ---- categoria ----
    if analise["sports_related"]:
        analise["category"] = "esportes"
    elif analise["event_related"]:
        analise["category"] = "eventos"
    elif analise["streaming_related"]:
        analise["category"] = "streaming"
    elif matched and matched[0]["name"] in CATEGORY_POR_TRIGGER:
        analise["category"] = CATEGORY_POR_TRIGGER[matched[0]["name"]]
    else:
        tema = item.get("tema", "")
        analise["category"] = CATEGORY_POR_TEMA.get(tema, "geral")

    # ---- motivo ----
    reasons = (regras.get("reasons") or {})
    analise["reason"] = reasons.get(analise["commercial_angle"]) or (
        "Notícia com potencial de gerar interesse pela programação regional."
        if analise["event_related"] else "")

    # ---- geracao de conteudo ----
    analise["generate_reel"] = analise["instagram_score"] >= 8 or analise["commercial_score"] >= 8
    analise["generate_cta"] = analise["commercial_score"] >= 7

    analise["regional"] = _eh_regional(alvo, themes, regras) or analise["regional"]
    analise["publish"] = True
    return analise


# ============================================================
# PONTO DE ENTRADA PRINCIPAL
# ============================================================

def analisar_noticia(item, api_key="", themes=None, rules=None):
    """Analisa uma notícia coletada e retorna a análise estruturada.

    Nunca levanta exceção: se IA e regras falharem, devolve valores padrão.
    """
    titulo = item.get("titulo", "")
    texto = item.get("texto", "")
    print(f"[ANALYZER] Analisando noticia: {(titulo or '?')[:60]}")

    analise = None
    if api_key:
        try:
            analise = _analisar_ia(titulo, texto, api_key)
            print(f"[ANALYZER] Análise via IA ok")
        except Exception as e:
            print(f"[ANALYZER] IA falhou, usando regras locais: {e}")

    if not analise:
        try:
            analise = analisar_regras(item, themes, rules)
            print(f"[ANALYZER] Análise por regras locais ok")
        except Exception as e:
            print(f"[ANALYZER] Regras falharam, usando padrão: {e}")
            analise = _default_analise()

    analise = normalizar_analise(analise)

    # Reforço regional (baseado em temas/cidades monitoradas)
    alvo = (titulo or "") + " " + (texto or "")
    analise["regional"] = _eh_regional(alvo, themes, rules)

    _log_analise(analise)
    return analise


def _log_analise(analise):
    print(f"[ANALYZER] Editorial score: {analise['editorial_score']}")
    print(f"[ANALYZER] Commercial score: {analise['commercial_score']}")
    print(f"[ANALYZER] Instagram score: {analise['instagram_score']}")
    if analise.get("commercial_angle"):
        print(f"[ANALYZER] Ângulo comercial: {analise['commercial_angle']}")
    if analise.get("suggested_service"):
        print(f"[ANALYZER] Serviço sugerido: {', '.join(analise['suggested_service'])}")
    print(f"[ANALYZER] Categoria: {analise.get('category', 'geral')}")
    print(f"[ANALYZER] Evento relacionado: {analise['event_related']}")
    print(f"[ANALYZER] Região: {('SIM' if analise.get('regional') else 'NAO')}")


def intensidade_comercial(score):
    """Mapeia commercial_score para o nivel de redação do bloco comercial."""
    if score <= 4:
        return None
    if score <= 6:
        return "5_6"
    if score <= 8:
        return "7_8"
    return "9_10"


# ============================================================
# CONTEÚDO SOCIAL ESTRUTURADO (Reel / Stories / Carousel)
# ============================================================

def _escolher_cta(analise, social_rules):
    angle = analise.get("commercial_angle") or "default"
    ctas = (social_rules.get("ctas") or {})
    lista = ctas.get(angle) or ctas.get("default") or []
    if not lista:
        return ""
    import random
    return random.choice(lista)


def _gerar_social_ia(item, analise, resumo, api_key):
    import summarize
    social_rules = load_social_rules()
    titulo = item.get("titulo", "")
    prompt = (
        "Você é o editor de redes sociais do 'Portal Ao Vivo'. Crie conteúdo "
        "estruturado para Instagram a partir da notícia abaixo.\n\n"
        "Responda APENAS com JSON válido (sem markdown):\n"
        "{\n"
        '  "reel": {"hook": "", "script": "", "caption": "", "cta": ""},\n'
        '  "stories": ["", "", ""],\n'
        '  "carousel": {"title": "", "slides": [""]}\n'
        "}\n\n"
        "O hook deve prender a atenção (pergunta ou dado surpreendente). "
        "O script deve ter desenvolvimento e conclusão naturais. "
        "A caption deve ser legenda pronta com hashtags. "
        "O cta deve ser escolhido conforme o ângulo comercial "
        f"'{analise.get('commercial_angle') or 'general'}' e o público-alvo "
        f"{json.dumps(analise.get('target_customer') or [], ensure_ascii=False)}.\n"
        "NUNCA transforme em anúncio agressivo: o conteúdo precisa ser útil "
        "mesmo para quem nunca contratará o portal.\n\n"
        "TÍTULO: {titulo}\nMATÉRIA:\n{resumo}\n"
        "CATEGORIA: {categoria} | INSTAGRAM SCORE: {insta} | "
        "COMMERCIAL SCORE: {comerc}"
    ).format(
        titulo=titulo[:200],
        resumo=(resumo or "")[:2500],
        categoria=analise.get("category", ""),
        insta=analise.get("instagram_score", 0),
        comerc=analise.get("commercial_score", 0),
    )
    resposta = summarize._gerar(prompt, api_key, temperature=0.7, max_tokens=1000)
    dados = _extrair_json(resposta)
    if not dados or "reel" not in dados:
        raise ValueError("IA não retornou conteúdo social válido")
    return dados


def _gerar_social_template(item, analise, resumo):
    social_rules = load_social_rules()
    commercial_rules = load_commercial_rules()
    angle = analise.get("commercial_angle") or "alcance"
    nivel = intensidade_comercial(analise.get("commercial_score", 0)) or "7_8"
    paragrafos = ((commercial_rules.get("commercial_paragraphs") or {})
                  .get(angle, {}))
    desenvolvimento = (paragrafos.get(nivel) or
                       paragrafos.get("9_10") or
                       "Eventos regionais de grande porte mostram que a "
                       "experiencia presencial pode ser ampliada para quem "
                       "esta em casa ou em outra cidade.")

    titulo = (item.get("titulo") or "")[:80]
    publico = item.get("_publico_esperado")
    if publico:
        hook = f"Esse evento reuniu {publico} pessoas. Mas quantas ficaram de fora?"
    elif analise.get("event_related"):
        hook = "O crescimento dos eventos regionais está mudando a forma de viver a cultura."
    else:
        hook = "Todo mundo está comentando. E quem ainda não viu?"

    script = (f"{hook} "
              f"{desenvolvimento} "
              f"Hoje, o evento não precisa terminar no local: a transmissão ao "
              f"vivo leva a experiência para quem está em casa.")
    cta = _escolher_cta(analise, social_rules)
    hashtags = social_rules.get("default_hashtags", "#PortalAoVivo")
    primeiro_par = ""
    if resumo:
        primeiro_par = resumo.strip().split("\n")[0].strip()[:300]
    caption = f"{titulo}\n\n{primeiro_par}\n\n{cta}\n\n{hashtags}"

    stories = [
        f"{titulo}",
        f"{desenvolvimento}",
        f"{cta}",
    ]

    return {
        "reel": {
            "hook": hook,
            "script": script,
            "caption": caption,
            "cta": cta,
        },
        "stories": [s for s in stories if s],
        "carousel": {
            "title": titulo,
            "slides": [primeiro_par, desenvolvimento, cta],
        },
    }


def gerar_conteudo_social(item, analise, resumo, api_key=""):
    """Gera conteúdo social estruturado (reel/stories/carousel).

    Só deve ser chamado quando generate_reel/conditional for True.
    Nunca quebra o pipeline.
    """
    analise = analise or {}
    print("[SOCIAL-GEN] Gerando conteúdo social especial...")
    try:
        if api_key:
            return _gerar_social_ia(item, analise, resumo, api_key)
    except Exception as e:
        print(f"[SOCIAL-GEN] IA de conteúdo social falhou: {e}")
    return _gerar_social_template(item, analise, resumo)


if __name__ == "__main__":
    exemplo = {
        "titulo": "Prefeitura anuncia grande festival para outubro com expectativa de 30 mil pessoas",
        "texto": "A Prefeitura de Patos de Minas anunciou um grande festival para outubro no parque de "
                 "exposições. A expectativa é reunir 30 mil pessoas durante os quatro dias, com shows, "
                 "praça de alimentação e programação cultural. A organização ainda busca patrocinadores.",
        "tema": "Local e Cidades",
    }
    analise_out = analisar_noticia(exemplo, api_key=os.environ.get("GEMINI_API_KEY", ""))
    print(json.dumps(analise_out, ensure_ascii=False, indent=2))