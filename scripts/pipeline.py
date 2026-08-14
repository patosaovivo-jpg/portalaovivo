import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import collect
import image
import publish
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
        print("[ERRO] GEMINI_API_KEY não definida. Abortando.")
        sys.exit(1)

    themes = collect.load_json(os.path.join(BASE_DIR, "themes.json"))

    print("=" * 60)
    print("ETAPA 1/4 - Coleta de notícias")
    print("=" * 60)
    candidatas, _ = collect.coleta_completa()
    if not candidatas:
        print("Nenhuma notícia nova encontrada. Encerrando.")
        return

    print("\n" + "=" * 60)
    print("ETAPA 2/4 - Extração de texto e classificação")
    print("=" * 60)
    selecionadas = collect.processar_candidatas(candidatas, themes, max_itens=6)
    if not selecionadas:
        print("Nenhuma matéria aproveitável. Encerrando.")
        return

    print("\n" + "=" * 60)
    print("ETAPA 3/4 - Resumo com IA + imagem")
    print("=" * 60)
    publicadas = 0
    for item in selecionadas:
        try:
            print(f"\n[IA] Resumindo: {item['titulo'][:60]}")
            resumo = summarize.resumir_texto(item["texto"], api_key)
            titulo_ia = summarize.gerar_titulo(resumo, api_key)
            if titulo_ia and len(titulo_ia) > 10:
                item["titulo"] = titulo_ia

            print("[IMAGEM] Gerando ilustração...")
            prompt = image.gerar_prompt_imagem(resumo, item["titulo"], item["tema"])
            nome_img = f"{slugify(item['titulo'])}.jpg"
            destino = os.path.join(BASE_DIR, "assets", "images", nome_img)
            img = image.baixar_imagem(prompt, destino)
            if img:
                imagem_rel = f"/assets/images/{nome_img}"
            else:
                imagem_rel = ""

            print("[PUBLICAÇÃO] Salvando matéria...")
            publish.publicar_materia(item, resumo, imagem_rel)
            publicadas += 1
        except Exception as e:
            print(f"[ERRO] falha ao processar {item.get('titulo', '?')}: {e}")

    print(f"\n[FIM] {publicadas} matéria(s) publicadas nesta rodada.")


if __name__ == "__main__":
    main()