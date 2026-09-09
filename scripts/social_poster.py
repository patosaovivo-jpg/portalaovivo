import json
import os
import time
from datetime import datetime, timezone, timedelta

import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOCIAL_LOG = os.path.join(BASE_DIR, "data", "social_log.json")
SOCIAL_RULES_FILE = os.path.join(BASE_DIR, "config", "social_rules.json")
THEMES_FILE = os.path.join(BASE_DIR, "themes.json")

BUFFER_API_URL = "https://api.buffer.com"
LIMITE_INSTAGRAM_DIA = 8

SITE_URL = "https://portalaovivo.com.br"

TEMAS_SOCIAIS = ["Local e Cidades", "Politica", "Esportes", "Geral", "Historia Regional"]

TIMEOUT = 30


def interesse_comercial(materia):
    """Novo foco: só publicar conteúdo que gere clientes (evento ou potencial
    comercial). Conteúdo negativo (crime, política, falecimento, acidente,
    saúde, concurso etc.) é sempre bloqueado, mesmo que uma análise antiga
    tenha atribuído score comercial alto."""
    import re as _re
    import unicodedata as _uni
    titulo = (materia.get("titulo") or "").lower()
    titulo = "".join(
        c for c in _uni.normalize("NFD", titulo)
        if not _uni.combining(c)
    )
    palavras_negativas = _re.compile(
        r"(faleciment|falec|morre|morrer|morte|pres[ao]|detid|agred|"
        r"acidente|incendio|assassin|homicidio|drog|maconha|traf|roubo|"
        r"furto|golp|voce viu|previsao|chuv|tempo|convocac|servent|"
        r"professor|monitor de|diario oficial|nota de|aviso|candidat|"
        r"votacao|sessao legislativa|vereador|deputad|governo|"
        r"secretari|prefeitura nome|servico pub|feriado|"
        r"desaparec|corpo|ferragens|carreta|selv|policia|prf|samu|"
        r"saude|hospital|cirurg|receptac|crime|bairro|mutirao|"
        r"limpeza|manutenc|concurso|medalha|estrela|loucura|"
        r"cooperar|cavalli|uberaba)", _re.IGNORECASE)
    if palavras_negativas.search(titulo):
        return False
    if materia.get("event_related"):
        return True
    if materia.get("event_type"):
        return True
    if materia.get("event_name"):
        return True
    if materia.get("commercial_angle"):
        return True
    try:
        if float(materia.get("commercial_score") or 0) >= 7:
            return True
    except (TypeError, ValueError):
        pass
    # Itens antigos (sem camada de análise): só deixar passar se o título
    # indicar evento ou algo que atraia clientes.
    if any(k in materia for k in
           ("commercial_score", "event_related", "event_type",
            "commercial_angle", "event_name")):
        return False
    palavras_evento = _re.compile(
        r"(festa|show|feira|rodeio|corrida|maratona|campeonato|torneio|"
        r"congresso|conferencia|encontro|formatura|inaugurac|"
        r"aniversario|festival|cavalgada|romaria|exposicao|"
        r"leilao|mega|edital|licitac|preme|feira)", _re.IGNORECASE)
    return bool(palavras_evento.search(titulo))


def _load_json(path, default=None):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[SOCIAL] Config invalida em {path}: {e}")
    return default if default is not None else {}


def load_social_rules():
    return _load_json(SOCIAL_RULES_FILE, {})


def load_themes():
    return _load_json(THEMES_FILE, {})


# ============================================================
# LOG
# ============================================================

def load_social_log():
    if os.path.exists(SOCIAL_LOG):
        with open(SOCIAL_LOG, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"posts": []}


def save_social_log(log):
    os.makedirs(os.path.dirname(SOCIAL_LOG), exist_ok=True)
    log["posts"] = log["posts"][-500:]
    with open(SOCIAL_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def posts_hoje(log):
    hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return sum(
        1 for p in log["posts"]
        if p.get("data", "").startswith(hoje)
        and p.get("plataforma") == "instagram"
    )


def ja_postou(log, link):
    links_recentes = {p["link"] for p in log["posts"][-200:]}
    return link in links_recentes


# ============================================================
# GOOGLE ANALYTICS - MATERIAS MAIS VISTAS
# ============================================================

def buscar_mais_vistas_3h():
    """Busca paginas mais acessadas nas ultimas 3 horas via GA4."""
    service_account_json = os.environ.get("GA_SERVICE_ACCOUNT", "").strip()
    property_id = os.environ.get("GA_PROPERTY_ID", "").strip()

    if not service_account_json or not property_id:
        print("[ANALYTICS] GA4 nao configurado. Pulando busca de populares.")
        return []

    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import (
            DateRange,
            Dimension,
            Metric,
            RunReportRequest,
        )
        from google.oauth2 import service_account as sa
    except ImportError:
        print("[ANALYTICS] Dependencias nao instaladas.")
        return []

    try:
        info = json.loads(service_account_json)
        if "private_key" in info:
            info["private_key"] = info["private_key"].replace("\\n", "\n")
        credentials = sa.Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/analytics.readonly"],
        )
        client = BetaAnalyticsDataClient(credentials=credentials)

        request = RunReportRequest(
            property=f"properties/{property_id}",
            date_ranges=[DateRange(start_date="today", end_date="today")],
            dimensions=[Dimension(name="pagePath"), Dimension(name="pageTitle")],
            metrics=[Metric(name="screenPageViews")],
            dimension_filter={
                "filter": {
                    "field_name": "sessionSource",
                    "string_filter": {
                        "match_type": "CONTAINS",
                        "value": "",
                    },
                }
            },
            order_bys=[
                {"metric": {"metric_name": "screenPageViews"}, "desc": True}
            ],
            limit=20,
        )

        response = client.run_report(request)

        resultados = []
        for row in response.rows:
            path = row.dimension_values[0].value
            titulo = row.dimension_values[1].value
            views = int(row.metric_values[0].value)
            if path and path != "/" and views > 0:
                resultados.append({
                    "path": path,
                    "titulo": titulo.split(" | ")[0].strip() if titulo else "",
                    "visualizacoes": views,
                })

        print(f"[ANALYTICS] {len(resultados)} paginas mais vistas hoje.")
        return resultados

    except Exception as e:
        print(f"[ANALYTICS] Erro ao buscar dados: {e}")
        return []


def _atribuir_views(materias_pendentes):
    """Atribui visualizacoes (GA4/views) a cada materia quando disponiveis."""
    populares = buscar_mais_vistas_3h()
    if not populares:
        print("[SOCIAL] Sem dados de analytics, materias sem views")
        return materias_pendentes

    for pop in populares:
        path_popular = pop["path"].rstrip("/")
        for mat in materias_pendentes:
            link_mat = mat.get("link", "")
            if path_popular in link_mat or link_mat.endswith(path_popular):
                mat["_views"] = max(mat.get("_views", 0), pop["visualizacoes"])
                print(f"[SOCIAL] Match: {pop['titulo'][:50]} ({pop['visualizacoes']} views)")
    return materias_pendentes


def selecionar_materias_por_popularidade(materias_pendentes):
    """Ordena materias por popularidade (GA4) e retorna lista ordenada.

    Mantido para compatibilidade com o fluxo antigo.
    """
    materias_pendentes = _atribuir_views(materias_pendentes)
    return sorted(materias_pendentes, key=lambda m: m.get("_views", 0), reverse=True)


def calcular_priority_score(mat, regras=None):
    """Score de prioridade social configurável.

    priority_score =
        views_score        * peso.views
        + instagram_score  * peso.instagram_score
        + commercial_score * peso.commercial_score
        + regional         * peso.regional
        + event_related    * peso.event

    views/regional/event normalizados em 0-10.
    Pesos em config/social_rules.json.
    """
    regras = regras or load_social_rules()
    pesos = (regras.get("priorizacao") or {}).get("weights", {})
    ceiling = float((regras.get("priorizacao") or {}).get("views_ceiling", 500))
    regional_value = float((regras.get("priorizacao") or {}).get("regional_value", 10))
    event_value = float((regras.get("priorizacao") or {}).get("event_value", 10))

    views = float(mat.get("_views", 0) or 0)
    views_score = min(10.0, (views / ceiling) * 10.0) if ceiling else 0.0

    insta = _clamp_score(mat.get("instagram_score", 5))
    comerc = _clamp_score(mat.get("commercial_score", 0))
    regional = regional_value if mat.get("regional") else 0.0
    evento = event_value if mat.get("event_related") else 0.0

    total = (
        views_score * float(pesos.get("views", 1.0))
        + insta * float(pesos.get("instagram_score", 2.0))
        + comerc * float(pesos.get("commercial_score", 2.0))
        + regional * float(pesos.get("regional", 1.5))
        + evento * float(pesos.get("event", 1.5))
    )
    return round(total, 2)


def _clamp_score(valor):
    try:
        return max(0.0, min(10.0, float(valor)))
    except (TypeError, ValueError):
        return 0.0


def ordenar_por_prioridade(materias_pendentes, regras=None):
    """Ordena matérias pela prioridade social (GA4 + scores + relevância regional/evento)."""
    materias_pendentes = _atribuir_views(materias_pendentes)
    regras = regras or load_social_rules()
    for mat in materias_pendentes:
        mat["_priority_score"] = calcular_priority_score(mat, regras)
    return sorted(materias_pendentes,
                  key=lambda m: m.get("_priority_score", 0), reverse=True)


# ============================================================
# BUFFER API
# ============================================================

def buffer_graphql(query, variables=None):
    """Executa uma query GraphQL na API do Buffer."""
    api_key = os.environ.get("BUFFER_API_KEY", "").strip()
    if not api_key:
        print("[BUFFER] BUFFER_API_KEY nao definido")
        return None

    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    try:
        r = requests.post(
            BUFFER_API_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + api_key,
            },
            json=payload,
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[BUFFER] Erro GraphQL: {e}")
        return None


def obter_channel_id_instagram():
    """Busca o channel ID do Instagram conectado no Buffer."""
    channel_id = os.environ.get("BUFFER_IG_CHANNEL_ID", "").strip()
    if channel_id:
        return channel_id

    orgs_data = buffer_graphql("""
        query {
            account {
                organizations {
                    id
                }
            }
        }
    """)
    if not orgs_data:
        return None

    orgs = orgs_data.get("data", {}).get("account", {}).get("organizations", [])
    if not orgs:
        return None

    org_id = orgs[0]["id"]
    channels_data = buffer_graphql("""
        query {
            channels(input: { organizationId: "%s" }) {
                id
                service
                displayName
            }
        }
    """ % org_id)

    if not channels_data:
        return None

    channels = channels_data.get("data", {}).get("channels", [])
    for ch in channels:
        if ch.get("service") == "instagram":
            print(f"[BUFFER] Instagram encontrado: {ch['displayName']} (ID: {ch['id']})")
            return ch["id"]

    return None


def _default_hashtags():
    regras = load_social_rules()
    return regras.get("default_hashtags",
                      "#PortalAoVivo #Noticias #PatosDeMinas "
                      "#AltoParanai #TrianguloMineiro #MinasGerais "
                      "#NoticiasRegionais #UltimaHora")


def gerar_legenda(item, resumo):
    """Gera legenda usando conteúdo social estruturado quando disponível."""
    titulo = item.get("titulo", "")
    link = item.get("link", "")
    conteudo_social = item.get("conteudo_social") if isinstance(item.get("conteudo_social"), dict) else None

    # Conteúdo especial (Reel/Carousel) gerado pela inteligência
    if conteudo_social:
        reel = conteudo_social.get("reel") or {}
        caption = reel.get("caption") or reel.get("script") or ""
        if caption:
            corpo = caption[:2000]
            return f"{titulo}\n\n{corpo}\n\n{SITE_URL}{link.replace('.html', '').rstrip('/')}"

        hook = reel.get("hook", "")
        script = reel.get("script", "")
        cta = reel.get("cta", "")
        corpo = " ".join(x for x in (hook, script, cta) if x)
        if corpo:
            corpo = corpo[:2000]
            return f"{titulo}\n\n{corpo}\n\n{SITE_URL}{link.replace('.html', '').rstrip('/')}"

    primeiro_par = resumo.strip().split("\n")[0].strip()

    texto = primeiro_par[:400]
    if len(primeiro_par) > 400:
        texto += "..."

    hashtags = _default_hashtags()

    legenda = f"{titulo}\n\n{texto}\n\n{SITE_URL}{link.replace('.html', '').rstrip('/')}\n\n{hashtags}"
    return legenda


def imagem_url_para_site(imagem_rel):
    """Converte caminho relativo para URL publica do site. Ja retorna URLs completas."""
    if not imagem_rel:
        return None
    if imagem_rel.startswith("http"):
        return imagem_rel
    caminho = imagem_rel.lstrip("/")
    return f"{SITE_URL}/{caminho}"


def imagem_acessivel(url, timeout=20):
    """Verifica se a imagem esta acessivel publicamente (HTTP 200 + content-type de imagem)."""
    if not url:
        return False
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.head(url, timeout=timeout, headers=headers, allow_redirects=True)
        if r.status_code == 405:
            r = requests.get(url, timeout=timeout, headers=headers, stream=True)
        if r.status_code != 200:
            print(f"  [IMG] Falhou HTTP {r.status_code}: {url[:90]}")
            return False
        ctype = r.headers.get("Content-Type", "") or r.headers.get("content-type", "")
        if ctype and not ctype.lower().startswith("image"):
            print(f"  [IMG] Content-Type nao e imagem ({ctype}): {url[:90]}")
            return False
        return True
    except Exception as e:
        print(f"  [IMG] Erro ao checar imagem: {e}")
        return False


def postar_instagram_buffer(item, resumo, imagem_url):
    """Posta no Instagram via Buffer API."""
    channel_id = obter_channel_id_instagram()
    if not channel_id:
        print("[BUFFER] Nenhum canal Instagram encontrado")
        return False

    legenda = gerar_legenda(item, resumo)

    assets = []
    if imagem_url:
        assets.append({
            "image": {"url": imagem_url}
        })

    query = """
    mutation CreateInstagramPost($input: CreatePostInput!) {
        createPost(input: $input) {
            ... on PostActionSuccess {
                post {
                    id
                    text
                    dueAt
                }
            }
            ... on MutationError {
                message
            }
        }
    }
    """

    variables = {
        "input": {
            "text": legenda,
            "channelId": channel_id,
            "schedulingType": "automatic",
            "mode": "shareNow",
            "metadata": {
                "instagram": {
                    "type": "post",
                    "shouldShareToFeed": True
                }
            }
        }
    }

    if assets:
        variables["input"]["assets"] = assets

    result = buffer_graphql(query, variables)
    if not result:
        print("[BUFFER] Resposta vazia")
        return False

    post_data = result.get("data", {}).get("createPost", {})
    if "post" in post_data:
        post_id = post_data["post"].get("id", "?")
        due = post_data["post"].get("dueAt", "?")
        print(f"[BUFFER] OK Post publicado (ID: {post_id}, para: {due})")
        return True
    else:
        msg = post_data.get("message", "erro desconhecido")
        print(f"[BUFFER] ERRO: {msg}")
        return False


# ============================================================
# POSTAGEM PRINCIPAL
# ============================================================

def postar_materias(materias):
    log = load_social_log()
    posts_ig = posts_hoje(log)

    print(f"[SOCIAL] Hoje: {posts_ig} posts Instagram")

    if posts_ig >= LIMITE_INSTAGRAM_DIA:
        print(f"[SOCIAL] Limite diario atingido ({LIMITE_INSTAGRAM_DIA})")
        return 0

    vagas = LIMITE_INSTAGRAM_DIA - posts_ig
    max_por_rodada = min(3, vagas)

    materias_filtradas = [
        m for m in materias
        if m.get("tema", "") in TEMAS_SOCIAIS
        and not ja_postou(log, m["link"])
        and interesse_comercial(m)
    ]

    if not materias_filtradas:
        print("[SOCIAL] Nenhuma materia nova para postar")
        return 0

    materias_ordenadas = ordenar_por_prioridade(materias_filtradas)
    escolhidas = materias_ordenadas[:max_por_rodada]

    postadas = 0
    for i, escolhida in enumerate(escolhidas):
        imagem_url = imagem_url_para_site(escolhida.get("imagem", ""))
        if not imagem_url:
            print(f"[SOCIAL] Sem imagem: {escolhida.get('titulo', '')[:50]}")
            continue

        if not imagem_acessivel(imagem_url):
            print(f"[SOCIAL] Imagem inacessivel, pulando: {escolhida.get('titulo', '')[:50]}")
            continue

        if i > 0:
            print(f"[SOCIAL] Aguardando 60s entre posts...")
            time.sleep(60)

        print(f"\n[SOCIAL] Postando ({postadas + 1}/{len(escolhidas)}): {escolhida.get('titulo', '')[:60]}")

        sucesso = postar_instagram_buffer(escolhida, escolhida.get("resumo", ""), imagem_url)

        if sucesso:
            log["posts"].append({
                "link": escolhida["link"],
                "titulo": escolhida.get("titulo", ""),
                "plataforma": "instagram",
                "data": datetime.now(timezone.utc).isoformat(),
            })
            save_social_log(log)
            postadas += 1

    return postadas


def processar_pendentes():
    pending_file = os.path.join(BASE_DIR, "data", "pending_social.json")
    if not os.path.exists(pending_file):
        print("[SOCIAL] Nenhum post pendente")
        return 0
    with open(pending_file, "r", encoding="utf-8") as f:
        materias = json.load(f)
    if not materias:
        print("[SOCIAL] Lista vazia")
        return 0

    # Novo foco: remover da fila o que não gera clientes (evento/oportunidade).
    antes = len(materias)
    materias = [m for m in materias if interesse_comercial(m)]
    removidas = antes - len(materias)
    if removidas:
        print(f"[SOCIAL] {removidas} materia(s) fora do foco removidas da fila")
    if not materias:
        if os.path.exists(pending_file):
            os.remove(pending_file)
        print("[SOCIAL] Fila agora vazia (tudo fora do foco)")
        return 0

    total = postar_materias(materias)

    log = load_social_log()
    materias_restantes = [
        m for m in materias
        if not ja_postou(log, m["link"])
    ]

    if materias_restantes:
        with open(pending_file, "w", encoding="utf-8") as f:
            json.dump(materias_restantes, f, ensure_ascii=False, indent=2)
        print(f"[SOCIAL] {len(materias_restantes)} materia(s) restante(s) para proximas rodadas")
    else:
        os.remove(pending_file)

    return total


if __name__ == "__main__":
    processar_pendentes()
