import json
import os
import re
import sys
import time
import urllib.parse
from datetime import datetime, timezone, timedelta

# Forcar saida UTF-8 para evitar erro de codificacao (emoji) no console Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIRAL_TOPICS_FILE = os.path.join(BASE_DIR, "data", "viral_topics.json")
POSTS_DIR = os.path.join(BASE_DIR, "_posts")

BRT = timezone(timedelta(hours=-3))

WIKI_HEADERS = {
    "User-Agent": (
        "PortalAoVivoBot/1.0 (https://portalaovivo.com.br; contato: "
        "bot@portalaovivo.com.br) Python/requests"
    )
}

# ============================================================
# CATEGORIAS DE CONTEUDO VIRAL - ALTO PARANAIBA / MG
# ============================================================

CATEGORIAS = {
    "povoados_abandonados": {
        "nome": "Povoados Abandonados",
        "emoji": "\U0001f3da\ufe0f",
        "pesquisas": [
            "povoados abandonados Alto Paranaiba Minas Gerais",
            "cidades fantasma interior Minas Gerais",
            "povoado abandonado Triangulo Mineiro",
            "comunidade abandonada Patos de Minas Patrocinio",
            "fazendas abandonadas historicas Minas Gerais",
            "arruados Minas Gerais cidades que pararam",
        ],
        "pesquisas_gerais": [
            "cidades abandonadas Brasil interior",
            "povoados fantasma Brasil historia",
        ],
    },
    "lendas_misteriosas": {
        "nome": "Lendas e Historias Misteriosas",
        "emoji": "\U0001f47b",
        "pesquisas": [
            "lendas misteriosas Alto Paranaiba",
            "historias sobrenaturais Triangulo Mineiro",
            "casas assombradas Patos de Minas Patrocinio",
            "lendas populares Minas Gerais interior",
            "mitos e lendas do cerrado mineiro",
            "aparicoes igrejas antigas Minas Gerais",
        ],
        "pesquisas_gerais": [
            "lendas brasileiras menos conhecidas",
            "historias misteriosas do interior do Brasil",
        ],
    },
    "tesouros_garimpos": {
        "nome": "Tesouros e Garimpos",
        "emoji": "\U0001f48e",
        "pesquisas": [
            "garimpos historicos Minas Gerais",
            "tesouros escondidos Alto Paranaiba",
            "bandeirantes garimpeiros Triangulo Mineiro",
            "ouro pedras preciosas Minas Gerais historia",
            "garimpo do rio Paranaiba historia",
            "fazendas de ouro Minas Gerais colonia",
        ],
        "pesquisas_gerais": [
            "tesouros enterrados Brasil",
            "historias de garimpos brasileiros",
        ],
    },
    "mudanca_nome": {
        "nome": "Cidades que Mudaram de Nome",
        "emoji": "\U0001f5fa\ufe0f",
        "pesquisas": [
            "cidades que mudaram de nome Minas Gerais",
            "antigos nomes cidades Alto Paranaiba",
            "toponimia historica Triangulo Mineiro",
            "nome antigo Patos de Minas Patrocinio",
            "etimologia nomes cidades mineiras",
            "historia nomes cidades interior MG",
        ],
        "pesquisas_gerais": [
            "cidades brasileiras que mudaram de nome",
            "origem nomes cidades Minas Gerais",
        ],
    },
    "ferrovias": {
        "nome": "Antigas Ferrovias",
        "emoji": "\U0001f682",
        "pesquisas": [
            "ferrovias historicas Minas Gerais",
            "estrada de ferro Triangulo Mineiro",
            "E.F.M.G. historia Alto Paranaiba",
            "ferrovia Patos de Minas Uberaba",
            "antiga ferrovia|mineracao Minas Gerais",
            "trilhos abandonados interior MG",
        ],
        "pesquisas_gerais": [
            "ferrovias abandonadas Brasil historia",
            "estradas de ferro coloniais Minas",
        ],
    },
    "caminhos_tropeiros": {
        "nome": "Estradas Antigas e Caminhos de Tropeiros",
        "emoji": "\U0001f6e3\ufe0f",
        "pesquisas": [
            "caminhos de tropeiros Minas Gerais",
            "antigos caminhos Alto Paranaiba",
            "estradas coloniais Triangulo Mineiro",
            "tropeiros historia interior MG",
            "picadas antigas Patos de Minas",
            "rotas do sal ouro Minas Gerais",
        ],
        "pesquisas_gerais": [
            "caminhos historicos Brasil colonial",
            "tropeiros do Brasil historia",
        ],
    },
    "igrejas_antigas": {
        "nome": "Igrejas Antigas",
        "emoji": "\u26ea",
        "pesquisas": [
            "igrejas centenarias Alto Paranaiba",
            "antigas igrejas Triangulo Mineiro",
            "patrimonio historico religioso MG",
            "igreja matriz historica Minas Gerais",
            "capelas antigas interior mineiro",
            "arquitetura religiosa colonia MG",
        ],
        "pesquisas_gerais": [
            "igrejas mais antigas Brasil",
            "patrimonio religioso Minas Gerais",
        ],
    },
    "predios_historicos": {
        "nome": "Predios Historicos",
        "emoji": "\U0001f3db\ufe0f",
        "pesquisas": [
            "predios historicos Patos de Minas",
            "casas antigas Alto Paranaiba",
            "arquitetura colonial Triangulo Mineiro",
            "patrimonio historico edificacoes MG",
            "antigos sobrados Minas Gerais",
            "fazendas seculares Minas Gerais",
        ],
        "pesquisas_gerais": [
            "edificios historicos Brasil",
            "arquitetura patrimonial Minas Gerais",
        ],
    },
    "personagens_esquecidos": {
        "nome": "Personagens Importantes Esquecidos",
        "emoji": "\U0001f468\u200d\U0001f33e",
        "pesquisas": [
            "fundadores cidades Alto Paranaiba",
            "personagens historicos Triangulo Mineiro",
            "pioneiros Patos de Minas Patrocinio",
            "bandeirantes Minas Gerais historia",
            "jejenes tropelheiros interior MG",
            "grandes fazendeiros historia MG",
        ],
        "pesquisas_gerais": [
            "personagens esquecidos da historia mineira",
            "pioneiros do Brasil interior",
        ],
    },
    "grandes_fortunas": {
        "nome": "Historias de Grandes Fortunas",
        "emoji": "\U0001f4b0",
        "pesquisas": [
            "grandes fortunas Minas Gerais historia",
        ],
        "pesquisas_gerais": [
            "fortunas historicas Brasil",
            "grandes fazendeiros ouro Minas",
        ],
    },
    "conflitos_incomuns": {
        "nome": "Conflitos e Acontecimentos Incomuns",
        "emoji": "\u2694\ufe0f",
        "pesquisas": [
            "conflitos historicos Alto Paranaiba",
            "guerras civis Triangulo Mineiro",
            "revoltas populares Minas Gerais",
            "acontecimentos estranhos MG historia",
            "batalhas esquecidas interior MG",
            "episodios curiosos Minas colonia",
        ],
        "pesquisas_gerais": [
            "acontecimentos incomuns Brasil historia",
            "episodios bizarros historia mineira",
        ],
    },
    "fotos_antigas": {
        "nome": "Fotos Antigas Comparadas",
        "emoji": "\U0001f4f7",
        "pesquisas": [
            "fotos antigas Patos de Minas",
            "fotos antigas Triangulo Mineiro",
            "fotos antigas Alto Paranaiba MG",
            "fotos antigas comparadas atuais MG",
            "antigas fotografias interior MG",
            "arquivo historico fotografico MG",
        ],
        "pesquisas_gerais": [
            "fotos antigas vs atuais cidades BR",
            "fotografia historica Minas Gerais",
        ],
    },
    "voce_sabia": {
        "nome": "Voce Sabia Que...?",
        "emoji": "\U0001f92f",
        "pesquisas": [
            "curiosidades historicas Alto Paranaiba",
            "voce sabia Minas Gerais interior",
            "curiosidades Triangulo Mineiro",
            "primeiro comercio escola cinema MG",
            "primeiro telefone radio Triangulo",
            "marcos historicos Minas Gerais",
            "feitos primeros Minas Gerais",
        ],
        "pesquisas_gerais": [
            "curiosidades brasileiras menos sabidas",
            "primeiros do Brasil historia",
        ],
    },
    "eustaquio_amaral": {
        "nome": "Eustaquio Amaral - Historia Regional",
        "emoji": "\U0001f4d6",
        "pesquisas": [
            "Eustaquio Amaral Alto Paranaiba colunista",
            "Eustaquio Amaral historias regionais",
            "Eustaquio Amaral nomes antigos cidades",
            "Eustaquio Amaral territorialidade MG",
            "Eustaquio Amaral curiosidades historicas",
            "coluna Eustaquio Amaral Patos de Minas",
        ],
        "pesquisas_gerais": [
            "Eustaquio Amaral Minas Gerais historias",
        ],
    },
}


# ============================================================
# CONTROLE DE TOPICOS UTILIZADOS
# ============================================================

def load_viral_topics():
    if os.path.exists(VIRAL_TOPICS_FILE):
        with open(VIRAL_TOPICS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"utilizados": [], "ultima_execucao": None, "stats": {}}


def save_viral_topics(data):
    os.makedirs(os.path.dirname(VIRAL_TOPICS_FILE), exist_ok=True)
    with open(VIRAL_TOPICS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def ja_utilizou(topicos, titulo):
    """Verifica se um titulo similar ja foi utilizado."""
    titulo_lower = titulo.lower().strip()
    for t in topicos.get("utilizados", []):
        t_lower = t.lower().strip()
        if titulo_lower == t_lower:
            return True
        palavras_titulo = set(titulo_lower.split())
        palavras_util = set(t_lower.split())
        if len(palavras_titulo & palavras_util) > len(palavras_titulo) * 0.7:
            return True
    return False


def registrar_utilizado(topicos, titulo, categoria):
    topicos.setdefault("utilizados", []).append(titulo)
    topicos["utilizados"] = topicos["utilizados"][-300:]
    topicos["ultima_execucao"] = datetime.now(BRT).isoformat()
    topicos.setdefault("stats", {})
    topicos["stats"][categoria] = topicos["stats"].get(categoria, 0) + 1
    save_viral_topics(topicos)


# ============================================================
# PESQUISA WEB
# ============================================================

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"


def _url_encoding_query(query):
    """Codifica a query para a URL de busca."""
    return urllib.parse.quote(query)


def pesquisar_google_news(query, num_results=8):
    """Busca noticias no Google News RSS (gratuito, sem chave).

    Retorna lista de dicts com titulo, texto (resumo), url e origem.
    Usa o operador when:30d para pegar conteudo das ultimas 30 dias.
    """
    import feedparser

    try:
        params = (
            f"?q={_url_encoding_query(query)}+when%3A90d&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        )
        url = GOOGLE_NEWS_RSS + params
        resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            print(f"  [GNEWS] HTTP {resp.status_code} para: {query[:50]}")
            return []

        feed = feedparser.parse(resp.content)
        resultados = []
        for entry in feed.entries[:num_results]:
            titulo = entry.get("title", "").strip()
            if not titulo:
                continue
            resumo = entry.get("summary", "") or entry.get("description", "") or ""
            resumo = _limpar_snippet(resumo)
            origem = entry.get("source", {}).get("title", "") if entry.get("source") else ""
            resultados.append({
                "titulo": titulo,
                "texto": resumo or titulo,
                "url": entry.get("link", ""),
                "fonte": origem,
            })
        if resultados:
            print(f"  [GNEWS] {len(resultados)} resultados para: {query[:50]}")
        # Enriquecer com contexto enciclopedico (Wikipedia) por titulo,
        # pois os links do Google News sao tokens de redirect sem URL real.
        enriquecidos = 0
        for r in resultados:
            if len(r["texto"]) < 300:
                contexto = _buscar_contexto_wiki(r["titulo"])
                if contexto and len(contexto) > len(r["texto"]):
                    r["texto"] = r["texto"] + "\n\n" + contexto[:1200]
                    enriquecidos += 1
        if enriquecidos:
            print(f"  [GNEWS] {enriquecidos} resultado(s) enriquecido(s) com contexto")
        return resultados
    except Exception as e:
        print(f"  [GNEWS] erro para '{query[:40]}': {e}")
        return []


def _buscar_contexto_wiki(assunto):
    """Busca na Wikipedia um resumo enciclopedico sobre o tema central do titulo.

    Extrai termos-chave (>=4 letras, sem stopwords comuns de noticia) do titulo
    para formar uma busca curta e eficaz.
    """
    # Extrair palavras-chave relevantes do titulo
    stop = {
        "que", "para", "com", "dos", "das", "uma", "sobre", "apos", "mais",
        "seu", "sua", "como", "foi", "ser", "est", "ao", "da", "de", "em",
        "e", "o", "a", "do", "no", "na", "pela", "pelo", "sao", "que", "e",
        "cresce", "registra", "defende", "avanco",
    }
    termos = [
        w.lower() for w in re.findall(r"[A-Za-zÀ-ú]{4,}", assunto)
        if w.lower() not in stop
    ]
    # Priorizar termos com mais caracteres / que sejam nomes proprios
    termos_top = sorted(set(termos), key=lambda w: len(w), reverse=True)[:2]
    query = " ".join(termos_top) if termos_top else assunto

    try:
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "utf8": 1,
            "srlimit": 1,
        }
        r = requests.get(
            "https://pt.wikipedia.org/w/api.php",
            params=params,
            timeout=15,
            headers=WIKI_HEADERS,
        )
        if r.status_code != 200:
            return None
        hits = r.json().get("query", {}).get("search", [])
        if not hits:
            return None
        titulo = hits[0].get("title", "")
        return _buscar_intro_wiki("https://pt.wikipedia.org/w/api.php", titulo)
    except Exception:
        return None


def pesquisar_web(query, num_results=5):
    """Realiza pesquisa web e retorna resultados.

    Cascata de fontes:
      1. Google News RSS (gratuito, regional BR) - principal
      2. Wikipedia (pt) - fallback enciclopedico
    """
    # 1. Tenta Google News RSS primeiro (melhor para noticias/curiosidades BR)
    resultados = pesquisar_google_news(query, num_results=num_results)
    if resultados:
        return resultados

    # 2. Fallback websearch (quando disponivel)
    try:
        from websearch import websearch
        results = websearch(query, num_results=num_results)
        if results:
            return results
    except ImportError:
        pass

    # 3. Ultimo fallback: Wikipedia (pt)
    resultados = []
    urls_fontes = [
        "https://pt.wikipedia.org/w/api.php",
    ]

    for url in urls_fontes:
        try:
            params = {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "utf8": 1,
                "srlimit": num_results,
            }
            r = requests.get(url, params=params, timeout=15, headers=WIKI_HEADERS)
            if r.status_code == 200:
                data = r.json()
                hits = data.get("query", {}).get("search", [])
                for item in hits:
                    titulo = item.get("title", "")
                    snippet = _limpar_snippet(item.get("snippet", ""))
                    intro = _buscar_intro_wiki(url, titulo)
                    texto = intro or snippet
                    resultados.append({
                        "titulo": titulo,
                        "texto": texto,
                        "url": f"https://pt.wikipedia.org/wiki/{titulo.replace(' ', '_')}",
                    })
        except Exception:
            continue

    return resultados


def _limpar_snippet(snippet):
    """Remove marcacao HTML dos snippets de busca."""
    snippet = re.sub(r"<[^>]+>", "", snippet)
    snippet = snippet.replace("&amp;", "&").replace("&#32;", " ")
    return snippet.strip()


def _buscar_intro_wiki(api_url, titulo):
    """Busca o resumo (intro) de um artigo da Wikipedia."""
    try:
        params = {
            "action": "query",
            "prop": "extracts",
            "explaintext": 1,
            "exintro": 1,
            "exlimit": 1,
            "titles": titulo,
            "format": "json",
            "utf8": 1,
            "redirects": 1,
        }
        r = requests.get(api_url, params=params, timeout=15, headers=WIKI_HEADERS)
        if r.status_code == 200:
            data = r.json()
            pages = data.get("query", {}).get("pages", {})
            for page in pages.values():
                text = page.get("extract", "")
                return text[:1200].strip() or None
    except Exception:
        pass
    return None


def pesquisar_para_categoria(categoria_id, config):
    """Pesquisa todas as queries de uma categoria."""
    todos_resultados = []
    pesquisas = config.get("pesquisas", []) + config.get("pesquisas_gerais", [])

    for query in pesquisas[:4]:
        try:
            resultados = pesquisar_web(query, num_results=3)
            todos_resultados.extend(resultados)
            time.sleep(1)
        except Exception as e:
            print(f"  [ERRO] Pesquisa '{query[:50]}': {e}")

    return todos_resultados


# ============================================================
# GERACAO DE CONTEUDO COM IA
# ============================================================

def gerar_conteudo_viral(resultados, categoria_config, api_key):
    """Gera conteudo viral usando IA baseado nos resultados da pesquisa."""
    if not api_key:
        return gerar_conteudo_fallback(resultados, categoria_config)

    prompt = f"""Voce e um editor de conteudo viral do Portal Ao Vivo, especializado em historias regionais do Alto Paranaiba e Triangulo Mineiro em Minas Gerais.

CATEGORIA: {categoria_config['nome']} {categoria_config['emoji']}

INSTRUCOES:
1. Escreva uma materia jornalistica viral com 3 a 4 paragrafos curtos
2. Use linguagem envolvente que gere curiosidade e compartilhamento
3. Inclua dados historicos e curiosidades reais
4. Comece com um gancho forte (pergunta, dado surpreendente ou frase impactante)
5. Termine com algo que faca o leitor querer saber mais
6. Use emojis com moderação no titulo
7. NAO invente informacoes - use apenas o que esta nos dados fornecidos
8. Escreva em portugues do Brasil, linguagem acessivel
9. Maximo de 800 caracteres no corpo do texto

DADOS DA PESQUISA:
{json.dumps(resultados[:5], ensure_ascii=False, indent=2)}

RETORNE APENAS UM JSON COM:
{{
  "titulo": "Titulo viral com ate 10 palavras e emoji",
  "corpo": "Texto da materia em 3-4 paragrafos",
  "hashtags": "hashtags relevantes separadas por espaco"
}}"""

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)

        modelos = ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-flash"]
        for modelo in modelos:
            try:
                model = genai.GenerativeModel(modelo)
                resp = model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.8,
                        max_output_tokens=1500,
                    ),
                )
                texto = resp.text.strip()

                # Tentar extrair JSON
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', texto, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    if "titulo" in data and "corpo" in data:
                        return data
            except Exception as e:
                print(f"  [IA] {modelo}: {e}")
                continue
    except Exception as e:
        print(f"  [IA] Erro geral: {e}")

    return gerar_conteudo_fallback(resultados, categoria_config)


def gerar_conteudo_fallback(resultados, categoria_config):
    """Gera conteudo sem IA usando os resultados da pesquisa."""
    if not resultados:
        return None

    primeiro = resultados[0]
    texto = primeiro.get("texto", "") or primeiro.get("titulo", "")

    # Limpar tags HTML
    texto = re.sub(r"<[^>]+>", "", texto)
    texto = re.sub(r"&#\d+;|&[a-zA-Z]+;", " ", texto)
    texto = re.sub(r"[\[\]]", "", texto)
    texto = re.sub(r"\s+", " ", texto).strip()

    if len(texto) < 60:
        texto = (
            f"Uma historia fascinante sobre {categoria_config['nome'].lower()} "
            "no Alto Paranaiba, em Minas Gerais. Essa regiao guarda segredos e "
            "historias que poucos conhecem."
        )

    # Montar titulo viral a partir do nome do artigo/categoria
    titulo_base = primeiro.get("titulo", "") or categoria_config["nome"]
    titulo_base = titulo_base.split(" - ")[0].strip()
    if len(titulo_base) > 65:
        titulo_base = titulo_base[:62].rstrip() + "..."

    titulo_viral = f"{categoria_config['emoji']} {titulo_base}"
    if len(titulo_viral) > 100:
        titulo_viral = titulo_viral[:97].rstrip() + "..."

    corpo = texto[:800]
    if len(texto) > 800:
        corpo += "..."

    tag_categoria = re.sub(r"[^a-zA-Z0-9]", "", categoria_config["nome"])
    hashtags = (
        "#PortalAoVivo #AltoParanaiba #TrianguloMineiro "
        "#MinasGerais #HistoriaRegional #VoceSabia "
        f"#{tag_categoria}"
    )

    return {
        "titulo": titulo_viral,
        "corpo": corpo,
        "hashtags": hashtags,
    }


# ============================================================
# PUBLICACAO
# ============================================================

def slugify(texto):
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9\s]", "", texto)
    texto = re.sub(r"\s+", "-", texto.strip())
    return texto[:60].strip("-")


def enfileirar_social(conteudo, categoria_config, imagem_rel):
    """Adiciona o post viral a fila de postagem em redes sociais."""
    pending_file = os.path.join(BASE_DIR, "data", "pending_social.json")

    existentes = []
    if os.path.exists(pending_file):
        with open(pending_file, "r", encoding="utf-8") as f:
            existentes = json.load(f)

    # Link unico baseado no slug das hashtags/titulo (sem URL externa)
    link = f"/viral/{slugify(conteudo['titulo'])}/"

    # Evitar duplicatas na fila
    for m in existentes:
        if m.get("link") == link:
            return

    existentes.append({
        "titulo": conteudo["titulo"],
        "link": link,
        "fonte": "Portal Ao Vivo - Pesquisa Viral",
        "tema": "Historia Regional",
        "resumo": conteudo["corpo"],
        "imagem": imagem_rel or "/assets/images/default.jpg",
    })

    os.makedirs(os.path.dirname(pending_file), exist_ok=True)
    with open(pending_file, "w", encoding="utf-8") as f:
        json.dump(existentes, f, ensure_ascii=False, indent=2)


def publicar_post_viral(conteudo, categoria_id, categoria_config, imagem_rel=None):
    """Publica um post viral como materia no _posts."""
    agora = datetime.now(BRT)
    data_str = agora.strftime("%Y-%m-%d")
    slug = slugify(conteudo["titulo"])
    arquivo = os.path.join(POSTS_DIR, f"{data_str}-viral-{slug}.md")

    if os.path.exists(arquivo):
        slug = slug + "-" + agora.strftime("%H%M")
        arquivo = os.path.join(POSTS_DIR, f"{data_str}-viral-{slug}.md")

    frontmatter = (
        "---\n"
        f'title: "{conteudo["titulo"].replace(chr(34), chr(39))}"\n'
        f'date: {agora.strftime("%Y-%m-%d %H:%M:%S -0300")}\n'
        f'image: /assets/images/default.jpg\n'
        f'tema: Historia Regional\n'
        f'fonte: "Portal Ao Vivo - Pesquisa Viral"\n'
        f'fonte_link: ""\n'
        f'resumo: "{conteudo["corpo"][:180].replace(chr(34), chr(39))}"\n'
        "---\n\n"
    )

    body = conteudo["corpo"] + "\n\n"
    if conteudo.get("hashtags"):
        body += conteudo["hashtags"] + "\n\n"
    body += "---\n"
    body += f"\n*Conteudo pesquisado e produzido automaticamente pelo Portal Ao Vivo - {categoria_config['nome']}*\n"

    conteudo_completo = frontmatter + body
    with open(arquivo, "w", encoding="utf-8") as f:
        f.write(conteudo_completo)

    print(f"[VIRAL] Publicado: {os.path.basename(arquivo)}")

    # Enfileirar para redes sociais
    try:
        enfileirar_social(conteudo, categoria_config, imagem_rel)
    except Exception as e:
        print(f"[VIRAL] Erro ao enfileirar social: {e}")

    return arquivo


def gerar_legenda_social(conteudo, categoria_config):
    """Gera legenda para redes sociais."""
    titulo = conteudo["titulo"]
    corpo = conteudo["corpo"][:400]
    hashtags = conteudo.get("hashtags", "")

    legenda = f"{titulo}\n\n{corpo}\n\n{hashtags}"
    return legenda


# ============================================================
# EXECUCAO PRINCIPAL
# ============================================================

def executar_pesquisa_viral(max_posts=2, categorias_especificas=None, um_por_dia=True):
    """Executa pesquisa e geracao de conteudo viral.
    
    Args:
        max_posts: Numero maximo de posts a gerar por execucao
        categorias_especificas: Lista de IDs de categorias para pesquisar.
                                Se None, usa todas as categorias.
        um_por_dia: Se True, publica no maximo 1 post viral por dia.
                    Usa `ultima_execucao` para garantir que um novo dia
                    gere apenas um novo conteudo.
    
    Returns:
        Lista de arquivos publicados
    """
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    topicos = load_viral_topics()
    publicados = []

    # ----- Controle de "1 por dia" -----
    if um_por_dia:
        hoje = datetime.now(BRT).strftime("%Y-%m-%d")
        ultima = (topicos.get("ultima_execucao") or "")[:10]
        if ultima == hoje:
            print(f"[VIRAL] Post de hoje ja foi gerado ({hoje}). Pulando pesquisa diaria.")
            return publicados
        # Forcar no maximo 1 post quando a flag esta ativa
        max_posts = min(max_posts, 1)

    cats = categorias_especificas or list(CATEGORIAS.keys())

    # Embaralhar categorias para variacao diaria
    import random
    random.shuffle(cats)

    print("\n" + "=" * 60)
    print("PESQUISA VIRAL - CONTEUDO HISTORICO E REGIONAL")
    print("=" * 60)

    posts_gerados = 0
    for cat_id in cats:
        if posts_gerados >= max_posts:
            break

        config = CATEGORIAS[cat_id]
        print(f"\n[CATEGORIA] {config['emoji']} {config['nome']}")

        # Pesquisar
        print(f"  Pesquisando {len(config['pesquisas'])} queries...")
        resultados = pesquisar_para_categoria(cat_id, config)

        if not resultados:
            print("  Nenhum resultado encontrado, pulando.")
            continue

        print(f"  {len(resultados)} resultados encontrados")

        # Gerar conteudo
        print("  Gerando conteudo viral...")
        conteudo = gerar_conteudo_viral(resultados, config, api_key)

        if not conteudo:
            print("  Nao foi possivel gerar conteudo, pulando.")
            continue

        # Verificar se titulo ja foi utilizado
        if ja_utilizou(topicos, conteudo["titulo"]):
            print(f"  Titulo ja utilizado, tentando proximo...")
            continue

        # Publicar
        try:
            arquivo = publicar_post_viral(conteudo, cat_id, config)
            registrar_utilizado(topicos, conteudo["titulo"], cat_id)
            publicados.append({
                "arquivo": arquivo,
                "titulo": conteudo["titulo"],
                "categoria": config["nome"],
                "legenda_social": gerar_legenda_social(conteudo, config),
            })
            posts_gerados += 1
            print(f"  OK - Post {posts_gerados}/{max_posts}")
        except Exception as e:
            print(f"  ERRO ao publicar: {e}")

        time.sleep(2)

    print(f"\n[VIRAL] Total: {posts_gerados} post(s) gerado(s)")
    return publicados


if __name__ == "__main__":
    import sys

    max_posts = 2
    cats = None

    if len(sys.argv) > 1:
        max_posts = int(sys.argv[1])
    if len(sys.argv) > 2:
        cats = sys.argv[2].split(",")

    resultados = executar_pesquisa_viral(max_posts=max_posts, categorias_especificas=cats)

    for r in resultados:
        print(f"\n{'='*60}")
        print(f"CATEGORIA: {r['categoria']}")
        print(f"TITULO: {r['titulo']}")
        print(f"ARQUIVO: {r['arquivo']}")
        print(f"LEGENDA:\n{r['legenda_social']}")
