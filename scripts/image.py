import json
import os
import re
import urllib.parse

import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# estilo visual padrao para as imagens
STYLE_SUFIXO = (
    ", estilo fotojornalismo, iluminacao natural, alta qualidade, "
    "tons de preto, vermelho e branco, composicao dramatica jornalistica"
)

# estilo street art / graffiti escolhido pelo dono do portal
STYLE_GRAFFITI = (
    ", mural de arte urbana graffiti vibrante, spray paint, cores fortes, "
    "contraste preto vermelho e branco, arte de rua moderna, alta qualidade"
)

PROMPT_BASE = (
    "Crie uma imagem jornalistica realista que ilustre esta noticia de forma "
    "generica e sem logos, marcas ou rostos identificaveis: {resumo}"
)

PROMPT_GRAFFITI = (
    "Reinterprete esta imagem como um mural de street art graffiti, "
    "vibrante, com spray paint e contornos marcantes, mantendo o tema da "
    "noticia mas sem textos legiveis: {resumo}"
)

MODELOS_GRAFFITI = ["klein", "kontext", "seedream"]
MODELO_PADRAO = "flux"


def slugify(texto):
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9\s]", "", texto)
    texto = re.sub(r"\s+", "-", texto.strip())
    return texto[:60].strip("-")


def gerar_prompt_imagem(resumo, titulo, tema):
    base = PROMPT_BASE.format(resumo=resumo[:500])
    return (base + STYLE_SUFIXO).strip()


def gerar_prompt_graffiti(resumo, titulo, tema):
    base = PROMPT_GRAFFITI.format(resumo=resumo[:400])
    return (base + STYLE_GRAFFITI).strip()


def baixar_imagem(prompt, destino, largura=900, altura=500, imagem_orig=None):
    """Gera e baixa a imagem via Pollinations.ai (gratuito, sem chave).
    Se houver imagem_orig, tenta img2img estilo graffiti usando essa foto
    como base. Fallback: flux texto->imagem com o prompt padrao."""
    tentativas = []

    if imagem_orig:
        # 1) img2img graffiti com a foto original
        prompt_graf = gerar_prompt_graffiti("", "", "")
        tentativas.append((prompt_graf, imagem_orig, MODELOS_GRAFFITI))

    # 2) texto->imagem padrao (flux)
    tentativas.append((prompt, None, [MODELO_PADRAO]))

    for prompt_usado, img_ref, modelos in tentativas:
        for modelo in modelos:
            url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt_usado)
            url += f"?width={largura}&height={altura}&nologo=true&model={modelo}"
            if img_ref:
                url += "&image=" + urllib.parse.quote(img_ref, safe="")
            try:
                r = requests.get(url, timeout=120)
                r.raise_for_status()
                if r.headers.get("content-type", "").startswith("image"):
                    os.makedirs(os.path.dirname(destino), exist_ok=True)
                    with open(destino, "wb") as f:
                        f.write(r.content)
                    print(f"  [IMAGEM] OK via {modelo}"
                          + (" (img2img graffiti)" if img_ref else ""))
                    return destino
            except Exception as e:
                print(f"  [ERRO] imagem Pollinations ({modelo}): {e}")
                continue
    return None


if __name__ == "__main__":
    prompt = gerar_prompt_imagem(
        "Prefeitura anuncia obras de pavimentacao no bairro Novo Horizonte",
        "Obras em Patos de Minas",
        "Local e Cidades",
    )
    print("Prompt:", prompt)
    out = baixar_imagem(prompt, os.path.join(BASE_DIR, "assets", "images", "teste.jpg"))
    print("Imagem gerada em:", out)
