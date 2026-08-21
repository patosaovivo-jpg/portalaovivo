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
    "VocÃª Ã© um editor-chefe de um portal de notÃ­cias regional chamado 'Portal Ao Vivo'. "
    "Resuma o texto a seguir em um texto jornalÃ­stico de 3 a 4 parÃ¡grafos curtos, "
    "mantendo TODOS os fatos e o contexto importantes (quem, o quÃª, onde, quando, como). "
    "Escreva em portuguÃªs do Brasil, com linguagem clara e direta. "
    "NÃƒO invente informaÃ§Ãµes que nÃ£o estejam no texto original. "
    "NÃƒO comece com 'Em resumo' nem com o nome do portal. "
    "Termine o texto sem assinaturas. Responda APENAS com o texto resumido.\n\n"
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
        "Crie um tÃ­tulo jornalÃ­stico curto e chamativo (mÃ¡ximo 10 palavras) para a "
        "notÃ­cia abaixo. Responda APENAS com o tÃ­tulo, sem aspas.\n\n" + texto[:4000]
    )
    titulo = _gerar(prompt, api_key, temperature=0.7, max_tokens=60)
    return titulo.strip().strip('"').strip()


if __name__ == "__main__":
    api = os.environ.get("GEMINI_API_KEY", "")
    if not api:
        print("GEMINI_API_KEY nÃ£o definida")
    else:
        print(resumir_texto("Prefeitura de Patos de Minas anuncia obras de pavimentaÃ§Ã£o no bairro Novo Horizonte. As obras comeÃ§am na prÃ³xima semana e vÃ£o durar 60 dias.", api))