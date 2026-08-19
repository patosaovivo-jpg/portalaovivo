"""
Busca as páginas mais acessadas no Google Analytics 4.
Gera data/popular.json para exibir "Mais Lidas" na home.

Requer o secret GA_SERVICE_ACCOUNT (JSON da conta de serviço)
e GA_PROPERTY_ID (ID da propriedade GA4, ex: 435987654).
"""
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def buscar_paginas_populares(dias=7, limite=10):
    """Retorna lista de dicts [{path, titulo, visualizacoes}, ...]."""
    service_account_json = os.environ.get("GA_SERVICE_ACCOUNT", "").strip()
    property_id = os.environ.get("GA_PROPERTY_ID", "").strip()

    if not service_account_json:
        print("[ANALYTICS] GA_SERVICE_ACCOUNT nao definido. Pulando.")
        return []

    if not property_id:
        print("[ANALYTICS] GA_PROPERTY_ID nao definido. Pulando.")
        return []

    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import (
            DateRange,
            Dimension,
            Metric,
            RunReportRequest,
        )
        from google.oauth2 import service_account as sa
    except ImportError:
        print("[ANALYTICS] Dependencias nao instaladas. Pulando.")
        return []

    try:
        info = json.loads(service_account_json)
        # GitHub Actions armazena \n como literal, nao como nova linha
        if "private_key" in info:
            info["private_key"] = info["private_key"].replace("\\n", "\n")
        credentials = sa.Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/analytics.readonly"],
        )
        client = BetaAnalyticsDataClient(credentials=credentials)

        request = RunReportRequest(
            property=f"properties/{property_id}",
            date_ranges=[DateRange(start_date=f"{dias}daysAgo", end_date="today")],
            dimensions=[Dimension(name="pagePath"), Dimension(name="pageTitle")],
            metrics=[Metric(name="screenPageViews")],
            order_bys=[
                {"metric": {"metric_name": "screenPageViews"}, "desc": True}
            ],
            limit=limite,
        )

        response = client.run_report(request)

        resultados = []
        for row in response.rows:
            path = row.dimension_values[0].value
            titulo = row.dimension_values[1].value
            views = int(row.metric_values[0].value)
            if path and path != "/" and views > 0:
                resultados.append({
                    "path": path,
                    "titulo": titulo.split(" | ")[0].strip() if titulo else "",
                    "visualizacoes": views,
                })

        print(f"[ANALYTICS] {len(resultados)} paginas populares encontradas.")
        return resultados

    except Exception as e:
        print(f"[ANALYTICS] Erro ao buscar dados: {e}")
        return []


def salvar_popular(dias=7, limite=10):
    """Busca e salva em data/popular.json."""
    resultados = buscar_paginas_populares(dias=dias, limite=limite)
    destino = os.path.join(BASE_DIR, "_data", "popular.json")
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, "w", encoding="utf-8") as f:
        json.dump({"atualizado": __import__("datetime").datetime.utcnow().isoformat() + "Z",
                    "mais_lidas": resultados}, f, ensure_ascii=False, indent=2)
    print(f"[ANALYTICS] Salvo em {destino}")
    return resultados


if __name__ == "__main__":
    salvar_popular()
