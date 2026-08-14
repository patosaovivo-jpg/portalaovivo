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

PROMPT_BASE = (
    "Crie uma imagem jornalistica realista que ilustre esta noticia de forma "
    "generica e sem logos, marcas ou rostos identificaveis: {resumo}"
)


def slugify(texto):
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9\s]", "", texto)
    texto = re.sub(r"\s+", "-", texto.strip())
    return texto[:60].strip("-")


def gerar_prompt_imagem(resumo, titulo, tema):
    base = PROMPT_BASE.format(resumo=resumo[:500])
    return (base + STYLE_SUFIXO).strip()


def baixar_imagem(prompt, destino, largura=900, altura=500):
    """Gera e baixa a imagem via Pollinations.ai (gratuito, sem chave).
    Tenta o prompt completo; se falhar, tenta versao simplificada com o titulo."""
    tentativas = [
        prompt,
        gerar_prompt_imagem("", "Ilustracao jornalistica", ""),
    ]
    for tentativa in tentativas:
        url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(tentativa)
        url += f"?width={largura}&height={altura}&nologo=true&model=flux"
        try:
            r = requests.get(url, timeout=90)
            r.raise_for_status()
            if r.headers.get("content-type", "").startswith("image"):
                os.makedirs(os.path.dirname(destino), exist_ok=True)
                with open(destino, "wb") as f:
                    f.write(r.content)
                return destino
        except Exception as e:
            print(f"  [ERRO] imagem Pollinations: {e}")
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