import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import feedparser
import requests
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS_FILE = os.path.join(BASE_DIR, "fonts.json")
THEMES_FILE = os.path.join(BASE_DIR, "themes.json")
PUBLISHED_FILE = os.path.join(BASE_DIR, "data", "published.json")
FREQ_FILE = os.path.join(BASE_DIR, "data", "font_frequency.json")

TIMEOUT = 30
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 PortalAoVivo"
}
JANELA_HORAS = 48
ANO_ATUAL = datetime.now().year

BRT = timezone(timedelta(hours=-3))


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


def load_frequency():
    if os.path.exists(FREQ_FILE):
        with open(FREQ_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_frequency(data):
    os.makedirs(os.path.dirname(FREQ_FILE), exist_ok=True)
    with open(FREQ_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fonte_deve_coletar(fonte):
    """Verifica se a fonte deve ser coletada agora baseado na frequencia."""
    freq_data = load_frequency()
    fonte_id = fonte["id"]
    freq_horas = fonte.get("frequencia_horas", 3)
    ultima = freq_data.get(fonte_id)

    if not ultima:
        return True

    try:
        ultima_dt = datetime.fromisoformat(ultima).replace(tzinfo=BRT)
    except Exception:
        return True

    agora = datetime.now(BRT)
    horas_desde = (agora - ultima_dt).total_seconds() / 3600
    return horas_desde >= freq_horas


def registrar_coleta(fonte_id):
    """Registra o horario da ultima coleta de uma fonte."""
    freq_data = load_frequency()
    freq_data[fonte_id] = datetime.now(BRT).isoformat()
    save_frequency(freq_data)


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
        link = normalize_url(urljoin(fonte["url"], href))
        # Bloquear paginas de categorias/tags/search
        if re.search(r"/(noticias?/i/|categoria/|tag/|category/|search|pesquisar)", link, re.IGNORECASE):
            continue
        # Bloquear links com query string apenas (buscas, filtros)
        if "?" in link.split("/")[-1]:
            continue
        # Bloquear links muito curtos (paginas institucionais)
        caminho = link.rstrip("/").split("/")[-1]
        if len(caminho) < 5:
            continue
        if not re.search(pattern, link, re.IGNORECASE):
            continue
        if link in seen:
            continue
        seen.add(link)
        titulo = a.get_text(" ", strip=True)
        # Fallback: usar alt do img dentro do link
        if len(titulo) < 10:
            img = a.find("img")
            if img:
                titulo = img.get("alt", "").strip()
        # Fallback: usar titulo do title attribute
        if len(titulo) < 10:
            titulo = a.get("title", "").strip()
        # Pular se titulo e curto demais ou e uma URL
        if len(titulo) < 15:
            continue
        if titulo.startswith("http"):
            continue
        items.append({
            "titulo": titulo[:200],
            "link": link,
            "fonte": fonte["nome"],
            "publicado": None,
        })
    return items[:20]


def coletar_diario_oficial(fonte):
    """Baixa e processa o Diario Oficial mais recente da prefeitura de Patos de Minas."""
    items = []
    r = fetch(fonte["url"])
    if not r:
        return items

    soup = BeautifulSoup(r.content, "lxml")

    # Encontrar a edicao mais recente (primeira com link de download)
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        text = a.get_text(" ", strip=True)

        # Link de download do diario
        if "/portal/download/diario-oficial/" in href or "/portal/diario-oficial/ver/" in href:
            # Extrair numero da edicao e data do texto ao redor
            parent = a.find_parent(["div", "li", "tr", "td", "span"])
            info_text = parent.get_text(" ", strip=True) if parent else text

            # Extrair numero da edicao
            ed_match = re.search(r'n[ÂºoÂ°]\s*(\d+)', info_text)
            edicao_num = ed_match.group(1) if ed_match else "?"

            # Extrair data de postagem
            date_match = re.search(r'Postagem:\s*(\d{2}/\d{2}/\d{4})', info_text)
            data_post = date_match.group(1) if date_match else ""

            link_completo = normalize_url(urljoin(fonte["url"], href))

            # Verificar se eh download direto ou pagina
            pdf_url = None
            if "/portal/download/" in href:
                # Seguir redirect para encontrar o PDF real
                try:
                    r2 = requests.get(link_completo, headers=HEADERS, timeout=30, allow_redirects=True)
                    ct = r2.headers.get("Content-Type", "")
                    if ".pdf" in r2.url or "pdf" in ct:
                        pdf_url = r2.url
                    elif r2.content[:4] == b"%PDF":
                        pdf_url = r2.url
                    else:
                        # Procurar URL do PDF no HTML
                        pdf_match = re.search(r'(/uploads/[^"\']+\.pdf)', r2.text)
                        if pdf_match:
                            pdf_url = "https://www.patosdeminas.mg.gov.br" + pdf_match.group(1)
                except Exception:
                    pass
            elif "/portal/diario-oficial/ver/" in href:
                # Pagina do viewer - procurar PDF no HTML
                try:
                    r2 = requests.get(link_completo, headers=HEADERS, timeout=30)
                    pdf_match = re.search(r'(/uploads/[^"\']+\.pdf)', r2.text)
                    if pdf_match:
                        pdf_url = "https://www.patosdeminas.mg.gov.br" + pdf_match.group(1)
                except Exception:
                    pass

            titulo = f"Diario Oficial Patos de Minas - Edicao {edicao_num}"
            if data_post:
                titulo += f" ({data_post})"

            item = {
                "titulo": titulo,
                "link": pdf_url or link_completo,
                "fonte": fonte["nome"],
                "publicado": None,
                "tipo": "diario_oficial",
                "edicao": edicao_num,
            }

            # Verificar se ja foi publicado
            published = load_published()
            published_links = {p["link"] for p in published}
            if item["link"] not in published_links:
                items.append(item)

            # Apenas a edicao mais recente
            break

    return items


def extrair_texto_diario(pdf_url):
    """Baixa um PDF do Diario Oficial e extrai o texto."""
    try:
        import pdfplumber
    except ImportError:
        print("  [AVISO] pdfplumber nao instalado. Instale: pip install pdfplumber")
        return None

    try:
        r = requests.get(pdf_url, headers=HEADERS, timeout=60)
        if r.status_code != 200:
            print(f"  [ERRO] Falha ao baixar PDF: {r.status_code}")
            return None

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(r.content)
            tmp_path = tmp.name

        texto_completo = []
        with pdfplumber.open(tmp_path) as pdf:
            # Pega apenas as primeiras 10 paginas (resumo)
            max_pages = min(len(pdf.pages), 10)
            for i in range(max_pages):
                page_text = pdf.pages[i].extract_text()
                if page_text:
                    texto_completo.append(page_text)

        os.unlink(tmp_path)

        if not texto_completo:
            return None

        return "\n\n".join(texto_completo)

    except Exception as e:
        print(f"  [ERRO] Ao extrair texto do PDF: {e}")
        return None


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
    try:
        soup = BeautifulSoup(resp.content, "html.parser")
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            url = normalize_url(og["content"].strip())
            if url.startswith("http") and not url.endswith(".svg"):
                return url
        tw = soup.find("meta", attrs={"name": "twitter:image"})
        if tw and tw.get("content"):
            url = normalize_url(tw["content"].strip())
            if url.startswith("http") and not url.endswith(".svg"):
                return url
        for img in soup.find_all("img", src=True):
            src = img["src"].strip()
            if not src or src.endswith(".svg"):
                continue
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
    titulo = item.get("titulo", "")
    if len(titulo) < 20:
        return False
    if titulo.startswith("http"):
        return False
    if item.get("tipo") == "instagram":
        if len(texto.strip()) < 80:
            return False
    elif len(texto.strip()) < 300:
        return False
    return True


def e_recente(link):
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
        # Verificar frequencia
        if not fonte_deve_coletar(fonte):
            print(f"[SKIP] {fonte['nome']} (coletada ha menos de {fonte.get('frequencia_horas', 3)}h)")
            continue

        print(f"[COLETA] {fonte['nome']} ({fonte['tipo']})...")
        try:
            if fonte["tipo"] == "rss":
                itens = coletar_rss(fonte)
            elif fonte["tipo"] == "sitemap":
                itens = coletar_sitemap(fonte)
            elif fonte["tipo"] == "diario_oficial":
                itens = coletar_diario_oficial(fonte)
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

        # Registrar coleta apenas se realmente coletou
        if itens:
            registrar_coleta(fonte["id"])

        time.sleep(0.5)

    # ===== Instagram =====
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
    selecionadas = []
    por_fonte = {}
    for item in candidatas:
        por_fonte.setdefault(item["fonte"], []).append(item)

    filas = list(por_fonte.values())
    idx = 0
    tentativas = 0
    links_vistos = set()
    fontes_usadas = set()
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
        # Limitar 1 post por fonte por execucao
        if item["fonte"] in fontes_usadas:
            continue
        # Pular titulos que sao URLs
        titulo = item.get("titulo", "")
        if titulo.startswith("http"):
            continue
        print(f"[TEXTO] {item['fonte']}: {item['titulo'][:60]}")

        if item.get("tipo") == "diario_oficial":
            # Extrair texto do PDF
            texto = extrair_texto_diario(item["link"])
            imagem = None
        elif item.get("tipo") == "instagram" and item.get("texto"):
            texto = item["texto"]
            imagem = item.get("imagem")
        else:
            texto, imagem = extrair_texto(item["link"])

        if not texto:
            continue

        # Diario oficial: relajar qualidade minima (PDFs curtos)
        if item.get("tipo") == "diario_oficial":
            if len(texto.strip()) < 100:
                continue
        elif not qualidade_minima(item, texto):
            continue

        tema = classificar(item["titulo"], texto, themes)
        if not tema:
            tema = "Geral"
        item["texto"] = texto
        item["tema"] = tema
        if imagem:
            item["imagem_original"] = imagem
        links_vistos.add(item["link"])
        fontes_usadas.add(item["fonte"])
        selecionadas.append(item)
        time.sleep(0.5)
    return selecionadas


if __name__ == "__main__":
    candidatas, _ = coleta_completa()
    themes = load_json(THEMES_FILE)
    sel = processar_candidatas(candidatas, themes)
    for s in sel:
        print(f"\n>>> {s['titulo']}\n    [{s['tema']}] {s['fonte']}\n    {s['link']}")
