import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import collect
import image
import publish
import social_poster
import summarize
import analyze_article
import event_detector


def slugify(texto):
    import re

    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9\s]", "", texto)
    texto = re.sub(r"\s+", "-", texto.strip())
    return texto[:60].strip("-")


def main():
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("[AVISO] GEMINI_API_KEY nao definida. Geradores gratuitos continuam funcionando.")

    themes = collect.load_json(os.path.join(BASE_DIR, "themes.json"))
    rules = analyze_article.load_commercial_rules()

    print("=" * 60)
    print("ETAPA 1/8 - Coleta de noticias")
    print("=" * 60)
    candidatas, _ = collect.coleta_completa()
    if not candidatas:
        print("Nenhuma noticia nova encontrada. Encerrando.")
        return

    print("\n" + "=" * 60)
    print("ETAPA 2/8 - Extracao de texto, deduplicacao e filtro editorial")
    print("=" * 60)
    selecionadas = collect.processar_candidatas(candidatas, themes, max_itens=6)
    if not selecionadas:
        print("Nenhuma materia aproveitavel. Encerrando.")
        return

    print("\n" + "=" * 60)
    print("ETAPA 3/8 - Analise Editorial + Comercial (scores, evento, lead)")
    print("=" * 60)
    print("----- Analise inteligente -----")
    for item in selecionadas:
        try:
            item["analise"] = analyze_article.analisar_noticia(
                item, api_key, themes=themes, rules=rules)
        except Exception as e:
            print(f"[ANALYZER] Falha ao analisar {item.get('titulo','?')}: {e}")

    print("\n" + "=" * 60)
    print("ETAPA 4/8 - Resumo com IA + imagem + publicacao")
    print("=" * 60)
    publicadas = 0
    materias_para_social = []
    for item in selecionadas:
        try:
            titulo = item["titulo"]
            texto = item["texto"]
            analise = item.get("analise") or {}

            # Resumo: tentar IA, fallback para texto original
            resumo = None
            eh_edital = item.get("tipo") == "edital"
            if api_key:
                try:
                    print(f"[IA] {'Resumindo edital' if eh_edital else 'Resumindo'}: {titulo[:60]}")
                    resumo = summarize.resumir_texto_com_analise(
                        texto, analise, api_key, eh_edital=eh_edital)
                except Exception as e:
                    print(f"[IA] Fallback resumo: {e}")
                    resumo = summarize.resumir_fallback(texto)
            else:
                print(f"[FALLBACK] Sem API_KEY, resumindo localmente: {titulo[:60]}")
                resumo = summarize.resumir_texto_com_analise(
                    texto, analise, api_key, eh_edital=eh_edital)

            # Titulo: tentar IA, fallback para titulo original
            if api_key:
                try:
                    if eh_edital:
                        titulo_ia = summarize.gerar_titulo_edital(resumo, api_key)
                    else:
                        titulo_ia = summarize.gerar_titulo(resumo, api_key)
                    if titulo_ia and len(titulo_ia) > 10:
                        titulo = titulo_ia
                except Exception as e:
                    print(f"[IA] Fallback titulo: {e}")

            item["titulo"] = titulo

            # Validacao final: pular posts com titulo-URL ou resumo vazio
            if titulo.startswith("http"):
                print(f"[SKIP] Titulo e URL, pulando: {titulo[:60]}")
                continue
            if not resumo or len(resumo.strip()) < 100:
                print(f"[SKIP] Resumo muito curto ou vazio, pulando: {titulo[:60]}")
                continue

            # Deteccao de evento + registro de lead comercial
            evento = event_detector.detectar_evento(item, analise, themes, rules)
            item["evento"] = evento
            for campo in ("event_name", "event_city", "event_date", "organizer"):
                if evento.get(campo):
                    item[campo] = evento[campo]
            if evento.get("event_detected"):
                resultado_lead = event_detector.registrar_lead(item, analise, evento, rules, themes)
                timing = evento.get("event_timing") or "sem_data"
                dias = evento.get("days_until")
                quando = f"em {dias}d" if dias is not None else timing
                print(f"[ANALYZER] Evento detectado: {evento.get('event_name')} ({quando})")
                if resultado_lead.get("status") in ("novo", "atualizado"):
                    lead = resultado_lead["lead"]
                    print(f"[ANALYZER] Oportunidade comercial: {lead.get('priority') or '-'} | "
                          f"lead_score={lead.get('lead_score')}")
                    print(f"[ANALYZER] Serviço sugerido: {', '.join(analise.get('suggested_service') or [])}")
                    print(f"[ANALYZER] Lead registrado ({resultado_lead['status']})")
            else:
                analise["event_name"] = None

            # Conteudo social especial (Reel/Stories/Carousel)
            conteudo_social = None
            if analise.get("generate_reel") or analise.get("generate_cta") or analise.get("commercial_score", 0) >= 8:
                conteudo_social = analyze_article.gerar_conteudo_social(
                    item, analise, resumo, api_key)
                item["conteudo_social"] = conteudo_social
                print("[ANALYZER] Conteúdo social especial gerado (reel/stories/carousel)")

            print("[IMAGEM] Verificando imagem original...")
            imagem_orig = item.get("imagem_original") or item.get("imagem") or None
            forca_ia = item.get("imagem_ia", False)
            if forca_ia:
                print("  [IA] Fonte marcada para imagem IA, ignorando imagem original")
                imagem_orig = None
            nome_slug = slugify(item["titulo"])
            destino_jpg = os.path.join(BASE_DIR, "assets", "images", f"{nome_slug}.jpg")

            if imagem_orig:
                # Baixa imagem original e aplica efeito cyberpunk
                print(f"  [ORIGINAL] {imagem_orig[:80]}...")
                try:
                    cyber_ok = image.baixar_e_cyberpunk(imagem_orig, destino_jpg)
                    if cyber_ok:
                        nome_final = os.path.basename(destino_jpg)
                        imagem_rel = f"/assets/images/{nome_final}"
                        print(f"  [OK] Imagem cyberpunk salva: {nome_final}")
                    else:
                        print(f"  [AVISO] Cyberpunk falhou, gerando com IA...")
                        imagem_orig = None
                except Exception as e:
                    print(f"  [AVISO] Falha ao processar imagem: {e}, gerando com IA...")
                    imagem_orig = None

            # Gera imagem apenas se nao tem original
            if not imagem_orig:
                print("[IMAGEM] Gerando ilustracao com IA...")
                prompt = image.gerar_prompt_imagem(resumo, item["titulo"], item["tema"])
                img = image.baixar_imagem(
                    prompt, destino_jpg, api_key=api_key,
                )
                if img:
                    nome_final = os.path.basename(img)
                    imagem_rel = f"/assets/images/{nome_final}"
                else:
                    print("[IMAGEM] Todos os geradores falharam, usando default.jpg")
                    imagem_rel = "/assets/images/default.jpg"

            print("[PUBLICACAO] Salvando materia...")
            sem_fonte = item.get("sem_fonte", False)
            publish.publicar_materia(item, resumo, imagem_rel, sem_fonte,
                                     analise=analise)
            publicadas += 1

            # Gera versao social 1:1 grafite (para Instagram)
            imagem_social = imagem_rel
            try:
                if imagem_rel and imagem_rel != "/assets/images/default.jpg":
                    origem_local = os.path.join(BASE_DIR, "assets", "images", os.path.basename(imagem_rel))
                    destino_social_nome = "social-" + os.path.basename(imagem_rel)
                    destino_social = os.path.join(BASE_DIR, "assets", "images", destino_social_nome)
                    if os.path.exists(origem_local):
                        if image.processar_grafite_local(origem_local, destino_social):
                            imagem_social = f"/assets/images/{destino_social_nome}"
            except Exception as e:
                print(f"  [GRAFITE] Falha ao preparar img social: {e}")

            materias_para_social.append({
                "titulo": item["titulo"],
                "link": item["link"],
                "fonte": item["fonte"],
                "tema": item.get("tema", "Geral"),
                "resumo": resumo,
                "imagem": imagem_social,
                # ----- campos da camada editorial/comercial -----
                "category": analise.get("category", "geral"),
                "editorial_score": analise.get("editorial_score", 5),
                "commercial_score": analise.get("commercial_score", 0),
                "instagram_score": analise.get("instagram_score", 5),
                "event_related": analise.get("event_related", False),
                "sports_related": analise.get("sports_related", False),
                "regional": analise.get("regional", False),
                "commercial_angle": analise.get("commercial_angle", ""),
                "target_customer": analise.get("target_customer", []),
                "suggested_service": analise.get("suggested_service", []),
                "generate_reel": analise.get("generate_reel", False),
                "generate_cta": analise.get("generate_cta", False),
                "event_name": (evento or {}).get("event_name") or "",
                "event_city": (evento or {}).get("event_city") or "",
                "event_date": (evento or {}).get("event_date") or "",
                "conteudo_social": conteudo_social,
            })
        except Exception as e:
            print(f"[ERRO] falha ao processar {item.get('titulo', '?')}: {e}")

    print(f"\n[FIM] {publicadas} materia(s) publicadas nesta rodada.")

    if materias_para_social:
        print("\n" + "=" * 60)
        print("ETAPA 5/8 - Fila para redes sociais (Instagram priorizada)")
        print("=" * 60)
        pending_file = os.path.join(BASE_DIR, "data", "pending_social.json")
        os.makedirs(os.path.dirname(pending_file), exist_ok=True)

        existentes = []
        if os.path.exists(pending_file):
            with open(pending_file, "r", encoding="utf-8") as f:
                existentes = json.load(f)

        links_existentes = {m["link"] for m in existentes}
        novas = [m for m in materias_para_social if m["link"] not in links_existentes]
        combinadas = existentes + novas

        with open(pending_file, "w", encoding="utf-8") as f:
            json.dump(combinadas, f, ensure_ascii=False, indent=2)
        print(f"[SOCIAL] {len(novas)} nova(s) + {len(existentes)} existente(s) = {len(combinadas)} materia(s) na fila")

    print("\n" + "=" * 60)
    print("ETAPA 6/8 - Postagem nas redes sociais (executada na etapa do workflow)")
    print("=" * 60)
    print("[SOCIAL] Postagem feita por scripts/social_poster.py na etapa seguinte do CI.")

    print("\n" + "=" * 60)
    print("ETAPA 7/8 - Pesquisa viral (historias e curiosidades regionais)")
    print("=" * 60)
    try:
        import research_viral
        viral = research_viral.executar_pesquisa_viral(max_posts=1, um_por_dia=True)
        for v in viral:
            print(f"[VIRAL] Publicado: {v['titulo']}")
    except Exception as e:
        print(f"[VIRAL] Passo de pesquisa viral falhou: {e}")

    print("\n" + "=" * 60)
    print("ETAPA 8/8 - Atualizar analytics + slider automatico")
    print("=" * 60)
    try:
        import analytics
        analytics.salvar_popular(dias=7, limite=10)
    except Exception as e:
        print(f"[ANALYTICS] Pulou: {e}")
    try:
        import slider
        slider.salvar_slider(limite_minimo=3)
    except Exception as e:
        print(f"[SLIDER] Pulou: {e}")

    try:
        import commercial_radar
        commercial_radar.print_top_leads(limite=10)
    except Exception as e:
        print(f"[RADAR] Pulou: {e}")

    print("\n" + "=" * 60)
    print("PROSPECÇÃO INTELIGENTE - Painel do diretor comercial")
    print("=" * 60)
    try:
        import commercial_prospecting
        n = commercial_prospecting.enriquecer_leads()
        print(f"[PROSPECCAO] {n} lead(s) enriquecidos.")
        commercial_prospecting.print_painel_prospeccao(limite=10)
        commercial_prospecting.print_resumo_funil()
        rel = commercial_prospecting.gerar_relatorio_diario()
        print(f"[PROSPECCAO] Relatório diário: {os.path.relpath(rel, BASE_DIR)}")
    except Exception as e:
        print(f"[PROSPECCAO] Pulou: {e}")


if __name__ == "__main__":
    main()
