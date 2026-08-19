import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from urllib.parse import urljoin

import feedparser
import requests
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS_FILE = os.path.join(BASE_DIR, "fonts.json")
THEMES_FILE = os.path.join(BASE_DIR, "themes.json")
PUBLISHED_FILE = os.path.join(BASE_DIR, "data", "published.json")

TIMEOUT = 30
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 PortalAoVivo"
}
JANELA_HORAS = 48
ANO_ATUAL = datetime.now().year


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_published():
    if os.path.exists(PUBLISHED_FILE):
        with open(PUBLISHED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_published(items):
    os.makedirs(os.path.dirname(PUBLISHED_FILE), exist_ok=True)
    with open(PUBLISHED_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def normalize_url(url):
    url = url.strip()
    if url.startswith("//"):
        url = "https:" + url
    return url


def fetch(url, tentativas=3):
    for i in range(tentativas):
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code == 429:
                time.sleep(3 * (i + 1))
                continue
            r.raise_for_status()
            return r
        except Exception as e:
            if i < tentativas - 1:
                time.sleep(3)
            else:
                print(f"  [ERRO] falha ao buscar {url}: {e}")
    return None


def coletar_rss(fonte):
    items = []
    r = fetch(fonte["url"])
    if not r:
        return items
    feed = feedparser.parse(r.content)
    for entry in feed.entries[:20]:
        link = normalize_url(entry.get("link", ""))
        if not link:
            continue
        published = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            published = datetime(*entry.published_parsed[:6])
        items.append({
            "titulo": entry.get("title", ""),
            "link": link,
            "fonte": fonte["nome"],
            "publicado": published.isoformat() if published else None,
        })
    return items


def aplicar_padrao(fonte):
    return (fonte.get("link_pattern") or "noticia|news").replace("{ano}", str(ANO_ATUAL))


def coletar_sitemap(fonte):
    items = []
    pattern = aplicar_padrao(fonte)

    def parse(url):
        r = fetch(url)
        if not r:
            return
        soup = BeautifulSoup(r.content, "xml")
        # sitemap index -> seguir sub-sitemaps
        sub = soup.find_all("loc")
        is_index = soup.find("sitemapindex") is not None
        for loc in sub:
            link = normalize_url(loc.get_text("", strip=True))
            if not link:
                continue
            if is_index:
                parse(link)
                continue
            if not re.search(pattern, link, re.IGNORECASE):
                continue
            items.append({
                "titulo": "",
                "link": link,
                "fonte": fonte["nome"],
                "publicado": None,
            })

    parse(fonte["url"])
    return items[:20]


def coletar_scrape(fonte):
    items = []
    r = fetch(fonte["url"])
    if not r:
        return items
    soup = BeautifulSoup(r.content, "lxml")
    seen = set()
    pattern = aplicar_padrao(fonte)
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript")):
            continue
        if not re.search(pattern, href, re.IGNORECASE):
            continue
        link = normalize_url(urljoin(fonte["url"], href))
        if link in seen:
            continue
        seen.add(link)
        titulo = a.get_text(" ", strip=True)
        if len(titulo) < 15:
            titulo = link
        items.append({
            "titulo": titulo[:200],
            "link": link,
            "fonte": fonte["nome"],
            "publicado": None,
        })
    return items[:20]


def extrair_texto(link):
    r = fetch(link)
    if not r:
        return None, None
    imagem = extrair_imagem(r, link)
    try:
        import trafilatura

        text = trafilatura.extract(
            r.content,
            include_comments=False,
            include_tables=False,
            url=link,
            favor_recall=False,
        )
        if text and len(text.strip()) > 200:
            return text.strip(), imagem
    except Exception as e:
        print(f"  [ERRO] trafilatura em {link}: {e}")
    return None, imagem


def extrair_imagem(resp, link):
    """Extrai a imagem principal (og:image) de uma pagina."""
    try:
        soup = BeautifulSoup(resp.content, "html.parser")
        # 1) og:image
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            url = normalize_url(og["content"].strip())
            if url.startswith("http") and not url.endswith(".svg"):
                return url
        # 2) twitter:image
        tw = soup.find("meta", attrs={"name": "twitter:image"})
        if tw and tw.get("content"):
            url = normalize_url(tw["content"].strip())
            if url.startswith("http") and not url.endswith(".svg"):
                return url
        # 3) primeira imagem grande do artigo
        for img in soup.find_all("img", src=True):
            src = img["src"].strip()
            if not src or src.endswith(".svg"):
                continue
            # pular icons, logos, avatares
            if any(x in src.lower() for x in ["logo", "icon", "avatar", "favicon", "sprite"]):
                continue
            w = img.get("width", "")
            if w and w.isdigit() and int(w) < 200:
                continue
            return normalize_url(src)
    except Exception:
        pass
    return None


def classificar(titulo, texto, themes):
    full = (titulo + " " + texto).lower()
    for t, config in themes["temas"].items():
        for kw in config["palavras"]:
            if kw.lower() in full:
                return t
    return None


def e_regionais(link, themes):
    link_l = link.lower()
    return any(c.lower() in link_l for c in themes["cidades"])


def filtrar_excluir(titulo, themes):
    t = titulo.lower()
    return any(e.lower() in t for e in themes["excluir"])


def qualidade_minima(item, texto):
    """Rejeita materias de baixa qualidade (titulo curto, texto pequeno ou spam).
    Para o Instagram (legendas curtas), o minimo de texto e menor."""
    titulo = item.get("titulo", "")
    if len(titulo) < 20:
        return False
    if item.get("tipo") == "instagram":
        if len(texto.strip()) < 80:
            return False
    elif len(texto.strip()) < 300:
        return False
    return True


def e_recente(link):
    """Descarta links de anos anteriores ao atual (ex.: noticia/2025/)."""
    for ano in range(ANO_ATUAL - 5, ANO_ATUAL):
        if f"/{ano}/" in link:
            return False
    return True


def coleta_completa():
    fonts = load_json(FONTS_FILE)["fonts"]
    themes = load_json(THEMES_FILE)
    published = load_published()
    published_links = {p["link"] for p in published}

    candidatas = []

    for fonte in fonts:
        print(f"[COLETA] {fonte['nome']} ({fonte['tipo']})...")
        try:
            if fonte["tipo"] == "rss":
                itens = coletar_rss(fonte)
            elif fonte["tipo"] == "sitemap":
                itens = coletar_sitemap(fonte)
            else:
                itens = coletar_scrape(fonte)
        except Exception as e:
            print(f"  [ERRO] {fonte['nome']}: {e}")
            continue

        novas = 0
        for item in itens:
            link = item["link"]
            if link in published_links:
                continue
            if filtrar_excluir(item["titulo"], themes):
                continue
            if not e_recente(link):
                continue
            candidatas.append(item)
            novas += 1
        print(f"  -> {len(itens)} itens, {novas} novas candidatas")
        time.sleep(0.5)

    # ===== Instagram (busca por hashtag) =====
    try:
        import instagram as ig

        ig_items = ig.coletar_instagram()
        for item in ig_items:
            if item["link"] in published_links:
                continue
            if item.get("titulo") and filtrar_excluir(item["titulo"], themes):
                continue
            item["tipo"] = "instagram"
            candidatas.append(item)
    except ImportError:
        print("[IG] modulo instagram nao encontrado. Ignorando.")
    except Exception as e:
        print(f"[IG] erro ao coletar Instagram: {e}")

    print(f"\n[COLETA] {len(candidatas)} candidatas novas no total")
    return candidatas, published


def processar_candidatas(candidatas, themes, max_itens=6):
    """Extrai texto e classifica, retornando as que devem virar matéria.
    Diversifica as fontes (nao deixa uma unica fonte dominar)."""
    selecionadas = []
    por_fonte = {}
    for item in candidatas:
        por_fonte.setdefault(item["fonte"], []).append(item)

    # roda round-robin entre as fontes (uma de cada vez)
    filas = list(por_fonte.values())
    idx = 0
    tentativas = 0
    links_vistos = set()
    limite_tentativas = max_itens * 5
    while len(selecionadas) < max_itens and tentativas < limite_tentativas:
        tentativas += 1
        if not filas:
            break
        fila = filas[idx % len(filas)]
        idx += 1
        if not fila:
            continue
        item = fila.pop(0)
        if item["link"] in links_vistos:
            continue
        print(f"[TEXTO] {item['fonte']}: {item['titulo'][:60]}")

        # Itens do Instagram já vêm com texto e imagem (legenda). Não precisam de extração.
        if item.get("tipo") == "instagram" and item.get("texto"):
            texto = item["texto"]
            imagem = item.get("imagem")
        else:
            texto, imagem = extrair_texto(item["link"])
        if not texto:
            continue
        if not qualidade_minima(item, texto):
            continue
        tema = classificar(item["titulo"], texto, themes)
        if not tema:
            continue
        item["texto"] = texto
        item["tema"] = tema
        if imagem:
            item["imagem_original"] = imagem
        links_vistos.add(item["link"])
        selecionadas.append(item)
        time.sleep(0.5)
    return selecionadas


if __name__ == "__main__":
    candidatas, _ = coleta_completa()
    themes = load_json(THEMES_FILE)
    sel = processar_candidatas(candidatas, themes)
    for s in sel:
        print(f"\n>>> {s['titulo']}\n    [{s['tema']}] {s['fonte']}\n    {s['link']}")
