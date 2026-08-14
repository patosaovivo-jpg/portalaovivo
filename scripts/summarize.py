import os

# Modelos em ordem de preferencia. Alguns sao descontinuados/indisponiveis
# para contas novas, entao tentamos em sequencia ate um funcionar.
MODELOS = [
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
    "gemini-2.5-flash",
]

PROMPT = (
    "Você é um editor-chefe de um portal de notícias regional chamado 'Portal Ao Vivo'. "
    "Resuma o texto a seguir em um texto jornalístico de 3 a 4 parágrafos curtos, "
    "mantendo TODOS os fatos e o contexto importantes (quem, o quê, onde, quando, como). "
    "Escreva em português do Brasil, com linguagem clara e direta. "
    "NÃO invente informações que não estejam no texto original. "
    "NÃO comece com 'Em resumo' nem com o nome do portal. "
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
    return _gerar(
        PROMPT.format(texto=texto[:15000]),
        api_key,
        temperature=0.4,
        max_tokens=800,
    )


def gerar_titulo(texto, api_key):
    prompt = (
        "Crie um título jornalístico curto e chamativo (máximo 10 palavras) para a "
        "notícia abaixo. Responda APENAS com o título, sem aspas.\n\n" + texto[:4000]
    )
    titulo = _gerar(prompt, api_key, temperature=0.7, max_tokens=60)
    return titulo.strip().strip('"').strip()


if __name__ == "__main__":
    api = os.environ.get("GEMINI_API_KEY", "")
    if not api:
        print("GEMINI_API_KEY não definida")
    else:
        print(resumir_texto("Prefeitura de Patos de Minas anuncia obras de pavimentação no bairro Novo Horizonte. As obras começam na próxima semana e vão durar 60 dias.", api))