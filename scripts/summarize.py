import json
import os

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


def resumir_texto(texto, api_key, model="gemini-2.0-flash"):
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model_inst = genai.GenerativeModel(model)
    resp = model_inst.generate_content(
        PROMPT.format(texto=texto[:15000]),
        generation_config=genai.types.GenerationConfig(
            temperature=0.4,
            max_output_tokens=800,
        ),
    )
    return resp.text.strip()


def gerar_titulo(texto, api_key, model="gemini-2.0-flash"):
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model_inst = genai.GenerativeModel(model)
    resp = model_inst.generate_content(
        "Crie um título jornalístico curto e chamativo (máximo 10 palavras) para a "
        "notícia abaixo. Responda APENAS com o título, sem aspas.\n\n" + texto[:4000],
        generation_config=genai.types.GenerationConfig(
            temperature=0.7,
            max_output_tokens=60,
        ),
    )
    return resp.text.strip().strip('"').strip()


if __name__ == "__main__":
    api = os.environ.get("GEMINI_API_KEY", "")
    if not api:
        print("GEMINI_API_KEY não definida")
    else:
        print(resumir_texto("Prefeitura de Patos de Minas anuncia obras de pavimentação no bairro Novo Horizonte. As obras começam na próxima semana e vão durar 60 dias.", api))