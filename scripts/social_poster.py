import json
import os
from datetime import datetime, timezone, timedelta

import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOCIAL_LOG = os.path.join(BASE_DIR, "data", "social_log.json")

BUFFER_API_URL = "https://api.buffer.com"
LIMITE_INSTAGRAM_DIA = 8
LIMITE_INSTAGRAM_ALTA = 10
LIMITE_VIEWS_ALTA = 500

SITE_URL = "https://portalaovivo.com.br"

TEMAS_SOCIAIS = ["Local e Cidades", "Politica"]

TIMEOUT = 30


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


def selecionar_materias_por_popularidade(materias_pendentes):
    """Ordena materias por popularidade (GA4) e retorna lista ordenada."""
    populares = buscar_mais_vistas_3h()
    if not populares:
        print("[SOCIAL] Sem dados de analytics, mantendo ordem original")
        return materias_pendentes

    populares_map = {}
    for pop in populares:
        path_popular = pop["path"].rstrip("/")
        for mat in materias_pendentes:
            link_mat = mat.get("link", "")
            if path_popular in link_mat or link_mat.endswith(path_popular):
                populares_map[mat["link"]] = pop["visualizacoes"]
                mat["_views"] = pop["visualizacoes"]
                print(f"[SOCIAL] Match: {pop['titulo'][:50]} ({pop['visualizacoes']} views)")

    ordenadas = sorted(materias_pendentes, key=lambda m: m.get("_views", 0), reverse=True)
    return ordenadas


def eh_trafego_alto(materias):
    """Verifica se o trafego justifica posts extras."""
    for m in materias:
        if m.get("_views", 0) >= LIMITE_VIEWS_ALTA:
            print(f"[SOCIAL] Trafego alto detectado: {m.get('_views', 0)} views")
            return True
    return False


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


def gerar_legenda(item, resumo):
    titulo = item.get("titulo", "")
    link = item.get("link", "")
    primeiro_par = resumo.strip().split("\n")[0].strip()

    texto = primeiro_par[:400]
    if len(primeiro_par) > 400:
        texto += "..."

    hashtags = (
        "#PortalAoVivo #Noticias #PatosDeMinas "
        "#AltoParanai #TrianguloMineiro #MinasGerais "
        "#NoticiasRegionais #UltimaHora"
    )

    legenda = f"{titulo}\n\n{texto}\n\n{SITE_URL}{link.replace('.html', '').rstrip('/')}\n\n{hashtags}"
    return legenda


def imagem_url_para_site(imagem_rel):
    """Converte caminho relativo para URL publica do site."""
    if not imagem_rel:
        return None
    caminho = imagem_rel.lstrip("/")
    return f"{SITE_URL}/{caminho}"


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
            "mode": "addToQueue",
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
        print(f"[BUFFER] OK Post agendado (ID: {post_id}, para: {due})")
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

    materias_filtradas = [
        m for m in materias
        if m.get("tema", "") in TEMAS_SOCIAIS and not ja_postou(log, m["link"])
    ]

    if not materias_filtradas:
        print("[SOCIAL] Nenhuma materia nova para postar")
        return 0

    materias_ordenadas = selecionar_materias_por_popularidade(materias_filtradas)

    if eh_trafego_alto(materias_ordenadas):
        limite = LIMITE_INSTAGRAM_ALTA
    else:
        limite = LIMITE_INSTAGRAM_DIA

    vagas = limite - posts_ig
    if vagas <= 0:
        print(f"[SOCIAL] Limite diario atingido ({limite})")
        return 0

    total = 0
    for mat in materias_ordenadas:
        if total >= vagas:
            break

        imagem_url = imagem_url_para_site(mat.get("imagem", ""))
        if not imagem_url:
            print(f"[SOCIAL] Sem imagem: {mat.get('titulo', '')[:50]}")
            continue

        print(f"\n[SOCIAL] Postando ({total + 1}/{vagas}): {mat.get('titulo', '')[:60]}")

        sucesso = postar_instagram_buffer(mat, mat.get("resumo", ""), imagem_url)

        if sucesso:
            log["posts"].append({
                "link": mat["link"],
                "titulo": mat.get("titulo", ""),
                "plataforma": "instagram",
                "data": datetime.now(timezone.utc).isoformat(),
            })
            total += 1

    if total > 0:
        save_social_log(log)

    return total


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
    total = postar_materias(materias)
    os.remove(pending_file)
    return total


if __name__ == "__main__":
    processar_pendentes()
