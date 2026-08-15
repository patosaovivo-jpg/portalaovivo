# Portal Ao Vivo

Portal de notícias automático para **Patos de Minas, Alto Paranaíba, Triângulo Mineiro e região**.
A cada hora, o sistema coleta as notícias mais recentes de **17 fontes**, resume com IA (Google Gemini),
gera uma imagem ilustrativa (Pollinations.ai) e publica automaticamente. Também monitora **hashtags do
Instagram** (busca por hashtag via API oficial).

## Como funciona

```
Coleta (RSS + sitemap + scraping + Instagram #hashtag) → extrai texto → resume com Gemini → gera imagem → publica no GitHub Pages
```

## Estrutura

- `fonts.json` — cadastro das 17 fontes de notícias (tipo: rss | sitemap | scrape)
- `hashtags.json` — hashtags do Instagram monitoradas (editável pelo painel admin)
- `themes.json` — temas e palavras-chave de curadoria + cidades monitoradas
- `scripts/` — pipeline Python (`collect.py`, `summarize.py`, `image.py`, `publish.py`, `instagram.py`)
- `.github/workflows/pipeline.yml` — roda a cada hora + build Jekyll + deploy Pages
- `_posts/` — matérias publicadas (geradas automaticamente)
- `_data/ads.yml` — **4 espaços de publicidade** (topo, lateral, rodapé e esquerda)
- `admin/` — **painel de admin** para gerenciar as hashtags do Instagram
- `_layouts/` — layout estilo portal: logo, menu, slider com as 5 últimas notícias e 3 colunas
- `assets/js/slider.js` — carrossel automático dos destaques
- `assets/css/style.scss` — tema preto/vermelho/branco

## Configurar (primeira vez)

1. No GitHub: Settings → Secrets and variables → Actions → **New repository secret**
   - Nome: `GEMINI_API_KEY`
   - Valor: sua chave gratuita do Google AI Studio (https://aistudio.google.com/apikey)
2. Settings → Pages → Source: **GitHub Actions**
3. Em **Custom domain** preencha `portalaovivo.com.br` e ative **Enforce HTTPS**
4. No seu painel de DNS, crie os registros abaixo apontando para o GitHub Pages
5. Rode o workflow manualmente (aba Actions → Publicacao Automatica → Run workflow) para publicar a primeira leva

### DNS (portalaovivo.com.br)

| Tipo | Nome | Valor |
|------|------|-------|
| A | @ | 185.199.108.153 |
| A | @ | 185.199.109.153 |
| A | @ | 185.199.110.153 |
| A | @ | 185.199.111.153 |
| CNAME | www | portalaovivo.com.br |

## Instagram (busca por hashtag)

O portal busca posts públicos marcados com as hashtags listadas em `hashtags.json` e publica resumos
das legendas (com a foto do post reestilizada como graffiti/street art).

### Configurar a API (uma vez)

1. Crie um app **Business** gratuito em https://developers.facebook.com
2. Conecte uma conta Instagram **Business ou Creator** sua ao app
3. No app, ative **Instagram** → **API setup with Instagram login** e gere um token
4. Solicite a permissão **Instagram Public Content Access** (App Review) — necessária para buscar hashtags
5. Descubra seu **IG User ID**: `GET https://graph.instagram.com/{versao}/me?fields=user_id,username&access_token={TOKEN}`
6. No GitHub (Settings → Secrets → Actions), crie:
   - `INSTAGRAM_ACCESS_TOKEN` → seu token de 60 dias
   - `INSTAGRAM_IG_USER_ID` → o ID da sua conta

> **Token expira em 60 dias.** Quando vencer, gere um novo e atualize o secret.
> Enquanto o App Review não for aprovado, o sistema **ignora o Instagram** e segue publicando normalmente.

### Gerenciar hashtags pelo painel admin

Acesse **`https://portalaovivo.com.br/admin/`**:

1. Entre com a senha definida em `admin/config.js`
2. Edite a lista de hashtags (uma por linha)
3. Clique em **"Gerar JSON e copiar"**
4. Clique em **"Abrir hashtags.json no GitHub"** → cole o conteúdo → commit

> A senha fica no arquivo `admin/config.js` (público). Use uma senha simples, pois a lista de hashtags
> também é pública — ela serve apenas como "porta de entrada" do painel.

## Publicidade

No arquivo `_data/ads.yml` há **4 espaços prontos**:

| Espaço | Local | Formato sugerido |
|--------|-------|------------------|
| `topo` | Topo da página, acima dos destaques | 970x90 / 728x90 |
| `esquerda` | Coluna fixa à esquerda | 160x600 / 300x250 |
| `lateral` | Coluna lateral direita | 300x250 |
| `rodape` | Fim de cada matéria | 728x90 / 300x250 |

Basta colar o código do seu anunciante no campo `codigo` e definir `ativo: true`.
Enquanto estiverem inativos, o site exibe um **placeholder tracejado** no lugar.