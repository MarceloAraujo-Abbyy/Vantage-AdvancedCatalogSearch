from dataclasses import fields
import json
import logging
import os
import re
import azure.functions as func
from azure.storage.blob import BlobServiceClient
from rapidfuzz import process, fuzz
import time
import requests
import unicodedata
from  urllib.parse import quote

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

def get_vantage_token():
    global TOKEN_CACHE

    now = time.time()

    # usa cache se válido
    if TOKEN_CACHE["access_token"] and now < TOKEN_CACHE["expires_at"]:
        return TOKEN_CACHE["access_token"]

    url = os.getenv("ABBYY_AUTH_URL")
    client_id = os.getenv("ABBYY_CLIENT_ID")
    client_secret = os.getenv("ABBYY_CLIENT_SECRET")

    if not url or not client_id or not client_secret:
        raise Exception("Missing ABBYY auth environment variables")

    payload = {
        "grant_type": "client_credentials",
        "scope": "openid permissions global.wildcard",
        "client_id": client_id,
        "client_secret": client_secret
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    response = requests.post(url, data=payload, headers=headers)

    if response.status_code != 200:
        raise Exception(f"Token error: {response.text}")

    token_data = response.json()

    access_token = token_data["access_token"]
    expires_in = token_data.get("expires_in", 3600)

    # salva com margem de segurança (30s)
    TOKEN_CACHE["access_token"] = access_token
    TOKEN_CACHE["expires_at"] = now + expires_in - 30

    return access_token

def load_options(file_path):
    base_path = os.path.dirname(__file__)
    file_path = os.path.join(base_path, file_path)

    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def normalize(text, stopwords=None):
    if not text:
        return ""

    text = text.lower()
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r'[^a-z0-9 ]', ' ', text)

    if stopwords:
        for word in stopwords:
            pattern = r'\b' + re.escape(word.lower()) + r'\b'
            text = re.sub(pattern, '', text)

    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def find_candidatesCatalog(options, query, limit=10):
    norm_query = normalize(query)
    
    # Extrair apenas as strings normalizadas para o match
    normalized_strings = [h["normalized"] for h in options]
    
    results = process.extract(
        norm_query,
        normalized_strings,   # ← lista de strings, não dicts
        scorer=fuzz.WRatio,
        limit=limit
    )
    
    mapped = []
    for matched_str, score, index in results:  # ← 'index' agora é o índice real
        item = options[index]                  # ← recupera o dict original
        mapped.append({
            "name": item.get("original"),
            "score": round(score, 2),
            "data": item.get("data"),
            "id": item.get("id")
        })
    
    return mapped

def find_candidates(options, choices, query, limit=10):
    norm_query = normalize(query)

    results = process.extract(
        norm_query,
        choices,
        scorer=fuzz.WRatio,
        limit=limit
    )

    mapped = [
        {
            "name": options[r[2]]["original"],
            "score": round(r[1], 2)
        }
        for r in results
    ]

    return mapped

def find_candidatesCatalog_multi(options, query_fields: dict, limit=10):
    active_fields = {
        col: meta
        for col, meta in query_fields.items()
        if meta.get("value")
    }

    if not active_fields:
        return []

    total_weight = sum(meta["weight"] for meta in active_fields.values())
    if total_weight == 0:
        return []

    def smart_score(query: str, candidate: str) -> float:
        """
        Combina múltiplos scorers para diferenciar melhor candidatos parecidos.
        """
        w_ratio       = fuzz.WRatio(query, candidate)
        token_set     = fuzz.token_set_ratio(query, candidate)
        token_sort    = fuzz.token_sort_ratio(query, candidate)
        partial       = fuzz.partial_ratio(query, candidate)

        # Score base ponderado
        base = (
            w_ratio    * 0.35 +
            token_set  * 0.25 +
            token_sort * 0.25 +
            partial    * 0.15
        )

        # ✅ Bonus por tokens do query encontrados no candidato
        query_tokens     = set(query.split())
        candidate_tokens = set(candidate.split())
        matched_tokens   = query_tokens & candidate_tokens
        token_bonus      = (len(matched_tokens) / max(len(query_tokens), 1)) * 8  # até +8 pts

        return min(base + token_bonus, 100.0)

    scored = []
    for idx, item in enumerate(options):
        composite_score = 0.0

        for col, meta in active_fields.items():
            norm_query_value = normalize(meta["value"])
            weight = meta["weight"] / total_weight

            raw_value       = str(item.get("data", {}).get(col, ""))
            candidate_value = normalize(raw_value)

            if not candidate_value:
                continue

            field_score      = smart_score(norm_query_value, candidate_value)
            composite_score += field_score * weight

        scored.append((idx, round(composite_score, 2)))

    scored.sort(key=lambda x: x[1], reverse=True)
    scored = scored[:limit]

    return [
        {
            "name":  options[idx].get("original"),
            "score": score,
            "data":  options[idx].get("data"),
            "id":    options[idx].get("id")
        }
        for idx, score in scored
    ]

CATALOG_CACHE = {}
TOKEN_CACHE = {"access_token": None, "expires_at": 0}

def load_catalog_from_blob(file_name):
    # 🔥 cache
    if file_name in CATALOG_CACHE:
        return CATALOG_CACHE[file_name]

    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    container_name = os.getenv("BLOB_CONTAINER_NAME", "catalogs")

    if not conn_str:
        raise Exception("Missing AZURE_STORAGE_CONNECTION_STRING")

    blob_service_client = BlobServiceClient.from_connection_string(conn_str)
    blob_client = blob_service_client.get_blob_client(
        container=container_name,
        blob=file_name
    )

    data = blob_client.download_blob().readall()
    catalog = json.loads(data)

    # 🔥 salvar no cache
    CATALOG_CACHE[file_name] = catalog

    return catalog

@app.route(route="UploadCatalog")
def UploadCatalog(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()

        choices = body.get("choices", [])
        stopwords = body.get("stopwords", [])
        file_name = body.get("file_name", "catalog.json")

        if not choices or not isinstance(choices, list):
            return func.HttpResponse(
                json.dumps({"error": "Invalid 'choices' list"}),
                status_code=400,
                mimetype="application/json"
            )

        processed = [
            {
                "original": item,
                "normalized": normalize(item, stopwords)
            }
            for item in choices if item
        ]

        conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        container_name = os.getenv("BLOB_CONTAINER_NAME")

        if not conn_str:
            raise Exception("Missing AZURE_STORAGE_CONNECTION_STRING")
        if not container_name:
            raise Exception("Missing BLOB_CONTAINER_NAME")

        blob_service_client = BlobServiceClient.from_connection_string(conn_str)
        container_client = blob_service_client.get_container_client(container_name)

        # cria container se não existir
        try:
            container_client.create_container()
        except:
            pass

        # upload
        blob_client = container_client.get_blob_client(file_name)

        blob_client.upload_blob(
            json.dumps(processed, ensure_ascii=False),
            overwrite=True
        )

        return func.HttpResponse(
            json.dumps({
                "message": "Catalog uploaded successfully",
                "file": file_name,
                "count": len(processed)
            }),
            mimetype="application/json",
            status_code=200
        )

    except Exception as e:
        logging.exception("Error processing upload")

        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )

@app.route(route="UploadCatalogFromVantage")
def UploadCatalogFromVantage(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()

        catalog_name = body.get("catalog_name")
        key_column = body.get("key_column")
        file_name = body.get("file_name", f"{catalog_name}.json")
        stopwords = body.get("stopwords", [])

        if not catalog_name or not key_column:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'catalog_name' or 'key_column'"}),
                status_code=400,
                mimetype="application/json"
            )

        base_url = os.getenv("ABBYY_CATALOG_GET_URL")
        token = get_vantage_token()

        if not base_url:
            raise Exception("Missing ABBYY_CATALOG_GET_URL")

        all_records = []
        offset = 0
        limit = 1000

        while True:
            url = f"{base_url}/{catalog_name}/records"

            params = {
                "offset": offset,
                "limit": limit
            }

            headers = {
                "Authorization": f"Bearer {token}",
                "accept": "application/json"
            }

            response = requests.get(url, headers=headers, params=params)

            if response.status_code != 200:
                raise Exception(f"Error fetching catalog: {response.text}")

            records = response.json()

            if not records:
                break

            for r in records:
                fields = r.get("fields", {})
                original_list = fields.get(key_column, [])

                original = original_list[0] if original_list else None

                if not original:
                    continue
                
                clean_data = {
                    k: v[0] if isinstance(v, list) and v else None
                    for k, v in fields.items()
                }

                normalized_value = normalize(original, stopwords)
                if not normalized_value:
                    continue  # 🔥 ignora lixo

                all_records.append({
                    "original": original,
                    "normalized": normalized_value,
                    "data": clean_data,
                    "id": r.get("id")
                })

            offset += limit

        # Upload to Blob
        conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        container_name = os.getenv("BLOB_CONTAINER_NAME")

        blob_service_client = BlobServiceClient.from_connection_string(conn_str)
        container_client = blob_service_client.get_container_client(container_name)

        try:
            container_client.create_container()
        except:
            pass

        blob_client = container_client.get_blob_client(file_name)

        blob_client.upload_blob(
            json.dumps(all_records, ensure_ascii=False),
            overwrite=True
        )

        return func.HttpResponse(
            json.dumps({
                "message": "Catalog imported successfully from Vantage",
                "catalog": catalog_name,
                "file": file_name,
                "count": len(all_records)
            }),
            mimetype="application/json",
            status_code=200
        )

    except Exception as e:
        logging.exception("Error importing catalog")

        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )

@app.route(route="FuzzySearch")
def FuzzySearch(req: func.HttpRequest) -> func.HttpResponse:

    logging.info("Python HTTP trigger function processed a request.")
    try:
        body = req.get_json()

        ocr_text = body.get("text")
        limit = body.get("limit", 10)
        file_name = body.get("file_name")

        options = load_catalog_from_blob(file_name)
        choices = [h["normalized"] for h in options]

        if not ocr_text:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'text' parameter"}),
                status_code=400,
                mimetype="application/json"
            )
        if not file_name:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'file_name' parameter"}),
                status_code=400,
                mimetype="application/json"
            )

        try:
            limit = max(1, min(int(limit), 50))
        except:
            limit = 10

        candidates = find_candidates(options, choices, ocr_text, limit)

        response = {
            "input": ocr_text,
            "count": len(candidates),
            "candidates": candidates
        }

        return func.HttpResponse(
            json.dumps(response),
            mimetype="application/json",
            status_code=200
        )

    except Exception as e:
        logging.exception("Error processing request")

        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )
    
@app.route(route="AdvCatalogSearch")
def AdvCatalogSearch(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("AdvCatalogSearch2 triggered")
    try:
        body = req.get_json()
        file_name   = body.get("file_name")
        limit       = body.get("limit", 1)
        query_fields = body.get("fields")  # 

        # validations
        if not file_name:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'file_name'"}),
                status_code=400, mimetype="application/json"
            )

        if not query_fields or not isinstance(query_fields, dict):
            return func.HttpResponse(
                json.dumps({"error": "'fields' must be a dict like: {\"Account Name\": {\"value\": \"...\", \"weight\": 0.6}}"}),
                status_code=400, mimetype="application/json"
            )

        # each field must have 'value' and 'weight'
        for col, meta in query_fields.items():
            if not isinstance(meta, dict) or "value" not in meta or "weight" not in meta:
                return func.HttpResponse(
                    json.dumps({"error": f"Field '{col}' must have 'value' and 'weight'"}),
                    status_code=400, mimetype="application/json"
                )
            try:
                query_fields[col]["weight"] = float(meta["weight"])
            except (ValueError, TypeError):
                return func.HttpResponse(
                    json.dumps({"error": f"Field '{col}': 'weight' must be a number"}),
                    status_code=400, mimetype="application/json"
                )

        try:
            limit = max(1, min(int(limit), 50))
        except:
            limit = 1

        options = load_catalog_from_blob(file_name)
        if not options:
            return func.HttpResponse(
                json.dumps({"records": []}),
                mimetype="application/json", status_code=200
            )

        # find candidates
        candidates = find_candidatesCatalog_multi(options, query_fields, limit=limit)

        records = [
            {
                "externalId":   c.get("id"),
                "score":        c.get("score"),
                "columnValues": c.get("data", {})
            }
            for c in candidates
        ]

        return func.HttpResponse(
            json.dumps({
                "input":   query_fields,
                "count":   len(records),
                "records": records
            }),
            mimetype="application/json", status_code=200
        )

    except Exception as e:
        logging.exception("Error in AdvCatalogSearch")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500, mimetype="application/json"
        )