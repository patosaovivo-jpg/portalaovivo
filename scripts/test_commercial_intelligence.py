# -*- coding: utf-8 -*-
"""
TESTES OBRIGATÓRIOS da camada de INTELIGÊNCIA EDITORIAL + COMERCIAL
e do RADAR DE OPORTUNIDADES COMERCIAIS.

Como rodar (sem API, usa regras locais - fallback):
    python scripts/test_commercial_intelligence.py

Valida:
  - os 7 testes obrigatórios de análise (scores, flags, leads, CTA)
  - detecção de evento (nome, cidade, data, organizador, patrocinadores)
  - classificação temporal (passado/hoje/em_breve/futuro) + days_until
  - lead_score e priorização (evento em 15 dias > evento em 60 dias)
  - ciclo de vida simples do status (novo -> monitorando -> ...)
  - radar comercial TOP N
  - conteúdo social (Reel/Stories/Carousel) via template
  - frontmatter expandido sem quebrar o atual
  - imports / pipeline antigo continua funcionando
"""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import analyze_article
import event_detector
import publish
import summarize

API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

LEADS_FILE = event_detector.LEADS_FILE
LEADS_BACKUP = None

TESTES = [
    {
        "id": "TESTE 1 - Festival municipal futuro",
        "titulo": "Prefeitura anuncia grande festival para outubro com expectativa de 30 mil pessoas",
        "texto": ("A Prefeitura anunciou um grande festival para outubro no parque de exposições. "
                  "A expectativa é reunir 30 mil pessoas durante os quatro dias de programação, "
                  "com shows, praça de alimentação e atrações culturais."),
        "esperado": {"event_related": True, "comercial_alto": True,
                      "lead": True, "servico": "transmissao ao vivo",
                      "timing": "futuro"},
    },
    {
        "id": "TESTE 2 - Final do campeonato regional",
        "titulo": "Final do Campeonato Regional acontece domingo",
        "texto": ("A final do Campeonato Regional da Liga Patense acontece neste domingo no estádio "
                  "municipal. Os dois melhores times da temporada decidem o título em jogo único, "
                  "com grande expectativa da torcida."),
        "esperado": {"sports_related": True, "comercial_alto": True,
                      "instagram_alto": True, "servico": "transmissao esportiva",
                      "timing": "em_breve"},
    },
    {
        "id": "TESTE 3 - Lançamento de câmera profissional",
        "titulo": "Empresa lança novo modelo de câmera profissional",
        "texto": ("Uma fabricante de equipamentos anunciou o lançamento de um novo modelo de câmera "
                  "profissional com sensor de alta resolução e gravação em 8K. A novidade chega ao "
                  "mercado no próximo trimestre."),
        "esperado": {"technology_related": True, "comercial_baixo_medio": True,
                      "sem_cta_agressivo": True},
    },
    {
        "id": "TESTE 4 - Festival com público recorde",
        "titulo": "Festival recebeu público recorde de 100 mil pessoas",
        "texto": ("O festival recebeu um público recorde de 100 mil pessoas ao longo dos três dias. "
                  "A organização comemorou a marca histórica e confirmou a próxima edição."),
        "esperado": {"comercial_alto": True, "instagram_alto": True,
                      "angle": "alcance", "timing": "passado"},
    },
    {
        "id": "TESTE 5 - Reunião administrativa",
        "titulo": "Prefeitura anuncia reunião administrativa",
        "texto": ("A prefeitura convocou uma reunião administrativa com as secretarias municipais "
                  "para tratar de planejamento orçamentário e metas do segundo semestre."),
        "esperado": {"editorial_ok": True, "comercial_baixo": True, "sem_cta": True},
    },
    {
        "id": "TESTE 6 - Congresso empresarial regional",
        "titulo": "Empresa anuncia congresso para 2 mil participantes em Patos de Minas",
        "texto": ("Uma empresa do setor industrial anunciou um congresso para 2 mil participantes "
                  "em Patos de Minas, com palestras, workshops e rodadas de negócios. O evento terá "
                  "15 patrocinadores confirmados."),
        "esperado": {"event_related": True, "lead": True},
    },
    {
        "id": "TESTE 7 - Notícia política sem eventos",
        "titulo": "Governo de Minas anuncia novos repasses para a saúde",
        "texto": ("O governo estadual anunciou novos repasses para a saúde dos municípios do Alto "
                  "Paranaíba. Os recursos serão destinados a hospitais regionais."),
        "esperado": {"comercial_baixo": True, "sem_cta": True},
    },
]

CENARIOS_RANKING = [
    ("CENÁRIO 15 DIAS", "Festa do Café",
     "A Festa do Café daqui a 15 dias, em Patrocinio, deve reunir 10 mil pessoas. "
     "A prefeitura e a associação organizam o evento tradicional no centro da cidade."),
    ("CENÁRIO 60 DIAS", "Festa do Café",
     "A Festa do Café daqui a 60 dias, em Patrocinio, deve reunir 10 mil pessoas. "
     "A prefeitura e a associação organizam o evento tradicional no centro da cidade."),
]


def checar(esperado, analise, resultado, evento):
    erros = []
    if esperado.get("event_related") and not analise["event_related"]:
        erros.append("esperava event_related=True")
    if esperado.get("sports_related") and not analise["sports_related"]:
        erros.append("esperava sports_related=True")
    if esperado.get("technology_related") and not analise["technology_related"]:
        erros.append("esperava technology_related=True")
    if esperado.get("comercial_alto") and not analise["commercial_score"] >= 8:
        erros.append(f"commercial_score baixo ({analise['commercial_score']})")
    if esperado.get("comercial_baixo") and not analise["commercial_score"] <= 2:
        erros.append(f"commercial_score alto ({analise['commercial_score']})")
    if esperado.get("comercial_baixo_medio") and not analise["commercial_score"] <= 4:
        erros.append(f"commercial_score {analise['commercial_score']}")
    if esperado.get("instagram_alto") and not (analise["instagram_score"] >= 6 or analise["commercial_score"] >= 8):
        erros.append(f"instagram_score baixo ({analise['instagram_score']})")
    if esperado.get("sem_cta") and analise["generate_cta"]:
        erros.append("gerou CTA quando nao deveria")
    if esperado.get("sem_cta_agressivo") and analise["generate_cta"]:
        erros.append("gerou CTA agressivo em noticia comercial baixa")
    if esperado.get("lead") and not (resultado.get("status") in ("novo", "atualizado")):
        erros.append("lead nao registrado")
    if esperado.get("servico"):
        servicos = " ".join(analise["suggested_service"]).lower()
        espera_norm = esperado["servico"].lower()
        if espera_norm not in servicos:
            erros.append(f"servico '{esperado['servico']}' ausente -> {analise['suggested_service']}")
    if esperado.get("angle") and analise["commercial_angle"] != esperado["angle"]:
        erros.append(f"angulo {analise['commercial_angle']} != {esperado['angle']}")
    if esperado.get("editorial_ok") and not analise["editorial_score"] >= 5:
        erros.append("editorial baixo")
    if esperado.get("timing") and evento.get("event_timing") != esperado["timing"]:
        erros.append(f"timing {evento.get('event_timing')} != {esperado['timing']}")
    return erros


def registrar_teste(item, rules, themes):
    analise = analyze_article.analisar_noticia(item, api_key=API_KEY,
                                                themes=themes, rules=rules)
    evento = event_detector.detectar_evento(item, analise, themes, rules)
    res = event_detector.registrar_lead(item, analise, evento, rules, themes)
    return analise, evento, res


def testar_estado_salvo():
    # snapshot para restaurar ao final (mantem o repo limpo)
    global LEADS_BACKUP
    if os.path.exists(LEADS_FILE):
        LEADS_BACKUP = open(LEADS_FILE, "r", encoding="utf-8").read()


def restaurar_estado():
    if LEADS_BACKUP is None:
        if os.path.exists(LEADS_FILE):
            os.remove(LEADS_FILE)
        return
    with open(LEADS_FILE, "w", encoding="utf-8") as f:
        f.write(LEADS_BACKUP)


def main():
    rules = analyze_article.load_commercial_rules()
    themes = analyze_article.load_themes()
    print("=" * 70)
    print("ANÁLISE EDITORIAL + COMERCIAL - SIMULAÇÃO (7 casos)")
    print("=" * 70)

    testar_estado_salvo()
    resultados = {"ok": 0, "falhas": 0}

    for teste in TESTES:
        item = {"titulo": teste["titulo"], "texto": teste["texto"],
                "tema": "Geral", "fonte": "Teste", "link": f"https://teste/{teste['id']}"}
        print(f"\n>>> {teste['id']}")
        print(f"    {teste['titulo'][:70]}")

        analise, evento, res = registrar_teste(item, rules, themes)
        print(f"    editorial={analise['editorial_score']}  "
              f"comercial={analise['commercial_score']}  "
              f"instagram={analise['instagram_score']}  "
              f"categoria={analise['category']}  "
              f"angle={analise['commercial_angle'] or '-'}")
        print(f"    flags: event={analise['event_related']} sports={analise['sports_related']} "
              f"tech={analise['technology_related']} regional={analise['regional']}")
        print(f"    servicos: {analise['suggested_service']}")
        print(f"    cta={analise['generate_cta']} reel={analise['generate_reel']}")
        if res.get("lead"):
            l = res["lead"]
            print(f"    lead: {res['status']} | score={l.get('lead_score')} | "
                  f"{l.get('event_timing')} | days={l.get('days_until_event')} | "
                  f"status={l.get('status')}")
        else:
            print(f"    lead: {res['status']}")

        erros = checar(teste["esperado"], analise, res, evento)
        if erros:
            resultados["falhas"] += 1
            print(f"    [FALHA] {'; '.join(erros)}")
        else:
            resultados["ok"] += 1
            print(f"    [OK]")

    # ---- RANKING: 15 dias vs 60 dias (mesmo commercial_score) ----
    print("\n" + "=" * 70)
    print("RADAR - PROXIMIDADE: EVENTO EM 15 DIAS DEVE VENCER 60 DIAS")
    print("=" * 70)
    scores = {}
    for nome_cenario, nome_evento, texto in CENARIOS_RANKING:
        item = {"titulo": f"{nome_evento} acontece em Patrocinio",
                "texto": texto, "tema": "Geral",
                "fonte": "Teste", "link": f"https://teste/{nome_cenario}"}
        analise, evento, res = registrar_teste(item, rules, themes)
        lead = res.get("lead") or {}
        scores[nome_cenario] = {
            "score": float(lead.get("lead_score") or 0),
            "days": lead.get("days_until_event"),
            "timing": lead.get("event_timing"),
            "comercial": analise["commercial_score"],
            "name": lead.get("event_name"),
        }
        print(f"    {nome_cenario}: lead_score={scores[nome_cenario]['score']} | "
              f"days={scores[nome_cenario]['days']} | "
              f"timing={scores[nome_cenario]['timing']}")

    s15 = scores.get("CENÁRIO 15 DIAS", {})
    s60 = scores.get("CENÁRIO 60 DIAS", {})
    if s15.get("days") == 15 and s60.get("days") == 60 and s15["score"] > s60["score"]:
        resultados["ok"] += 1
        print(f"    [OK] 15 dias ({s15['score']}) > 60 dias ({s60['score']})")
    else:
        resultados["falhas"] += 1
        print(f"    [FALHA] ranking de proximidade: {s15} vs {s60}")

    # ---- CICLO DE VIDA DO STATUS (simples, nao-CRM) ----
    print("\n" + "=" * 70)
    print("CICLO DE VIDA DO STATUS (novo -> monitorando -> contatado)")
    print("=" * 70)
    item = {"titulo": "Leilão agropecuário da próxima semana em Vazante",
            "texto": ("O Leilão agropecuário daqui a 7 dias em Vazante espera 5 mil pessoas "
                      "e 10 patrocinadores. A associação rural é a organizadora."),
            "tema": "Geral", "fonte": "Teste", "link": "https://teste/leilao"}
    _, _, res = registrar_teste(item, rules, themes)
    lead = res.get("lead")
    if not lead:
        resultados["falhas"] += 1
        print("    [FALHA] leilao agropecuario nao gerou lead")
    else:
        leads = event_detector.load_leads()
        for k, v in leads.items():
            if (v.get("event_name") == lead.get("event_name")
                    and v.get("city") == lead.get("city")
                    and v.get("event_date") == lead.get("event_date")):
                v["status"] = "contatado"
        event_detector.save_leads(leads)
        _, _, res2 = registrar_teste(item, rules, themes)
        manter = (res2.get("lead") or {}).get("status")
        if manter == "contatado":
            resultados["ok"] += 1
            print("    [OK] status preservado apos re-registro:", manter)
        else:
            resultados["falhas"] += 1
            print(f"    [FALHA] status regrediu: {manter}")

    # ---- CONTEÚDO SOCIAL + FRONTMATTER + RESUMO (valida fluxo antigo) ----
    print("\n" + "=" * 70)
    print("CONTEÚDO SOCIAL, FRONTMATTER E RESUMO - FLUXO COMPATÍVEL")
    print("=" * 70)
    item4 = {"titulo": "Festival recebeu público recorde de 100 mil pessoas",
             "texto": "O festival recebeu público recorde de 100 mil pessoas.",
             "tema": "Geral"}
    analise4 = analyze_article.analisar_noticia(item4, themes=themes, rules=rules)
    social = analyze_article.gerar_conteudo_social(item4, analise4, "Resumo do festival.", api_key="")
    assert social.get("reel") and social.get("stories") and social.get("carousel"), "conteudo social incompleto"

    with tempfile.TemporaryDirectory() as tmp:
        publish.POSTS_DIR = tmp
        item_pub = dict(item4)
        item_pub.update({"analise": analise4, "conteudo_social": social,
                         "event_name": None, "fonte": "Teste", "link": "https://teste/x"})
        arquivo = publish.gerar_markdown(item_pub, "Texto da matéria.", "/assets/images/x.jpg",
                                         sem_fonte=False, analise=analise4)
        conteudo = open(arquivo, "r", encoding="utf-8").read()
        assert "categoria: \"eventos\"" in conteudo and "commercial_score:" in conteudo
        print("    [OK] frontmatter expandido (diminuto, checado acima)")

    resumo = summarize.resumir_texto_com_analise(TESTES[0]["texto"], analise4, api_key="")
    assert resumo and len(resumo) > 100
    print("    [OK] resumo comercial fallback")

    # ---- RADAR TOP ----
    print("\n" + "=" * 70)
    print("RADAR COMERCIAL - TOP 10 (imprime tambem no GitHub Actions)")
    print("=" * 70)
    topo = event_detector.print_top_leads(limite=10)
    if topo and topo[0].get("lead_score") is not None:
        resultados["ok"] += 1
        print(f"    [OK] radar ordenado, top: {topo[0].get('event_name')} "
              f"{topo[0].get('lead_score')}")
    else:
        resultados["falhas"] += 1
        print("    [FALHA] radar sem leads ou sem lead_score")

    # ---- PIPELINE ANTIGO CONTINUA IMPORTANDO ----
    print("\n" + "=" * 70)
    print("IMPORTS DO PIPELINE ANTIGO")
    print("=" * 70)
    import collect, image, social_poster, commercial_radar  # noqa
    assert callable(collect.coleta_completa)
    assert callable(image.baixar_imagem)
    assert callable(social_poster.postar_materias)
    assert callable(commercial_radar.print_top_leads)
    print("  OK: collect, image, social_poster, commercial_radar importam normalmente")

    restaurar_estado()
    print(f"\nRESULTADO FINAL: {resultados['ok']} OK, {resultados['falhas']} FALHAS")
    sys.exit(1 if resultados["falhas"] else 0)


if __name__ == "__main__":
    main()