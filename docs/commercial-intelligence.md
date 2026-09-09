# Inteligência Editorial + Comercial

Camada adicionada ao pipeline automático do Portal Ao Vivo. Complementa o fluxo
existente (coleta -> resumo IA -> imagem -> publicação -> redes sociais) sem
substituí-lo: se o Gemini não estiver disponível, tudo funciona via regras locais.

## Escopo

- 3 scores por notícia (editorial, comercial, Instagram).
- Detecção de eventos + registro de leads comerciais.
- Conteúdo social estruturado (Reel/Stories/Carousel) + CTA comercial.
- Priorização das matérias para o Instagram.
- Frontmatter expandido nas matérias publicadas.

## Arquitetura

```
config/commercial_rules.json     -> triggers, alvos, parágrafos comerciais, lead
config/social_rules.json         -> pesos de priorização, CTAs, hashtags
config/prospecting_rules.json    -> janelas, clientes, serviços, rascunhos, pesos
scripts/analyze_article.py       -> análise (IA via Gemini ou regras locais)
scripts/event_detector.py        -> detecção de evento + leads
scripts/commercial_radar.py      -> TOP OPORTUNIDADES (ranking por lead_score)
scripts/commercial_prospecting.py-> prospecção inteligente (janela/prioridade/rascunho)
scripts/summarize.py             -> resumo com parágrafo comercial opcional
scripts/publish.py               -> frontmatter expandido (compatível Jekyll)
scripts/social_poster.py         -> ordenação por prioridade + legendas estruturadas
scripts/pipeline.py              -> integração das etapas 1/8 a 8/8
data/commercial_leads.json       -> oportunidades comerciais consolidadas
scripts/test_commercial_intelligence.py -> testes obrigatórios (7 casos)
scripts/test_prospecting.py      -> testes obrigatórios de prospecção (10 cenários)
```

## Scores (0 a 10)

| Score | Significado |
|-------|-------------|
| editorial_score | Valor jornalístico/regional da notícia |
| commercial_score | Potencial comercial (0-4 neutro, 5-6 editorial, 7-8 discreto, 9-10 CTA direto) |
| instagram_score  | Potencial de engajamento/formatos (Reel, Stories, Carousel) |

Regra principal: `NOTÍCIA > PROPAGANDA`. Quanto maior o score comercial, mais
suave e contextual é a menção.

- `commercial_score >= 7`  -> permite CTA comercial no conteúdo social.
- `commercial_score >= 8`  -> gera conteúdo social especial (Reel etc.).
- Valores de fallback se a análise falhar: editorial 5, comercial 0, instagram 5.

## Radar de oportunidades comerciais (lead_score)

Cada lead recebe um `lead_score` (0 a 10, 1 casa decimal) que pondera:

| Fator | Peso | Como mede |
|-------|------|-----------|
| commercial_score | 0.30 | /10 |
| proximidade | 0.25 | janela ideal 1-15 dias (60d < 15d) |
| porte | 0.15 | público esperado / porte |
| tipo do evento | 0.08 | campeonato, festival, feira, congresso... |
| cidade | 0.05 | cidade monitorada da região |
| recorrência | 0.05 | evento tradicional/anual (Festa do Café, jubileu) |
| patrocinadores | 0.05 | presença de patrocinadores/marcas |
| organizador | 0.02 | organizador identificável |
| transmissão | 0.03 | potencial de transmissão |
| conteúdo | 0.02 | potencial Instagram/editorial |

Exemplo prático (mesmo score comercial):
- evento em 60 dias -> lead_score 8.1
- evento em 15 dias -> lead_score 8.8 (prospecção primeiro)

`scripts/commercial_radar.py` imprime o ranking no log do pipeline e em um
passo dedicado do GitHub Actions:

```
 1. Festa do Café [Patrocínio] - 8.8 (em 15d, novo)
 2. Leilão agropecuário [Vazante] - 8.4 (em 7d, contatado)
 ...
```

## Prospecção inteligente (janela e prioridade de contato)

`scripts/commercial_prospecting.py` responde a duas perguntas por lead: **QUEM**
contratar e **QUANDO** prospectar. É um enriquecimento **acoplado ao lead** (não
depende de terceiros) e é **só rascunho: NUNCA envia mensagem**.

### Preenchimento automático (enriquecimento)

Toda nova notícia registrada passa por `enriquecer_lead()` (chamado dentro de
`event_detector.registrar_lead()`):

- cliente provável (`potential_client_type`), serviços recomendados
  (`recommended_services`) e dor (`commercial_need`) via `client_types`/`services`
  de `config/prospecting_rules.json`.
- janela de contato (`contact_window` / `recommended_contact_window`) pela data
  do evento.
- prioridade de prospecção (`prospecting_priority`, na escada
  `monitorar < baixo < médio < alto < urgente < muito_urgente`).
- organizador/tipo/source só da notícia (nunca inventa; `organizer_url` fica
  vazio sem evidência).
- `sponsors_detected`/`sponsors_evidence` só por evidência textual.
- `prospecting_score` (0-10, separado do `lead_score`): pesos em
  `prospecting_weights` (lead_score .30, proximidade .22, organizador .10,
  cliente .10, porte .08, recorrência .06, patrocinadores .06, cidade .05,
  serviços .03).
- quando `prospecting_priority` aponta contato E `lead_score >= 8`, gera um
  `suggested_outreach` (rascunho de abordagem) — nunca envia.

### Janelas por tipo (config/prospecting_rules.json -> windows)

| Grupo | monitoring | prospecting_start | priority_days | urgent_high | urgent | too_late |
|-------|-----------:|------------------:|--------------:|------------:|-------:|---------:|
| default | 90 | 60 | 30 | 20 | 7 | 2 |
| festival | 90 | 90 | 45 | 20 | 7 | 2 |
| sports | 90 | 45 | 30 | 20 | 7 | 2 |
| corporate | 90 | 60 | 40 | 20 | 7 | 2 |
| education | 90 | 50 | 25 | 20 | 7 | 2 |
| religious | 90 | 75 | 40 | 20 | 7 | 2 |

Classificação por dias até o evento: evento passado -> não prospectar;
`dias >= monitoring` -> monitorar; `dias <= too_late` -> muito tarde;
`dias <= urgent` -> urgente; `dias <= urgent_high` -> urgente;
`dias <= priority_days` -> prioridade/urgente; `dias <= prospecting_start` ->
prioridade; senão -> prospectar. Evento sem data -> monitorar; evento hoje ->
urgente/muito_urgente.

Boost de prioridade (+1 degrau) quando o evento é **recorrente** (tradicional/
anual/edição) ou tem histórico nos leads (`previous_event_detected`) ou
`lead_score >= 9`.

### TOP PROSPECÇÃO

`top_prospeccao()` / `print_painel_prospeccao()` ordenam pelos critérios:
`prospecting_score` (desc) e depois a escada de prioridade. Exclui eventos
passados. O pipeline imprime o painel ao final e o GitHub Actions roda um passo
dedicado:

```
Prioridade: URGENTE | Score: 8.5 | Festa do Café [Patrocínio] - em 12 dias
Prioridade: ALTO   | Score: 7.6 | Campeonato Regional [Patos de Minas] - em 30 dias
```

### Sem conflito com o status

`prospecting_priority` é um campo derivado, recalculado a cada enriquecimento;
**não substitui** o `status` do ciclo de vida (novo -> monitorando -> contatado
-> proposta_enviada -> fechado | perdido). Re-registrar a mesma notícia preserva
status/observações/histórico e atualiza prioridade, janela e rascunho.

## Ciclo de vida do lead (simples, sem CRM)

Arquivo `data/commercial_leads.json` com o schema:

```json
{
  "lead_score": 8.8,
  "priority": "FORTE",
  "event_name": "Festa do Café",
  "event_type": "festa",
  "city": "Patrocínio",
  "event_date": "2026-09-25",
  "days_until_event": 15,
  "event_timing": "em_breve",
  "organizer": "Prefeitura de Patrocínio",
  "estimated_audience": 10000,
  "porte": "grande",
  "recurring": true,
  "edition": 10,
  "sponsors": [],
  "sponsors_count": 0,
  "source": "Patrocinio Online",
  "source_url": "https://...",
  "commercial_angle": "alcance",
  "suggested_services": ["transmissao ao vivo"],
  "target_customer": ["organizador de eventos"],
  "commercial_score": 8,
  "instagram_score": 8,
  "transmission_opportunity": 9,
  "status": "novo",
  "detected_at": "...",
  "updated_at": "...",
  "event_id": "...",
  "lead_id": "...",
  "recurring_event": true,
  "recurrence_pattern": "anual",
  "previous_event_detected": true,
  "organizer_type": "Prefeitura",
  "organizer_source": "Citado na notícia de ...",
  "organizer_url": "",
  "sponsors_detected": true,
  "sponsors_evidence": ["..."] ,
  "potential_client_type": ["organizador de eventos"],
  "recommended_services": ["transmissao ao vivo"],
  "commercial_need": "...",
  "contact_window": "prospectar_prioridade",
  "recommended_contact_window": "20 a 45 dias antes",
  "prospecting_priority": "urgente",
  "contact_reason": "...",
  "suggested_outreach": "...",
  "contact_history": [],
  "notes": "",
  "prospecting_score": 8.5,
  "sources": []
}
```

Os campos adicionados vêm da prospecção inteligente (ver seção acima). Para
`contact_reason`/`suggested_outreach` serem (re)gerados automaticamente, o
lead precisa estar ativo e com `lead_score >= 8`; prioridades antigas são
atualizadas a cada novo registro da mesma notícia.

`status` segue o ciclo: `novo` (inicial) -> `monitorando` -> `contatado` ->
`proposta_enviada` -> `fechado` | `perdido`. O pipeline NUNCA regressa o status:
só cria/atualiza `novo`. Tipos de evento ainda não detectados foram adicionados:
corrida/maratona, leilão/agropecuária, formatura, festa religiosa, conferência
e inauguração.

## Detecção de eventos

`event_detector.detectar_evento()` extrai a partir da notícia, sem inventar dados:

- nome do evento (palavras-chave + corte em conectivos, ex.: "Campeonato Regional")
- cidade regional (lista em `themes.json -> cidades`)
- data (dia/mês/texto: "15 de outubro", "em outubro", "daqui a 5 dias", "domingo")
- organizador (Prefeitura, Câmara, Secretaria, Liga, Clube)
- tipo/porte/público esperado/patrocinadores/redes sociais

## Leads comerciais

`event_detector.registrar_lead()` grava em `data/commercial_leads.json` quando:

1. `event_related == true` E `commercial_score >= lead.min_score` (padrão 5).
2. Chave única: `nome do evento | cidade | data` (sem duplicação).
3. Fontes múltiplas consolidam os campos vazios do mesmo evento.

Cada lead guarda: organizador, tipo, porte, público esperado, score, ângulo,
serviços sugeridos, fonte e prioridade (BAIXA/MEDIA/FORTE/MUITO FORTE).

## Serviços e ângulos comerciais

Definidos em `config/commercial_rules.json`:

- `target_mapping`: organizadores-alvo por palavra-chave.
- `triggers`: grande evento, campeonato, patrocínio, streaming etc. (inclui
  corrida, agropecuária/leilão, formatura, evento religioso, conferência,
  inauguração).
- `commercial_paragraphs`: parágrafo comercial por ângulo e nível (5-6 / 7-8 / 9-10).
  Ângulos: alcance, audiencia, esporte, visibilidade, empresarial.
- `lead.min_score`: mínimo de commercial_score para virar lead.

## Conteúdo social

`analyze_article.gerar_conteudo_social()` produz (IA ou template):

- `reel`      -> hook, script, caption, cta
- `stories`   -> lista de frases para stories
- `carousel`  -> título + slides

CTA e hashtags por ângulo vêm de `config/social_rules.json`.

## Priorização do Instagram

`social_poster.calcular_priority_score()` pondera (pesos em `social_rules.json`):

```
views (+1.0 até o teto)  +  instagram_score (x2)  +  commercial (x2)
+ regional (x1.5)        +  evento (x1.5)
```

`postar_materias()` ordena a fila por prioridade antes de postar.

## Frontmatter

`publish.py` adiciona (sem quebrar os campos atuais):

```yaml
categoria: eventos
editorial_score: 7
commercial_score: 8
instagram_score: 7
event_related: true
generate_reel: true
generate_cta: true
event_type: festival
event_types:
  - festival
commercial_angle: alcance
target_customer: ...
suggested_service: ...
reason: ...
instagram_hook: ...
instagram_script: ...
instagram_caption: ...
```

## Como ajustar

Edite apenas os JSONs de `config/`; não precisa mexer no código:

- Aumentar peso do Instagram na fila: `config/social_rules.json -> priorizacao.weights.instagram`.
- Novos gatilhos comerciais: `config/commercial_rules.json -> triggers`.
- Novas cidades: `themes.json -> cidades`.
- Parágrafos/CTA/hashtags por ângulo: `config/commercial_rules.json` e `config/social_rules.json`.
- Janelas de prospecção por tipo: `config/prospecting_rules.json -> windows`.
- Clientes/serviços/dores e rascunhos de abordagem: `config/prospecting_rules.json -> client_types/services/outreach_templates`.
- Pesos do `prospecting_score`: `config/prospecting_rules.json -> prospecting_weights`.

## Testes

```bash
python scripts/test_commercial_intelligence.py    # sem API: usa regras locais
python scripts/test_prospecting.py                # ETAPA 3: prospecção (10 cenários)
```

Cobre: festival municipal futuro, final de campeonato regional, lançamento de
câmera profissional, festival com público recorde, reunião administrativa,
congresso empresarial regional, notícia política sem evento, classificação
temporal (passado/em breve/futuro), ranking por proximidade (15 dias > 60 dias),
ciclo de vida do status, radar TOP 10, conteúdo social, frontmatter e imports
do pipeline antigo.

`test_prospecting.py` cobre os 10 cenários de prospecção (festival em 15 dias,
campeonato em 30, congresso em 90, evento passado, sem data, evento recorrente,
com/sem patrocinadores, empresarial e esportivo) e valida: **nunca envia**
mensagem (só rascunho `suggested_outreach`), **nunca inventa** contato
(organizador vem da notícia, `organizer_url` vazio), a prioridade de prospecção
**não substitui** o status, o TOP PROSPECÇÃO é ordenado por `prospecting_score`
e o painel imprime sem quebrar.