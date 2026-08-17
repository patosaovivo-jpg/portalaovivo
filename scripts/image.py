import base64
import json
import os
import re
import time
import urllib.parse

import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ============================================================
# PROMPTS MELHORADOS - FOTOJORNALISMO
# ============================================================

STYLE_SUFIXO = (
    ", editorial photograph, photojournalism, natural lighting, "
    "high detail, dramatic composition, rule of thirds, "
    "no text, no logos, no watermarks, no faces clearly identifiable, "
    "cinematic color grading, shallow depth of field"
)

STYLE_GRAFFITI = (
    " street art mural, vibrant spray paint style, bold outlines, "
    "urban graffiti art, dripping paint texture, stencil accents, "
    "black white and red color palette, high contrast, "
    "no readable text, no logos"
)

PROMPT_BASE = (
    "A realistic editorial photograph illustrating this news story "
    "with a generic scene (no specific people, no logos, no brands). "
    "Use symbolic or metaphorical visual elements. "
    "Horizontal composition (16:9 aspect ratio). "
    "Scene: {resumo}"
)

PROMPT_GRAFFITI = (
    "Transform this photograph into a vibrant street art graffiti mural. "
    "Keep the subject and theme of the original image. "
    "Apply spray paint texture, bold outlines, stencil techniques. "
    "No readable text, no logos. "
    "Theme context: {resumo}"
)

# Modelos por finalidade (testados e funcionando em Ago/2026)
MODELOS_GRAFFITI = ["klein"]
MODELOS_TEXTO = ["flux", "sana"]

# Gemini models (ordem de preferencia)
GEMINI_MODELS = [
    "gemini-3.1-flash-image",
    "gemini-3.1-flash-lite-image",
    "gemini-2.5-flash-image",
]


def slugify(texto):
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9\s]", "", texto)
    texto = re.sub(r"\s+", "-", texto.strip())
    return texto[:60].strip("-")


def gerar_prompt_imagem(resumo, titulo, tema):
    ctx = resumo[:600]
    if titulo:
        ctx = titulo[:120] + ". " + ctx
    return (PROMPT_BASE.format(resumo=ctx) + STYLE_SUFIXO).strip()


def gerar_prompt_graffiti(resumo, titulo, tema):
    ctx = ""
    if titulo:
        ctx = titulo[:120]
    if resumo:
        ctx += ". " + resumo[:400]
    ctx = ctx.strip() or "urban scene"
    return (PROMPT_GRAFFITI.format(resumo=ctx) + STYLE_GRAFFITI).strip()


# ============================================================
# GERADOR 1: GEMINI (teste com chave atual)
# ============================================================

def _gerar_gemini(prompt, destino, api_key, largura=900, altura=500):
    """Tenta gerar imagem via Gemini Nano Banana.
    Retorna True se sucesso, False se falhar."""
    if not api_key:
        return False

    try:
        from google import genai
    except ImportError:
        try:
            import google.generativeai as genai_legacy
            return _gerar_gemini_legacy(prompt, destino, api_key, largura, altura, genai_legacy)
        except ImportError:
            print("  [GEMINI] SDK nao instalado, pulando")
            return False

    try:
        client = genai.Client(api_key=api_key)

        for model in GEMINI_MODELS:
            try:
                ratio = f"{largura}:{altura}"
                resp = client.models.generate_images(
                    model=model,
                    prompt=prompt,
                    config=genai.types.GenerateImagesConfig(
                        number_of_images=1,
                        image_size="1K:" + ratio if ":" in str(ratio) else "1K",
                        safety_filter_level="block_none",
                    ),
                )
                if resp.generated_images:
                    img = resp.generated_images[0]
                    img_bytes = img.image.image_bytes
                    if img_bytes:
                        os.makedirs(os.path.dirname(destino), exist_ok=True)
                        with open(destino, "wb") as f:
                            f.write(img_bytes)
                        print(f"  [IMAGEM] OK via Gemini ({model})")
                        return True
            except Exception as e:
                print(f"  [GEMINI] {model}: {e}")
                continue
    except Exception as e:
        print(f"  [GEMINI] erro geral: {e}")
    return False


def _gerar_gemini_legacy(prompt, destino, api_key, largura, altura, genai):
    """Fallback para SDK legado google-generativeai."""
    try:
        genai.configure(api_key=api_key)
        for model in GEMINI_MODELS:
            try:
                m = genai.GenerativeModel(model)
                resp = m.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        response_modalities=["IMAGE", "TEXT"],
                        temperature=0.7,
                    ),
                )
                for part in resp.parts:
                    if hasattr(part, "inline_data") and part.inline_data:
                        img_data = part.inline_data.data
                        if isinstance(img_data, str):
                            img_data = base64.b64decode(img_data)
                        os.makedirs(os.path.dirname(destino), exist_ok=True)
                        with open(destino, "wb") as f:
                            f.write(img_data)
                        print(f"  [IMAGEM] OK via Gemini legacy ({model})")
                        return True
            except Exception as e:
                print(f"  [GEMINI legacy] {model}: {e}")
                continue
    except Exception as e:
        print(f"  [GEMINI legacy] erro: {e}")
    return False


# ============================================================
# GERADOR 2: POLLINATIONS (gratuito, sem chave)
# ============================================================

def _gerar_pollinations(prompt, destino, largura=900, altura=500, modelo="flux"):
    """Gera imagem via Pollinations. Retorna True se sucesso."""
    url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt)
    url += f"?width={largura}&height={altura}&nologo=true&model={modelo}"
    try:
        r = requests.get(url, timeout=120)
        r.raise_for_status()
        if r.headers.get("content-type", "").startswith("image"):
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            with open(destino, "wb") as f:
                f.write(r.content)
            print(f"  [IMAGEM] OK via Pollinations ({modelo})")
            return True
    except Exception as e:
        print(f"  [POLLINATIONS] {modelo}: {e}")
    return False


def _gerar_pollinations_img2img(prompt_graf, img_url, destino, largura=900, altura=500):
    """Gera graffiti via Pollinations img2img. Retorna True se sucesso."""
    for modelo in MODELOS_GRAFFITI:
        url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt_graf)
        url += f"?width={largura}&height={altura}&nologo=true&model={modelo}"
        if img_url:
            url += "&image=" + urllib.parse.quote(img_url, safe="")
        try:
            r = requests.get(url, timeout=120)
            r.raise_for_status()
            if r.headers.get("content-type", "").startswith("image"):
                os.makedirs(os.path.dirname(destino), exist_ok=True)
                with open(destino, "wb") as f:
                    f.write(r.content)
                print(f"  [IMAGEM] OK via Pollinations graffiti ({modelo})")
                return True
        except Exception as e:
            print(f"  [POLLINATIONS graffiti] {modelo}: {e}")
    return False


# ============================================================
# GERADOR 3: AI HORDE (crowdsourced, ultimo fallback)
# ============================================================

def _gerar_ai_horde(prompt, destino, largura=900, altura=500):
    """Gera imagem via AI Horde (gratuito, crowdsourced, lento)."""
    try:
        payload = {
            "prompt": prompt,
            "params": {
                "width": largura,
                "height": altura,
                "steps": 30,
                "cfg_scale": 7.5,
                "sampler_name": "k_euler_a",
                "n": 1,
            },
            "nsfw": False,
            "censor_nsfw": True,
            "models": ["stable_diffusion"],
        }
        headers = {"Content-Type": "application/json", "apikey": "0000000000"}

        r = requests.post(
            "https://aihorde.net/api/v2/generate/async",
            json=payload,
            headers=headers,
            timeout=30,
        )
        r.raise_for_status()
        job_id = r.json().get("id")
        if not job_id:
            print("  [AI HORDE] sem job id")
            return False

        print(f"  [AI HORDE] job {job_id}, aguardando...")
        for _ in range(60):
            time.sleep(5)
            check = requests.get(
                f"https://aihorde.net/api/v2/generate/check/{job_id}",
                timeout=10,
            ).json()
            if check.get("done"):
                break
            if check.get("faulted"):
                print("  [AI HORDE] job falhou")
                return False

        result = requests.get(
            f"https://aihorde.net/api/v2/generate/status/{job_id}",
            timeout=30,
        ).json()
        generations = result.get("generations", [])
        if generations and generations[0].get("img"):
            img_url = generations[0]["img"]
            if img_url.startswith("http"):
                img_data = requests.get(img_url, timeout=60).content
            else:
                img_data = base64.b64decode(img_url)
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            with open(destino, "wb") as f:
                f.write(img_data)
            print("  [IMAGEM] OK via AI Horde")
            return True
    except Exception as e:
        print(f"  [AI HORDE] {e}")
    return False


# ============================================================
# FUNCAO PRINCIPAL - CADEIA DE FALLBACK
# ============================================================

def baixar_imagem(prompt, destino, largura=900, altura=500, imagem_orig=None, api_key=None):
    """Cadeia de fallback: Gemini -> Pollinations -> AI Horde.
    Se houver imagem_orig, tenta graffiti antes do texto->imagem."""
    os.makedirs(os.path.dirname(destino), exist_ok=True)

    # --- PASSO 1: Graffiti (se tiver imagem original) ---
    if imagem_orig:
        prompt_graf = gerar_prompt_graffiti(imagem_orig, "", "")
        print("  [GRAFFITI] tentando img2img...")

        # Graffiti: Pollinations (klein)
        if _gerar_pollinations_img2img(prompt_graf, imagem_orig, destino, largura, altura):
            return destino

    # --- PASSO 2: Texto->Imagem (cascata de geradores) ---
    tentativas = []

    # Gemini primeiro (se chave disponivel)
    if api_key:
        tentativas.append(("Gemini", lambda: _gerar_gemini(prompt, destino, api_key, largura, altura)))

    # Pollinations (flux, sana)
    for modelo in MODELOS_TEXTO:
        tentativas.append(
            (f"Pollinations-{modelo}",
             lambda m=modelo: _gerar_pollinations(prompt, destino, largura, altura, m))
        )

    # AI Horde (ultimo recurso)
    tentativas.append(("AI Horde", lambda: _gerar_ai_horde(prompt, destino, largura, altura)))

    for nome, gerar_fn in tentativas:
        print(f"  [TENTATIVA] {nome}...")
        if gerar_fn():
            return destino

    print("  [ERRO] nenhum gerador de imagem funcionou")
    return None


if __name__ == "__main__":
    prompt = gerar_prompt_imagem(
        "Prefeitura anuncia obras de pavimentacao no bairro Novo Horizonte",
        "Obras em Patos de Minas",
        "Local e Cidades",
    )
    print("Prompt:", prompt[:200])
    out = baixar_imagem(
        prompt,
        os.path.join(BASE_DIR, "assets", "images", "teste.jpg"),
        api_key=os.environ.get("GEMINI_API_KEY", ""),
    )
    print("Imagem gerada em:", out)
