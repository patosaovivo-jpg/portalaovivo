import json
import os
import time
from datetime import datetime, timezone

import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HASHTAGS_FILE = os.path.join(BASE_DIR, "hashtags.json")

API_VERSION = "v21.0"
GRAPH_URL = f"https://graph.facebook.com/{API_VERSION}"
TIMEOUT = 30
MAX_POR_HASHTAG = 10

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 PortalAoVivo"
}


def load_hashtags():
    if not os.path.exists(HASHTAGS_FILE):
        return []
    with open(HASHTAGS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    tags = data.get("hashtags", []) if isinstance(data, dict) else data
    return [t.strip().lstrip("#").lower() for t in tags if t.strip()]


def extrair_legenda(caption):
    """Pega o texto da legenda, removendo as hashtags de rodapé."""
    if not caption:
        return ""
    # remove linhas que sejam apenas hashtags
    linhas = []
    for linha in caption.split("\n"):
        limpa = linha.strip()
        if not limpa:
            continue
        # se a linha é composta só de hashtags/@, ignora
        sem_simbolos = limpa.replace("#", "").replace("@", "").replace(" ", "")
        if sem_simbolos and not all(c.isalnum() for c in sem_simbolos):
            linhas.append(limpa)
        elif sem_simbolos:
            linhas.append(limpa)
    return "\n".join(linhas).strip()


def resolver_hashtag_id(hashtag, token, ig_user_id):
    """Resolve o nome da hashtag para o ID na API."""
    url = f"{GRAPH_URL}/{ig_user_id}/ig_hashtag_search"
    params = {"q": hashtag, "access_token": token}
    r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    dados = r.json().get("data", [])
    if not dados:
        return None
    # procura o match exato (case-insensitive)
    for item in dados:
        if item.get("name", "").lower() == hashtag.lower():
            return item["id"]
    return dados[0]["id"]


def coletar_hashtag(hashtag, token, ig_user_id):
    """Busca os posts recentes de uma hashtag."""
    items = []
    try:
        hashtag_id = resolver_hashtag_id(hashtag, token, ig_user_id)
        if not hashtag_id:
            print(f"  [IG] hashtag #{hashtag}: nao encontrada")
            return items
    except Exception as e:
        print(f"  [IG] erro ao resolver #{hashtag}: {e}")
        return items

    url = f"{GRAPH_URL}/{hashtag_id}/recent_media"
    params = {
        "fields": "caption,media_url,permalink,timestamp,username",
        "limit": MAX_POR_HASHTAG,
        "access_token": token,
    }
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        dados = r.json().get("data", [])
    except Exception as e:
        print(f"  [IG] erro ao buscar posts de #{hashtag}: {e}")
        return items

    for post in dados:
        legenda = extrair_legenda(post.get("caption", ""))
        link = post.get("permalink", "")
        if not link:
            continue
        publicado = None
        if post.get("timestamp"):
            try:
                publicado = datetime.fromisoformat(
                    post["timestamp"].replace("Z", "+00:00")
                )
            except Exception:
                publicado = None
        items.append({
            "titulo": legenda.split("\n")[0][:120] if legenda else f"Post #{hashtag}",
            "link": link,
            "fonte": f"Instagram @{post.get('username', hashtag)}",
            "publicado": publicado.isoformat() if publicado else None,
            "texto": legenda,
            "imagem": post.get("media_url", ""),
            "tema": "Instagram",
        })
    print(f"  [IG] #{hashtag}: {len(items)} posts")
    return items


def coletar_instagram():
    """Ponto de entrada: lê hashtags.json e busca os posts de cada uma."""
    token = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "").strip()
    ig_user_id = os.environ.get("INSTAGRAM_IG_USER_ID", "").strip()
    if not token or not ig_user_id:
        print("[IG] INSTAGRAM_ACCESS_TOKEN/INSTAGRAM_IG_USER_ID nao definidos. Ignorando Instagram.")
        return []

    hashtags = load_hashtags()
    if not hashtags:
        print("[IG] Nenhuma hashtag configurada em hashtags.json")
        return []

    items = []
    print(f"[IG] Monitorando {len(hashtags)} hashtag(s)...")
    for hashtag in hashtags:
        try:
            itens = coletar_hashtag(hashtag, token, ig_user_id)
            items.extend(itens)
        except Exception as e:
            print(f"  [IG] erro em #{hashtag}: {e}")
        time.sleep(1)
    print(f"[IG] {len(items)} posts coletados no total")
    return items


if __name__ == "__main__":
    for it in coletar_instagram():
        print(f">>> {it['titulo'][:60]} | {it['fonte']} | {it['link']}")
