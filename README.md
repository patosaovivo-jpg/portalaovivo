# Portal Ao Vivo

Portal de noticias automatico para **Patos de Minas, Alto Paranaiba, Triangulo Mineiro e regiao**.
A cada hora, o sistema coleta as noticias mais recentes de **17 fontes**, resume com IA (Google Gemini),
gera uma imagem ilustrativa (Pollinations.ai / Gemini / AI Horde) e publica automaticamente. Tambem monitora **hashtags do
Instagram** (busca por hashtag via API oficial).

## Como funciona

```
Coleta (RSS + sitemap + scraping + Instagram #hashtag) -> extrai texto -> resume com Gemini -> gera imagem -> publica no GitHub Pages
```

## Geracao de Imagens (fallback chain)

O sistema usa 3 geradores em cascata. Se um falhar, pula para o proximo:

1. **Gemini Nano Banana** (testa com chave atual; se sem free tier, falha rapido)
2. **Pollinations.ai** (gratuito, sem chave; modelos flux, sana, klein)
3. **AI Horde** (crowdsourced, gratuito, ultimo recurso; mais lento)

Grafite (img2img com foto original do Instagram) usa Pollinations com modelo `klein`.

## Estrutura

- `fonts.json` — cadastro das 17 fontes de noticias (tipo: rss | sitemap | scrape)
- `hashtags.json` — hashtags do Instagram monitoradas
- `themes.json` — temas e palavras-chave de curadoria + cidades monitoradas
- `scripts/` — pipeline Python (`collect.py`, `summarize.py`, `image.py`, `publish.py`, `instagram.py`)
- `.github/workflows/pipeline.yml` — roda a cada hora + build Jekyll + deploy Pages
- `_posts/` — materias publicadas (geradas automaticamente)
- `_data/ads.yml` — ativa/desativa os espacos de publicidade
- `ads_topo/`, `ads_lateral/`, `ads_materia/`, `ads_rodape/` — pastas com imagens de anuncios
- `assets/js/ads-imagens.json` — manifesto JSON com lista de imagens por pasta
- `assets/js/ads.js` — carrega o manifesto e sorteia imagem aleatoria
- `admin/` — painel antigo (hashtags, copiar/colar)
- `painel/` — **painel de controle** completo: fontes, banners, hashtags, temas
- `_layouts/` — layout do portal: home 2 colunas; materias 75% conteudo + 25% lateral
- `parts/` — fragmentos unicos do layout (header, banner-topo, footer, barra-lateral)
- `assets/js/layout.js` — carrega fragmentos em todas as paginas (semi-dinamico)
- `assets/js/slider.js` — carrossel automatico dos destaques
- `assets/css/style.scss` — tema preto/vermelho/branco

## Configurar (primeira vez)

1. No GitHub: Settings -> Secrets and variables -> Actions -> **New repository secret**
   - Nome: `GEMINI_API_KEY`
   - Valor: sua chave gratuita do Google AI Studio (https://aistudio.google.com/apikey)
2. Settings -> Pages -> Source: **GitHub Actions**
3. Em **Custom domain** preencha `portalaovivo.com.br` e ative **Enforce HTTPS**
4. No seu painel de DNS, crie os registros abaixo apontando para o GitHub Pages
5. Rode o workflow manualmente (aba Actions -> Publicacao Automatica -> Run workflow)

### DNS (portalaovivo.com.br)

| Tipo | Nome | Valor |
|------|------|-------|
| A | @ | 185.199.108.153 |
| A | @ | 185.199.109.153 |
| A | @ | 185.199.110.153 |
| A | @ | 185.199.111.153 |
| TXT | _github-pages-challenge-patosaovivo-jpg | (fornecido pelo GitHub) |

## Instagram (busca por hashtag)

O portal busca posts publicos marcados com as hashtags listadas em `hashtags.json` e publica resumos
das legendas (com a foto do post reestilizada como graffiti/street art).

### Configurar a API (uma vez)

1. Crie um app **Business** gratuito em https://developers.facebook.com
2. Conecte uma conta Instagram **Business ou Creator** sua ao app
3. No app, ative **Instagram** -> **API setup with Instagram login** e gere um token
4. Solicite a permissao **Instagram Public Content Access** (App Review)
5. Descubra seu **IG User ID**: `GET https://graph.instagram.com/{versao}/me?fields=user_id,username&access_token={TOKEN}`
6. No GitHub (Settings -> Secrets -> Actions), crie:
   - `INSTAGRAM_ACCESS_TOKEN` -> seu token de 60 dias
   - `INSTAGRAM_IG_USER_ID` -> o ID da sua conta

> **Token expira em 60 dias.** Quando vencer, gere um novo e atualize o secret.
> Enquanto o App Review nao for aprovado, o sistema **ignora o Instagram** e segue publicando normalmente.

### Gerenciar configuracoes pelo painel de controle

Acesse **`https://portalaovivo.com.br/painel/`**:

1. Entre com a senha definida em `painel/config.js`
2. Navegue entre as abas: **Fontes**, **Banners**, **Hashtags**, **Temas**
3. Edite as configuracoes desejadas
4. Clique em **"Copiar"** ou **"Gerar e copiar"**
5. Clique em **"Abrir no GitHub"** -> cole o conteudo -> commit
6. Va em Actions -> **Run workflow** para aplicar as mudancas

> O painel funciona 100% no navegador (sem token). Voce copia o JSON gerado e cola no GitHub manualmente.

## Publicidade

O site usa **pastas de anuncios** com sorteio de imagem aleatoria. O manifesto de imagens fica em
`assets/js/ads-imagens.json` (editavel pelo painel em `/painel/` na aba Banners).

Pastas:

| Pasta | Local | Formato sugerido |
|-------|-------|------------------|
| `ads_topo/` | Topo da pagina, acima dos destaques | 970x90 / 728x90 |
| `ads_lateral/` | Coluna lateral direita | 300x250 |
| `ads_materia/` | Dentro de cada materia | 728x90 |
| `ads_rodape/` | Fim de cada materia | 728x90 |

Para **anunciar**: coloque a imagem na pasta e adicione o nome no manifesto JSON (pelo painel ou manualmente).

Para **ativar/desativar** um espaco, use `ativo: true/false` em `_data/ads.yml`.
