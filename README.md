# Portal Ao Vivo

Portal de notícias automático para **Patos de Minas, Alto Paranaíba, Triângulo Mineiro e região**.
A cada hora, o sistema coleta as notícias mais recentes de **17 fontes**, resume com IA (Google Gemini),
gera uma imagem ilustrativa (Pollinations.ai) e publica automaticamente.

## Como funciona

```
Coleta (RSS + sitemap + scraping) → extrai texto → resume com Gemini → gera imagem → publica no GitHub Pages
```

## Estrutura

- `fonts.json` — cadastro das 17 fontes de notícias (tipo: rss | sitemap | scrape)
- `themes.json` — temas e palavras-chave de curadoria + cidades monitoradas
- `scripts/` — pipeline Python (`collect.py`, `summarize.py`, `image.py`, `publish.py`)
- `.github/workflows/pipeline.yml` — roda a cada hora + build Jekyll + deploy Pages
- `_posts/` — matérias publicadas (geradas automaticamente)
- `_data/ads.yml` — **3 espaços de publicidade** do site

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

## Publicidade

No arquivo `_data/ads.yml` há 3 espaços prontos (topo, lateral e rodapé). Basta colar o código
do seu anunciante no campo `codigo` e definir `ativo: true`.