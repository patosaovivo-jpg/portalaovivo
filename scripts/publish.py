import json
import os
import re
from datetime import datetime, timezone, timedelta

BRT = timezone(timedelta(hours=-3))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTS_DIR = os.path.join(BASE_DIR, "_posts")
PUBLISHED_FILE = os.path.join(BASE_DIR, "data", "published.json")


def slugify(texto):
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9\s]", "", texto)
    texto = re.sub(r"\s+", "-", texto.strip())
    return texto[:60].strip("-")


def agora_brt():
    return datetime.now(BRT)


def gerar_markdown(item, resumo, imagem_rel):
    agora = agora_brt()
    data_str = agora.strftime("%Y-%m-%d")
    slug = slugify(item["titulo"]) or slugify(item["link"])
    arquivo = os.path.join(POSTS_DIR, f"{data_str}-{slug}.md")

    if os.path.exists(arquivo):
        slug = slug + "-" + agora.strftime("%H%M")
        arquivo = os.path.join(POSTS_DIR, f"{data_str}-{slug}.md")

    titulo = item.get("titulo") or resumo.split("\n")[0][:100]
    primeiro_par = resumo.strip().split("\n")[0].strip()
    resumo_curto = primeiro_par[:180] + ("..." if len(primeiro_par) > 180 else "")
    frontmatter = (
        "---\n"
        f'title: "{esc(titulo)}"\n'
        f'date: {agora.strftime("%Y-%m-%d %H:%M:%S -0300")}\n'
        f'image: {imagem_rel}\n'
        f'tema: {item.get("tema", "Geral")}\n'
        f'fonte: "{esc(item["fonte"])}"\n'
        f'fonte_link: "{esc(item["link"])}"\n'
        f'resumo: "{esc(resumo_curto)}"\n'
        "---\n\n"
    )

    body = resumo + "\n\n"
    body += f'*Leia a matéria completa na fonte original:* [{esc(item["fonte"])}]({esc(item["link"])})\n'
    body += "\n---\n"
    body += "\n*Conteúdo resumido automaticamente pelo Portal Ao Vivo.*\n"

    conteudo = frontmatter + body
    with open(arquivo, "w", encoding="utf-8") as f:
        f.write(conteudo)
    return arquivo


def esc(t):
    return t.replace('"', '\\"').replace("\n", " ")


def registrar_publicado(item, arquivo):
    lista = []
    if os.path.exists(PUBLISHED_FILE):
        with open(PUBLISHED_FILE, "r", encoding="utf-8") as f:
            lista = json.load(f)
    lista.append({
        "link": item["link"],
        "titulo": item.get("titulo", ""),
        "arquivo": os.path.basename(arquivo),
        "publicado": agora_brt().isoformat(),
    })
    lista = lista[-2000:]
    os.makedirs(os.path.dirname(PUBLISHED_FILE), exist_ok=True)
    with open(PUBLISHED_FILE, "w", encoding="utf-8") as f:
        json.dump(lista, f, ensure_ascii=False, indent=2)


def publicar_materia(item, resumo, imagem_rel):
    arquivo = gerar_markdown(item, resumo, imagem_rel)
    registrar_publicado(item, arquivo)
    print(f"[PUBLICADO] {arquivo}")
    return arquivo
