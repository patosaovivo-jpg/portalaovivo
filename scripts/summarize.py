import json
import os

# Modelos em ordem de preferencia. Alguns sao descontinuados/indisponiveis
# para contas novas, entao tentamos em sequencia ate um funcionar.
MODELOS = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
]

PROMPT = (
    "Você é um editor-chefe de um portal de notícias regional chamado 'Portal Ao Vivo'. "
    "Resuma o texto a seguir em um texto jornalístico de 3 a 4 parágrafos curtos, "
    "mantendo TODOS os fatos e o contexto importantes (quem, o quê, onde, quando, como). "
    "Escreva em português do Brasil, com linguagem clara e direta. "
    "NÃO invente informações que não estejam no texto original. "
    "NÃO comece com 'Em resumo' nem com o nome do portal. "
    "Termine o texto sem assinaturas. Responda APENAS com o texto resumido.\n\n"
    "Se o texto contiver formatação quebrada, caracteres estranhos ou parecer extraído de PDF, "
    "ignore os erros de formatação e extraia apenas as informações relevantes.\n\n"
    "TEXTO ORIGINAL:\n{texto}"
)


def _gerar(prompt, api_key, temperature, max_tokens):
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    erros = []
    for model in MODELOS:
        try:
            model_inst = genai.GenerativeModel(model)
            resp = model_inst.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
            )
            texto = resp.text.strip()
            if texto:
                return texto
            erros.append(f"{model}: resposta vazia")
        except Exception as e:
            erros.append(f"{model}: {e}")
    raise RuntimeError("Nenhum modelo Gemini respondeu. Erros: " + " | ".join(erros))


def resumir_texto(texto, api_key):
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY nao definida")
    return _gerar(
        PROMPT.format(texto=texto[:15000]),
        api_key,
        temperature=0.4,
        max_tokens=800,
    )


PROMPT_EDITAL = (
    "Você é um jornalista especializado em cobertura de editais e diários oficiais "
    "do portal 'Portal Ao Vivo'. O texto abaixo foi extraído de um edital ou diário oficial. "
    "Transforme-o em uma matéria jornalística clara e completa para o público leigo, "
    "explicando CADA tópico/assunto importante do edital em parágrafos separados. "
    "Para cada convocação, licitação, credenciamento, nomeação, resultado, ou homologação, "
    "explique: O QUE é, QUEM está envolvido (órgão, comissão, candidato, empresa), QUANDO "
    "(datas, prazos, horários de entrega/sessão), ONDE (endereço, local, site, e-mail). "
    "Use linguagem simples, em português do Brasil. "
    "Organize com títulos curtos ou negrito (*Assunto:*) antes de cada explicação para facilitar a leitura. "
    "Mantenha todos os números de edital, processos, prazos e valores. "
    "NÃO invente informações. NÃO repita o texto cru. "
    "Escreva em primeira pessoa do plural (nós) ou impessoal. "
    "Termine sem assinaturas. Responda APENAS com a matéria.\n\n"
    "TEXTO DO EDITAL:\n{texto}"
)


def resumir_edital(texto, api_key):
    """Resumo especializado que explica cada topico de um edital."""
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY nao definida")
    return _gerar(
        PROMPT_EDITAL.format(texto=texto[:15000]),
        api_key,
        temperature=0.3,
        max_tokens=1500,
    )


def resumir_fallback(texto):
    """Gera resumo sem IA pegando os primeiros paragrafos do texto original."""
    paragrafos = [p.strip() for p in texto.split("\n") if len(p.strip()) > 30]
    if not paragrafos:
        return None
    resumo = "\n\n".join(paragrafos[:4])
    if len(resumo) < 100:
        return None
    if len(resumo) > 1000:
        resumo = resumo[:997] + "..."
    return resumo


def gerar_titulo(texto, api_key):
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY nao definida")
    prompt = (
        "Crie um título jornalístico curto e chamativo (máximo 10 palavras) para a "
        "notícia abaixo. Responda APENAS com o título, sem aspas.\n\n" + texto[:4000]
    )
    titulo = _gerar(prompt, api_key, temperature=0.7, max_tokens=60)
    return titulo.strip().strip('"').strip()


def gerar_titulo_edital(texto, api_key):
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY nao definida")
    prompt = (
        "Crie um título jornalístico curto (máximo 10 palavras) para a matéria sobre este "
        "edital. Inclua o número e o tipo do edital (ex: 'Edital de Convocação nº 66 - "
        "Servente Escolar') e o órgão/empresa envolvido se houver. Não use aspas. "
        "Responda APENAS com o título.\n\n" + texto[:4000]
    )
    titulo = _gerar(prompt, api_key, temperature=0.5, max_tokens=60)
    return titulo.strip().strip('"').strip()


# ============================================================
# CAMADA COMERCIAL: MATERIA + BLOCO EDITORIAL/COMERCIAL NATURAL
# ============================================================

CONTEXTO_COMERCIAL_INSTRUCAO = {
    "5_6": (
        "Inclua no final UM parágrafo curto e natural com contexto editorial "
        "sobre a relevância/força desse tipo de evento para a região. "
        "Não mencione o portal nem serviços. Apenas conexão editorial."
    ),
    "7_8": (
        "Inclua no final UM parágrafo curto e natural comentando a relevância "
        "do evento e MENCIONANDO de forma discreta que a transmissão ao vivo "
        "/ cobertura audiovisual pode ampliar o alcance de quem não pode estar "
        "presente. Sem tom de anúncio, sem CTA direto."
    ),
    "9_10": (
        "Inclua no final UM parágrafo curto e natural sobre o potencial do "
        "evento de alcançar um público além do presencial, citando de forma"
        " editorial a transmissão ao vivo / cobertura audiovisual como "
        "instrumento de ampliar esse alcance. Pode haver um leve convite "
        "discreto, mas a matéria continua sendo NOTÍCIA, não anúncio."
    ),
}


def _carregar_commercial_rules():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "config", "commercial_rules.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def nivel_comercial(score):
    """0-4: nada | 5-6: conexão editorial | 7-8: menção discreta | 9-10: CTA sutil."""
    if score <= 4:
        return None
    if score <= 6:
        return "5_6"
    if score <= 8:
        return "7_8"
    return "9_10"


def resumir_texto_com_analise(texto, analise, api_key, eh_edital=False):
    """Gera a matéria considerando a análise comercial.

    Mantém o comportamento atual para scores baixos e adiciona bloco
    comercial natural apenas quando o nível permitir. Nunca quebra:
    se a IA falhar, usa fallback local (com bloco comercial simples).
    """
    analise = analise or {}
    if eh_edital:
        if api_key:
            return resumir_edital(texto, api_key)
        return resumir_fallback(texto)

    score = int(analise.get("commercial_score") or 0)
    nivel = nivel_comercial(score)
    angle = (analise.get("commercial_angle") or "").strip()

    if not nivel:
        # Sem camada comercial: comportamento 100% atual
        if api_key:
            return resumir_texto(texto, api_key)
        return resumir_fallback(texto)

    if api_key:
        try:
            return _resumir_com_comercial(texto, api_key, angle, nivel)
        except Exception as e:
            print(f"[IA] Falha no resumo com contexto comercial, fallback: {e}")

    return _resumir_fallback_comercial(texto, angle, nivel)


def _resumir_com_comercial(texto, api_key, angle, nivel):
    instrucao = CONTEXTO_COMERCIAL_INSTRUCAO.get(nivel, "")
    prompt = (
        PROMPT + "\n\nINSTRUÇÃO ADICIONAL:\n" + instrucao +
        (f"\nÂngulo comercial da notícia: {angle}" if angle else "")
    )
    return _gerar(prompt.format(texto=texto[:15000]), api_key,
                  temperature=0.4, max_tokens=900)


def _resumir_fallback_comercial(texto, angle, nivel):
    base = resumir_fallback(texto)
    if not base:
        return None
    regras = _carregar_commercial_rules()
    paragrafos = ((regras.get("commercial_paragraphs") or {})
                  .get(angle, {}))
    frase = (paragrafos.get(nivel) or
             paragrafos.get("9_10") or
             (("O crescimento desse tipo de evento mostra a força das "
               "programações regionais e o interesse do público em acompanhar "
               "a agenda cultural de perto.") if angle else ""))
    if frase:
        base = base.rstrip() + "\n\n" + frase
    return base


if __name__ == "__main__":
    api = os.environ.get("GEMINI_API_KEY", "")
    if not api:
        print("GEMINI_API_KEY não definida")
    else:
        print(resumir_texto("Prefeitura de Patos de Minas anuncia obras de pavimentação no bairro Novo Horizonte. As obras começam na próxima semana e vão durar 60 dias.", api))