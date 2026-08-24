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

    print("=" * 60)
    print("ETAPA 1/6 - Coleta de noticias")
    print("=" * 60)
    candidatas, _ = collect.coleta_completa()
    if not candidatas:
        print("Nenhuma noticia nova encontrada. Encerrando.")
        return

    print("\n" + "=" * 60)
    print("ETAPA 2/6 - Extracao de texto e classificacao")
    print("=" * 60)
    selecionadas = collect.processar_candidatas(candidatas, themes, max_itens=6)
    if not selecionadas:
        print("Nenhuma materia aproveitavel. Encerrando.")
        return

    print("\n" + "=" * 60)
    print("ETAPA 3/6 - Resumo com IA + imagem")
    print("=" * 60)
    publicadas = 0
    materias_para_social = []
    for item in selecionadas:
        try:
            titulo = item["titulo"]
            texto = item["texto"]

            # Resumo: tentar IA, fallback para texto original
            resumo = None
            if api_key:
                try:
                    print(f"[IA] Resumindo: {titulo[:60]}")
                    resumo = summarize.resumir_texto(texto, api_key)
                except Exception as e:
                    print(f"[IA] Fallback resumo: {e}")
                    resumo = summarize.resumir_fallback(texto)
            else:
                print(f"[FALLBACK] Sem API_KEY, resumindo localmente: {titulo[:60]}")
                resumo = summarize.resumir_fallback(texto)

            # Titulo: tentar IA, fallback para titulo original
            if api_key:
                try:
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

            print("[IMAGEM] Verificando imagem original...")
            imagem_orig = item.get("imagem_original") or item.get("imagem") or None
            nome_slug = slugify(item["titulo"])
            destino_jpg = os.path.join(BASE_DIR, "assets", "images", f"{nome_slug}.jpg")

            if imagem_orig:
                # Tenta baixar a imagem original primeiro
                print(f"  [ORIGINAL] {imagem_orig[:80]}...")
                try:
                    import requests as _req
                    resp = _req.get(imagem_orig, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
                    if resp.status_code == 200 and len(resp.content) > 2000:
                        with open(destino_jpg, "wb") as f:
                            f.write(resp.content)
                        nome_final = os.path.basename(destino_jpg)
                        imagem_rel = f"/assets/images/{nome_final}"
                        print(f"  [OK] Imagem original salva: {nome_final}")
                    else:
                        print(f"  [AVISO] Imagem original invalida ({resp.status_code}, {len(resp.content)} bytes), gerando com IA...")
                        imagem_orig = None
                except Exception as e:
                    print(f"  [AVISO] Falha ao baixar original: {e}, gerando com IA...")
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
                    imagem_rel = ""

            print("[PUBLICACAO] Salvando materia...")
            publish.publicar_materia(item, resumo, imagem_rel)
            publicadas += 1

            materias_para_social.append({
                "titulo": item["titulo"],
                "link": item["link"],
                "fonte": item["fonte"],
                "tema": item.get("tema", "Geral"),
                "resumo": resumo,
                "imagem": imagem_rel,
            })
        except Exception as e:
            print(f"[ERRO] falha ao processar {item.get('titulo', '?')}: {e}")

    print(f"\n[FIM] {publicadas} materia(s) publicadas nesta rodada.")

    if materias_para_social:
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
    print("ETAPA 6/6 - Atualizar analytics + slider automatico")
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


if __name__ == "__main__":
    main()
