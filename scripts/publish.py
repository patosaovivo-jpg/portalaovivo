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


def gerar_markdown(item, resumo, imagem_rel, sem_fonte=False, analise=None):
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
    )

    # ====== Campos da camada editorial + comercial (compatíveis com Jekyll) ======
    frontmatter += _frontmatter_analise(analise, item)

    frontmatter += "---\n\n"

    body = resumo + "\n\n"
    if not sem_fonte:
        body += f'*Leia a matéria completa na fonte original:* [{esc(item["fonte"])}]({esc(item["link"])})\n'
    body += "\n---\n"
    body += "\n*Conteúdo produzido pelo Portal Ao Vivo.*\n"

    conteudo = frontmatter + body
    with open(arquivo, "w", encoding="utf-8") as f:
        f.write(conteudo)
    return arquivo


def _fmt_lista(itens):
    """Formata lista como YAML (array). Retorna string vazia se vazia."""
    itens = [str(x).strip() for x in (itens or []) if str(x).strip()]
    if not itens:
        return ""
    return "\n" + "\n".join(f'  - "{esc(x)}"' for x in itens)


def _frontmatter_analise(analise, item):
    """Adiciona os novos campos de inteligência ao frontmatter sem quebrar os atuais."""
    if not analise:
        return ""
    a = analise
    linhas = []
    linhas.append(f'categoria: "{esc(a.get("category", "geral"))}"')

    for campo in ("editorial_score", "commercial_score", "instagram_score"):
        linhas.append(f"{campo}: {int(a.get(campo, 0) or 0)}")

    for campo in ("event_related", "sports_related", "streaming_related",
                  "technology_related", "sponsorship_related", "generate_reel",
                  "generate_cta"):
        linhas.append(f"{campo}: {'true' if a.get(campo) else 'false'}")

    for campo in ("event_name", "event_city", "event_date", "organizer"):
        valor = a.get(campo) or item.get(campo)
        if valor:
            linhas.append(f"{campo}: \"{esc(str(valor)[:120])}\"")

    tipo_raw = a.get("event_type") or item.get("event_type")
    tipos = tipo_raw if isinstance(tipo_raw, list) else ([tipo_raw] if tipo_raw else [])
    if tipos:
        primeiro = str(tipos[0]).strip()
        if primeiro:
            linhas.append(f'event_type: "{esc(primeiro)}"')
        linhas.append("event_types:" + _fmt_lista(tipos))
    if a.get("commercial_angle"):
        linhas.append(f'commercial_angle: "{esc(a["commercial_angle"])}"')
    if a.get("target_customer"):
        linhas.append("target_customer:" + _fmt_lista(a.get("target_customer")))
    if a.get("suggested_service"):
        linhas.append("suggested_service:" + _fmt_lista(a.get("suggested_service")))
    if a.get("reason"):
        linhas.append(f'reason: "{esc(a["reason"][:200])}"')

    conteudo_social = item.get("conteudo_social") or a.get("conteudo_social")
    if conteudo_social:
        reel = conteudo_social.get("reel") or {}
        for campo in ("hook", "script", "caption", "cta"):
            valor = reel.get(campo)
            if valor:
                linhas.append(f"instagram_{campo}: \"{esc(str(valor)[:300])}\"")

    return "\n".join(linhas) + "\n"


def esc(t):
    return t.replace('"', '\\"').replace("\n", " ") if t else ""


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


def publicar_materia(item, resumo, imagem_rel, sem_fonte=False, analise=None):
    arquivo = gerar_markdown(item, resumo, imagem_rel, sem_fonte, analise=analise)
    registrar_publicado(item, arquivo)
    print(f"[PUBLICADO] {arquivo}")
    return arquivo
