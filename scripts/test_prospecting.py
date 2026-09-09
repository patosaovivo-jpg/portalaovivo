# -*- coding: utf-8 -*-
"""
TESTES OBRIGATÓRIOS da PROSPECÇÃO INTELIGENTE (ETAPA 3).

Como rodar (sem API, usa regras locais - fallback):
    python scripts/test_prospecting.py

Valida os 10 cenários obrigatórios:
   1. Festival em 15 dias        -> prospectar com urgência
   2. Campeonato em 30 dias      -> janela de prioridade
   3. Evento em 90 dias          -> monitorar/prospectar
   4. Evento passado             -> nao prospectar (monitorar)
   5. Evento sem data            -> monitorar
   6. Evento recorrente          -> boost de prioridade
   7. Com patrocinadores         -> sponsors_detected True (evidência)
   8. Sem patrocinadores         -> sponsors_detected False
   9. Empresarial (congresso)    -> cliente/serviço/dor corporativos
   10. Esportivo (corrida)       -> cliente/serviço esportivos

Também valida:
   - NUNCA envia mensagem (suggested_outreach é só rascunho >= 8)
   - NUNCA inventa contato (organizer_source só da fonte, organizer_url vazio)
   - prospecting_priority não substitui status (status continua vivo)
   - ranking TOP PROSPECÇÃO ordenado por prospecting_score
   - fluxo antigo (radar + pipeline imports) continua funcionando
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import analyze_article
import event_detector
import commercial_prospecting as cp

API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
LEADS_FILE = event_detector.LEADS_FILE


def _verificar_nunca_envia():
    """Prospecção inteligente NUNCA envia nada automaticamente."""
    fonte = os.path.join(BASE_DIR, "scripts", "commercial_prospecting.py")
    if not os.path.exists(fonte):
        return True
    linhas = []
    try:
        with open(fonte, "r", encoding="utf-8") as f:
            linhas = f.readlines()
    except Exception:
        return True
    padrao_envio = re.compile(
        r"(import\s+(smtplib|email|requests)\b|"
        r"webdriver\s*\(|pywhatkit|selenium|"
        r"sendmail\s*\(|send_message\s*\(|messages\.send\s*\(|"
        r"http\.post\s*\(|requests\.post\s*\("
        r"|\bwhatsapp\.html2|api\.whatsapp\.com|"
        r"graph\.facebook\.com.*message)", re.IGNORECASE)
    for linha in linhas:
        linha_sem_coment = linha.split("#")[0]
        if padrao_envio.search(linha_sem_coment):
            return False
    return True
LEADS_BACKUP = None

CENARIOS = [
    {
        "id": "C1 - Festival em 15 dias",
        "titulo": "Festival de Inverno acontece daqui a 15 dias em Patos de Minas",
        "texto": (
            "O Festival de Inverno acontece daqui a 15 dias em Patos de Minas, "
            "com expectativa de 15 mil pessoas. Uma produtora local é a "
            "organizadora. Ha 8 patrocinadores confirmados."),
        "esperado": {"timing": "futuro", "dias": 15, "janela": "urgente",
                     "tipo": "festival"},
    },
    {
        "id": "C2 - Campeonato em 30 dias",
        "titulo": "Campeonato Regional da Liga Patense começa daqui a 30 dias",
        "texto": (
            "O Campeonato Regional da Liga Patense começa daqui a 30 dias. "
            "A liga esportiva organiza a competicao com 20 mil torcedores "
            "esperados em toda a regiao."),
        "esperado": {"timing": "futuro", "dias": 30, "tipo": "campeonato"},
    },
    {
        "id": "C3 - Evento em 90 dias",
        "titulo": "Congresso empresarial sera realizado daqui a 90 dias em Patrocinio",
        "texto": (
            "O Congresso empresarial sera realizado daqui a 90 dias em Patrocinio, "
            "para 3 mil participantes, com palestras e workshops. Uma entidade "
            "empresarial organiza o evento."),
        "esperado": {"timing": "futuro", "dias": 90, "tipo": "congresso"},
    },
    {
        "id": "C4 - Evento passado",
        "titulo": "Feira agropecuaria registrou publico recorde no fim de semana",
        "texto": (
            "A Feira agropecuaria registrou publico recorde de 40 mil pessoas "
            "no fim de semana em Coromandel. A organizacao comemorou o resultado "
            "e ja confirma a proxima edicao."),
        "esperado": {"timing": "passado", "tipo": "feira"},
    },
    {
        "id": "C5 - Evento sem data",
        "titulo": "Show de encerramento da semana cultural sera anunciado",
        "texto": (
            "O show de encerramento da Semana Cultural de Varjao de Minas sera "
            "anunciado em breve. A prefeitura organiza a programacao cultural "
            "com apresentacoes e feira de artesanato."),
        "esperado": {"timing": "sem_data", "tipo": "show"},
    },
    {
        "id": "C6 - Evento recorrente anual",
        "titulo": "Festa do Cafe comemora edicao tradicional daqui a 45 dias",
        "texto": (
            "A Festa do Cafe, evento tradicional anual em Patrocinio, sera "
            "realizada daqui a 45 dias com expectativa de 10 mil pessoas. A "
            "prefeitura e a associacao organizam."),
        "esperado": {"timing": "futuro", "dias": 45, "recorrente": True,
                     "tipo": "festa"},
    },
    {
        "id": "C7 - Com patrocinadores",
        "titulo": "Rodeio com patrocinadores daqui a 25 dias em Serra do Salitre",
        "texto": (
            "O Rodeio em Serra do Salitre sera realizado daqui a 25 dias, com "
            "patrocinado por uma cervejaria e ha 5 patrocinadores confirmados. "
            "Uma produtora de eventos organiza."),
        "esperado": {"timing": "futuro", "dias": 25, "patrocinadores": True},
    },
    {
        "id": "C8 - Sem patrocinadores",
        "titulo": "Quermesse da festa do padroeiro acontece daqui a 18 dias",
        "texto": (
            "A Quermesse da festa do padroeiro acontece daqui a 18 dias em "
            "Sacramento, organizada pela paroquia local, com shows e barracas."),
        "esperado": {"timing": "futuro", "dias": 18, "patrocinadores": False,
                     "tipo": "festa religiosa"},
    },
    {
        "id": "C9 - Empresarial",
        "titulo": "Conferencia de inovacao para empresas ocorre em 35 dias",
        "texto": (
            "A Conferencia de inovacao ocorre daqui a 35 dias em Araxa, para "
            "2 mil participantes, com palestras e mesas redondas. Uma "
            "entidade empresarial organiza o evento."),
        "esperado": {"timing": "futuro", "dias": 35, "tipo": "conferencia"},
    },
    {
        "id": "C10 - Esportivo corrida",
        "titulo": "Corrida de rua em Sao Gotardo acontece daqui a 12 dias",
        "texto": (
            "A Corrida de rua de Sao Gotardo acontece daqui a 12 dias, com "
            "3 mil corredores inscritos. A liga esportiva e a prefeitura "
            "organizam a prova."),
        "esperado": {"timing": "em_breve", "dias": 12, "tipo": "corrida"},
    },
    {
        "id": "C11 - Cavalgada (novo tipo)",
        "titulo": "Cavalgada em Rio Paranaiba acontece daqui a 22 dias",
        "texto": (
            "A Cavalgada em Rio Paranaiba acontece daqui a 22 dias, reunindo "
            "criadores e cavaleiros da regiao. O sindicato rural organiza com "
            "a prefeitura."),
        "esperado": {"timing": "futuro", "dias": 22, "tipo": "cavalgada"},
    },
    {
        "id": "C12 - Porte alto pontua mais",
        "titulo": "Show em Patos de Minas sera realizado daqui a 40 dias",
        "texto": (
            "O show de sertanejo em Patos de Minas sera realizado daqui a 40 "
            "dias, com expectativa de 60 mil pessoas no estadio. Uma produtora "
            "de eventos organiza o show."),
        "esperado": {"timing": "futuro", "dias": 40, "tipo": "show",
                     "porte_alto": True},
    },
]


def registrar(item, rules, themes):
    analise = analyze_article.analisar_noticia(item, themes=themes, rules=rules)
    evento = event_detector.detectar_evento(item, analise, themes, rules)
    res = event_detector.registrar_lead(item, analise, evento, rules, themes)
    return analise, evento, res


def testar_estado_salvo():
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
    print("PROSPECÇÃO INTELIGENTE - SIMULAÇÃO (10 cenários)")
    print("=" * 70)

    testar_estado_salvo()
    resultados = {"ok": 0, "falhas": 0}

    for c in CENARIOS:
        item = {"titulo": c["titulo"], "texto": c["texto"], "tema": "Geral",
                "fonte": "Teste", "link": f"https://teste/{c['id']}"}
        print(f"\n>>> {c['id']}")
        print(f"    {c['titulo']}")

        analise, evento, res = registrar(item, rules, themes)
        lead = res.get("lead") or {}
        ok = True

        def assert_ok(cond, msg):
            nonlocal ok
            if not cond:
                ok = False
                print(f"    [FALHA] {msg}")

        # pelo menos um lead registrado
        assert_ok(res.get("status") in ("novo", "atualizado"),
                  f"lead nao registrado ({res.get('status')})")

        if not ok:
            resultados["falhas"] += 1
            continue

        # --- Todas as chaves novas da ETAPA 3 presentes ---
        campos = ["lead_id", "event_id", "potential_client_type",
                  "recommended_services", "commercial_need",
                  "recommended_contact_window", "contact_window",
                  "prospecting_priority", "recurring_event",
                  "recurrence_pattern", "organizer_type",
                  "organizer_source", "organizer_url",
                  "sponsors_detected", "sponsors_evidence",
                  "contact_reason", "suggested_outreach",
                  "contact_history", "notes", "prospecting_score"]
        ausentes = [k for k in campos if k not in lead]
        assert_ok(not ausentes, f"campos da ETAPA 3 ausentes: {ausentes}")

        # --- Cenário específico ---
        esp = c["esperado"]
        if esp.get("timing"):
            assert_ok(lead.get("event_timing") == esp["timing"],
                      f"timing {lead.get('event_timing')} != {esp['timing']}")
        if esp.get("dias") is not None:
            dias = lead.get("days_until_event")
            assert_ok(dias is not None and int(dias) == esp["dias"],
                      f"days_until_event {dias} != {esp['dias']}")
        if esp.get("tipo"):
            assert_ok(esp["tipo"] in (analise.get("event_type") or []),
                      f"tipo {analise.get('event_type')} nao contem {esp['tipo']}")

        prio = lead.get("prospecting_priority")
        janela = lead.get("contact_window")
        assert_ok(prio in cp.LADDER, f"prioridade invalida: {prio}")
        assert_ok(janela in cp.WINDOW_TEXTO,
                  f"janela invalida: {janela}")
        if esp.get("janela"):
            assert_ok(janela == esp["janela"],
                      f"janela {janela} != esperada {esp['janela']}")

        # Não inventa contatos
        assert_ok(not lead.get("organizer_url"),
                  "organizer_url nao deveria ser preenchido (sem fonte)")
        if esp.get("timing", "futuro") != "passado":
            assert_ok(not lead.get("suggested_outreach")
                      or lead.get("lead_score", 0) >= 8,
                      "rascunho gerado sem lead_score >= 8")

        # Patrocinadores por evidência textual
        if esp.get("patrocinadores") is not None:
            assert_ok(lead.get("sponsors_detected") == esp["patrocinadores"],
                      f"sponsors_detected {lead.get('sponsors_detected')} != "
                      f"{esp['patrocinadores']}")
            if esp["patrocinadores"] is False:
                assert_ok(not lead.get("sponsors_evidence"),
                          "evidencia de patrocinio sem menção textual")

        # Recorrência
        if esp.get("recorrente"):
            assert_ok(lead.get("recurring_event") is True and
                      lead.get("recurrence_pattern"),
                      "recorrencia nao detectada ou sem padrao")

        # Porte elevado não deixa o score de prospecção baixo
        if esp.get("porte_alto"):
            assert_ok(float(lead.get("prospecting_score") or 0) >= 7.0,
                      f"porte alto deveria pontuar bem: "
                      f"{lead.get('prospecting_score')}")

        # Verificação de prioridade esperada (decorre das janelas)
        prio_esperada = {15: "urgente", 30: "alto", 90: "monitorar",
                         12: "urgente", 18: "urgente", 25: "alto",
                         35: "alto"}.get(lead.get("days_until_event"))
        if prio_esperada and not esp.get("recorrente"):
            assert_ok(prio == prio_esperada,
                      f"prioridade {prio} != esperada {prio_esperada}")

        # Recorrência em evento próximo eleva a prioridade por um degrau
        if esp.get("recorrente") and lead.get("days_until_event"):
            assert_ok(prio == "urgente",
                      f"recorrente em 45d deveria subir para urgente, veio {prio}")

        # Passado: não prospectar
        if lead.get("event_timing") == "passado":
            assert_ok(janela == "nao_prospectar" and prio == "monitorar",
                      f"passado deve ser nao_prospectar/monitorar ({janela}/{prio})")

        print(f"    cliente provavel: {lead.get('potential_client_type')}")
        print(f"    servicos: {lead.get('recommended_services')}")
        print(f"    dor: {lead.get('commercial_need')[:60]}")
        print(f"    janela: {lead.get('recommended_contact_window')!r}")
        print(f"    prioridade: {prio} | janela={janela} | "
              f"prospecting_score={lead.get('prospecting_score')} | "
              f"sponsors={lead.get('sponsors_detected')}")

        if ok:
            resultados["ok"] += 1
            print("    [OK]")
        else:
            resultados["falhas"] += 1

    # ---- STATUS NÃO É SUBSTITUÍDO PELA PRIORIDADE ----
    print("\n" + "=" * 70)
    print("STATUS CONTINUA VIVO (prioridade não substitui status)")
    print("=" * 70)
    item = CENARIOS[0]
    item = {"titulo": item["titulo"], "texto": item["texto"], "tema": "Geral",
            "fonte": "Teste", "link": "https://teste/status-prospeccao"}
    _, _, res = registrar(item, rules, themes)
    lead = res.get("lead")
    if not lead:
        resultados["falhas"] += 1
        print("    [FALHA] sem lead para teste de status")
    else:
        leads = event_detector.load_leads()
        chave = [k for k, v in leads.items()
                 if v.get("event_name") == lead.get("event_name")
                 and v.get("city") == lead.get("city")][0]
        leads[chave]["status"] = "contatado"
        leads[chave]["prospecting_priority"] = "muito_urgente"
        event_detector.save_leads(leads)

        _, _, res2 = registrar(item, rules, themes)
        l2 = res2.get("lead") or {}
        if l2.get("status") == "contatado" and l2.get("prospecting_priority") in cp.LADDER:
            resultados["ok"] += 1
            print(f"    [OK] status={l2['status']} NÃO substituído por "
                  f"prospecting_priority={l2['prospecting_priority']}")
        else:
            resultados["falhas"] += 1
            print(f"    [FALHA] status={l2.get('status')} / "
                  f"priority={l2.get('prospecting_priority')}")

    # ---- RANKING TOP PROSPECÇÃO (ordem por prospecting_score) ----
    print("\n" + "=" * 70)
    print("RANKING TOP PROSPECÇÃO (ordena por prospecting_score)")
    print("=" * 70)
    cp.enriquecer_leads()
    topo = cp.top_prospeccao(limite=10)
    scores = [float(l.get("prospecting_score") or 0) for l in topo]
    if len(topo) >= 2 and scores == sorted(scores, reverse=True):
        resultados["ok"] += 1
        print(f"    [OK] TOP PROSPECÇÃO ordenado: "
              + ", ".join(f"{s:.1f}" for s in scores))
    elif len(topo) == 1:
        resultados["ok"] += 1
        print(f"    [OK] apenas 1 lead, score {scores[0]:.1f}")
    else:
        resultados["falhas"] += 1
        print(f"    [FALHA] ranking invalido: {scores}")

    # ---- FUNIL DE PROSPECÇÃO (ETAPA 4) ----
    print("\n" + "=" * 70)
    print("FUNIL DE PROSPECÇÃO (acompanhamento manual)")
    print("=" * 70)
    try:
        r = cp.resumo_funil()
        ok_f = (isinstance(r.get("total"), int)
                and r.get("total") >= 0
                and isinstance(r.get("por_prioridade"), dict)
                and isinstance(r.get("a_fazer"), list))
        if ok_f:
            resultados["ok"] += 1
            print(f"    [OK] funil: total={r['total']}, "
                  f"urgentes={len(r['urgentes'])}, "
                  f"monitorar={len(r['monitoring'])}, "
                  f"a_fazer={len(r['a_fazer'])}")
        else:
            resultados["falhas"] += 1
            print(f"    [FALHA] funil malformado: {r}")
        cp.print_resumo_funil()
    except Exception as e:
        resultados["falhas"] += 1
        print(f"    [FALHA] funil quebrou: {e}")

    # ---- RELATÓRIO DIÁRIO (ETAPA 4) ----
    print("\n" + "=" * 70)
    print("RELATÓRIO DIÁRIO DE PROSPECÇÃO (markdown)")
    print("=" * 70)
    rel_temp = os.path.join(BASE_DIR, "data", "prospeccao_teste.md")
    try:
        gerou = cp.gerar_relatorio_diario(arquivo=rel_temp)
        conteudo = open(gerou, "r", encoding="utf-8").read()
        if (os.path.exists(gerou)
                and conteudo.startswith("# Relatório de Prospecção")
                and "suggested_outreach" in conteudo
                and "não enviados" in conteudo):
            resultados["ok"] += 1
            print(f"    [OK] relatório markdown gerado ({len(conteudo)} chars)")
        else:
            resultados["falhas"] += 1
            print("    [FALHA] relatório markdown malformado")
        if os.path.exists(rel_temp):
            os.remove(rel_temp)
    except Exception as e:
        resultados["falhas"] += 1
        print(f"    [FALHA] relatório quebrou: {e}")

    # ---- SCORING: porte/público peso no rank (ETAPA 4) ----
    print("\n" + "=" * 70)
    print("SCORING PONDERA PORTE/PÚBLICO ESTIMADO")
    print("=" * 70)
    try:
        base = {
            "event_name": "Evento Teste Score", "city": "Patos de Minas",
            "event_type": "show", "event_timing": "futuro",
            "days_until_event": 40, "lead_score": 8.0,
            "organizer": "Produtora Local", "source": "Teste",
            "estimated_audience": 100,
        }
        base2 = dict(base)
        base2["estimated_audience"] = 60000
        cp.enriquecer_lead(base, leads={}, rules=None)
        cp.enriquecer_lead(base2, leads={}, rules=None)
        s1 = float(base.get("prospecting_score") or 0)
        s2 = float(base2.get("prospecting_score") or 0)
        if s2 - s1 >= 0.3:
            resultados["ok"] += 1
            print(f"    [OK] público 60k ({s2:.1f}) pontua acima de público 100 "
                  f"({s1:.1f})")
        else:
            resultados["falhas"] += 1
            print(f"    [FALHA] porte nao pesou: pequeno={s1:.1f} grande={s2:.1f}")
    except Exception as e:
        resultados["falhas"] += 1
        print(f"    [FALHA] teste de scoring quebrou: {e}")

    # ---- PAINEL imprime sem quebrar ----
    print("\n" + "=" * 70)
    print("PAINEL DE PROSPECÇÃO (imprime no GitHub Actions)")
    print("=" * 70)
    try:
        cp.print_painel_prospeccao(limite=10)
        resultados["ok"] += 1
        print("    [OK] painel de prospecção gerado")
    except Exception as e:
        resultados["falhas"] += 1
        print(f"    [FALHA] painel quebrou: {e}")

    # ---- OUTBOX: fila semi-manual (ETAPA 5) ----
    print("\n" + "=" * 70)
    print("OUTBOX — FILA DE APROVAÇÃO (envio SEMPRE manual)")
    print("=" * 70)
    try:
        import json
        from copy import deepcopy
        backup_outbox = None
        if os.path.exists(cp.OUTBOX_FILE):
            backup_outbox = open(cp.OUTBOX_FILE, "r", encoding="utf-8").read()
        leads_fake = {
            "outbox-lead-1": {"lead_id": "outbox-lead-1", "event_id": "ev-1",
             "event_name": "Show Teste Outbox", "city": "Patos de Minas",
             "event_timing": "futuro", "days_until_event": 5,
             "prospecting_priority": "urgente", "prospecting_score": 9.1,
             "lead_score": 9.5, "organizer": "Produtora Local",
             "sponsors_count": 2, "estimated_audience": 60000,
             "recurring_event": True,
             "suggested_outreach": "rascunho original",
             "contact_window": "5 dias antes", "potential_client_type": ["produtor"],
             "recommended_services": ["cobertura"], "status": "novo"},
            "outbox-lead-2": {"lead_id": "outbox-lead-2", "event_id": "ev-2",
             "event_name": "Evento Fraco", "city": "Patos de Minas",
             "event_timing": "futuro", "days_until_event": 30,
             "prospecting_priority": "baixo", "prospecting_score": 5.0,
             "lead_score": 5.0, "suggested_outreach": "Rascunho fraco",
             "contact_window": "30 dias antes", "potential_client_type": ["produtor"],
             "recommended_services": ["cobertura"], "status": "novo"},
        }
        import event_detector as _ed
        _backup_leads = {}
        if os.path.exists(_ed.LEADS_FILE):
            _backup_leads = deepcopy(_ed.load_leads())
        _ed.save_leads(leads_fake)
        gerar_outbox = getattr(cp, "gerar_outbox", None)
        if gerar_outbox is None:
            raise RuntimeError("gerar_outbox ainda não existe")
        itens = gerar_outbox()
        pendentes = [i for i in itens if i.get("status") == "pendente"]
        apenas_leads_fortes = all(
            i.get("lead_id") == "outbox-lead-1" for i in pendentes)
        tem_rascunho = any(bool(i.get("rascunho")) for i in itens)
        if pendentes and apenas_leads_fortes and tem_rascunho:
            resultados["ok"] += 1
            print(f"    [OK] {len(pendentes)} rascunho(s) na fila "
                  f"(apenas leads fortes, nunca enviados)")
        else:
            resultados["falhas"] += 1
            print(f"    [FALHA] outbox: {len(pendentes)} pendente(s), "
                  f"fortes={apenas_leads_fortes}, rascunho={tem_rascunho}")

        # decisão manual preservada
        alvo, err = cp.atualizar_status_outbox("outbox-lead-1", "enviado",
                                                observacao="enviado pelo diretor")
        if alvo and alvo.get("status") == "enviado" and alvo.get("enviado_em"):
            gerar_outbox(regerar=False)
            itens2 = cp.load_outbox()
            item_re= [i for i in itens2 if i.get("lead_id") == "outbox-lead-1"]
            if item_re and item_re[0].get("status") == "enviado":
                resultados["ok"] += 1
                print("    [OK] decisão manual 'enviado' preservada "
                      "(não sobrescrita)")
            else:
                resultados["falhas"] += 1
                print("    [FALHA] decisão manual perdida")
        else:
            resultados["falhas"] += 1
            print(f"    [FALHA] atualizar_status_outbox: {err}")

        # regerar() novo lead pós-envio volta a pendente
        if _backup_leads:
            _ed.save_leads(_backup_leads)
        else:
            open(_ed.LEADS_FILE, "w", encoding="utf-8").write(
                json.dumps({"leads": {}}, ensure_ascii=False))
        # OUTBOX: restaura backup
        if backup_outbox is not None:
            with open(cp.OUTBOX_FILE, "w", encoding="utf-8") as f:
                f.write(backup_outbox)
        else:
            # limpa arquivo pós-teste (não existia antes)
            open(cp.OUTBOX_FILE, "w", encoding="utf-8").write(
                json.dumps({"itens": []}, ensure_ascii=False))
    except Exception as e:
        resultados["falhas"] += 1
        print(f"    [FALHA] teste de outbox quebrou: {e}")

    # ---- NUNCA ENVIA NADA ----
    print("\n" + "=" * 70)
    print("SAÍDA NUNCA ENVIA MENSAGEM (rascunho apenas)")
    print("=" * 70)
    import builtins
    chamadas_io = []
    original_print = print
    original_input = input
    # Verificar que não há código de envio (nenhum e-mail/API de mensagem)
    if _verificar_nunca_envia():
        resultados["ok"] += 1
        print("    [OK] nenhum código de envio automático na camada de prospecção")
    else:
        resultados["falhas"] += 1
        print("    [FALHA] código de envio encontrado em commercial_prospecting.py")

    restaurar_estado()
    print(f"\nRESULTADO FINAL: {resultados['ok']} OK, {resultados['falhas']} FALHAS")
    sys.exit(1 if resultados["falhas"] else 0)


if __name__ == "__main__":
    main()