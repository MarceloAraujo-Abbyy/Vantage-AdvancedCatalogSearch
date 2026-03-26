# 📘 How to Use the Catalog Matching API with ABBYY Vantage

This guide explains how to:

* Create and upload catalogs
* Use the search API
* Integrate with ABBYY Vantage

---

# 🧠 Overview

The API provides two ways to search. 
- Simple Match: Upload and search any Catalog;
- Vantage Catalog Match: Reads and search the catalog directly from Vantage.

The API provides four main endpoints:

## 1. Upload Catalog 

Creates a normalized dataset stored in Azure Blob Storage.

## 2. Upload Catalog From Vantage

Reads the Vantage Catalog and creates a normalized dataset stored in Azure Blob Storage.

## 3. Fuzzy Search 

Receives the result OCR text as parameter and returns the best matching candidates.

## 4. Advanced Search Catalog

Receives OCR text, finds the best matching based in defined weights and return the best matched catalog record.

---

# 📤 1. Upload Catalog

## Endpoint

```
POST /api/UploadCatalog
```

## Purpose

* Accept a list of names
* Normalize and preprocess data
* Store as JSON in Azure Blob Storage

---

## Request Example

```json
{
  "choices": [
    "Global Tech Solutions Ltd",
    "Advanced Medical Supplies Inc",
    "Prime Industrial Equipment Co"
  ],
  "stopwords": [
    "ltd",
    "inc",
    "llc",
    "co",
    "company",
    "services",
    "solutions"
  ],
  "file_name": "vendors_catalog.json"
}
```

---

## Parameters

| Field     | Type   | Required | Description                             |
| --------- | ------ | -------- | --------------------------------------- |
| choices   | array  | ✅        | List of names to include in the catalog |
| stopwords | array  | ❌        | Words to remove during normalization    |
| file_name | string | ✅        | Output file name stored in Blob         |

---

## What Happens

Each item is transformed into:

```json
{
  "original": "Global Tech Solutions Ltd",
  "normalized": "global tech"
}
```

---

## Response Example

```json
{
  "message": "Catalog uploaded successfully",
  "file": "vendors_catalog.json",
  "count": 3
}
```

---

# 📤 2. Upload Catalog From Vantage

## Endpoint

```
POST /api/UploadCatalogFromVantage
```

## Purpose

* Load records from Vantage Catalog
* Normalize and preprocess data for Key Field
* Store as JSON in Azure Blob Storage

---

## Request Example

```json
{
  "catalog_name": "Vendors",
  "key_column": "Vendor Name",
  "file_name": "Vendors.json",
  "stopwords": ["LLC","Company"]
}
```

---

## Parameters

| Field        | Type    | Required   | Description                             |
| ------------ | ------  | ---------- | --------------------------------------- |
| catalog_name | string  | ✅        | Catalog name in Vantage                 |
| key_column   | string  | ✅        | field used for search                   |
| file_name    | string  | ✅        | Output file name stored in Blob         |
| stopwords    | array   | ❌        | Words to remove during normalization    |


---

## What Happens

Each record in catalod is transformed into:

```json
{
    "original": "Company Global Tech LLC",
    "normalized": "global tech",
    "data": {
      "Account Name": "Company Global Tech LLC",
      "City": "Miami",
      "State": "FL",
      "Postal Code": "34672"
    },
    "id": "98d218ad-6ad8-4ea8-8bd7-b47484c77082"
  }
```

---

## Response Example

```json
{
    "message": "Catalog imported successfully from Vantage",
    "catalog": "Vendors",
    "file": "Vendors.json",
    "count": 678
}
```

---

# 🔍 3. Fuzzy Search

## Endpoint

```
GET /api/FuzzySearch
```

---

## Purpose

* Receive OCR text
* Retrieve catalog from Blob Storage
* Return best matching candidates

---

## Request Example

```json
{
  "text": "global tech solutons",
  "limit": 2,
  "file_name": "vendors_catalog.json"
}
```

---

## Parameters

| Field     | Type   | Required | Description                            |
| --------- | ------ | -------- | -------------------------------------- |
| text      | string | ✅        | OCR extracted text                     |
| limit     | number | ❌        | Max number of candidates (default: 10) |
| file_name | string | ✅        | Catalog file stored in Blob            |

---

## Response Example

```json
{
  "input": "global tech solutons",
  "file": "vendors_catalog.json",
  "count": 2,
  "candidates": [
    {
      "name": "Global Tech Solutions Ltd",
      "score": 92.4
    },
    {
      "name": "OmniTech IT Solutions",
      "score": 81.2
    }
  ]
}
```

---

# ⚙️ How It Works

1. Input text is normalized
2. Fuzzy matching is applied
3. Top candidates are returned

---


# 🔍 4. Advanced Search Catalog

## Endpoint

```
GET /api/AdvSearchCatalog
```

---

## Purpose

* Receive OCR text
* Retrieve catalog from Blob Storage
* Find the best matching candidate based in the weights
* Returns the related Vantage Catalog Record

---

## Request Example

```json
{

  "file_name": "vendors.json",
  "limit":2,
  "fields": {
    "Account Name": { "value": "Global tech LLC ", "weight": 0.7 },
    "State":        { "value": "FL","weight": 0.3 }
  }
```
  or using only one parameter
```json
  {

  "file_name": "Accounts.json",
  "limit":1,
  "fields": {
    "Account Name": { "value": " Atrium Health Navicent ", "weight": 1 }
  }
}

}

```

---

## Parameters

| Field        | Type   | Required | Description                                                      |
| ------------ | ------ | -------- | ---------------------------------------------------------------- |
| fields       | array  | ✅       | OCR extracted text plus weight for each field                    |
| file_name    | string | ✅       | Catalog file stored in Blob                                      |
| limit        | intger | ❌       | default = 1                                                      |

---

## Response Example

```json
{
    {
    "input": {
        "Account Name": {
            "value": " Global Tech LLC ",
            "weight": 0.7
        },
        "State": {
            "value": "FL",
            "weight": 0.3
        }
    },
    "count": 1,
    "records": [
        {
            "externalId": "2db87539-7a33-4b9b-84dc-cda41cf2f21d",
            "score": 85.63,
            "columnValues": {
                "Account Name": "Global Technology Company LLC",
                "City": "Miami",
                "State": "FL",
                "Postal Code": "34712"
            }
        },
}
```

---

# ⚙️ How It Works

1. Input text is normalized
2. Fuzzy matching and weights is applied
3. Top candidate are returned
4. Get data from normalized JSON in Blob
5. Return the vatalog record




# ⚙️ # Fuzzy Matching Scorers Explained

> **Input:** `"global tech"`  
> **Candidates:** Global Technology Inc, Global Technical Services, Digital Tech Global

---

## Why combine scorers?

One scorer sees the text from one angle only. Combining them fills each other's blind spots.

---

## The Scorers

**`WRatio`** — general similarity, handles typos
```
"global tech"  vs  "Global Technology Inc"      → 88
"global tech"  vs  "Global Technical Services"  → 88   ← can't tell apart
```

**`token_sort_ratio`** — sorts words alphabetically before comparing
```
"global tech"  vs  "global technology"   → high  ✅  (tech ≈ technology)
"global tech"  vs  "global technical"    → high  ✅  (tech ≈ technical)
"global tech"  vs  "digital global tech" → lower ❌  (word order noise removed)
```

**`token_set_ratio`** — ignores extra words, focuses on shared tokens
```
"global tech"  vs  "Global Technology Inc"
→ focuses on "global tech", ignores "inc"  → high ✅

"global tech"  vs  "Digital Tech Global"
→ both words exist but reversed context   → medium
```

**`partial_ratio`** — checks if query fits as a substring
```
"global tech" inside "Global Technology Inc"     → fits naturally ✅
"global tech" inside "Digital Tech Global"       → doesn't slot in ❌
```

**`token_bonus`** *(custom)* — rewards exact token matches by users
```
"global tech" → tokens: [global, tech]

"Global Technology Inc"     → global ✅  tech~ ✅  → +8 pts
"Digital Tech Global"       → global ✅  tech  ✅  → +8 pts  (same)
"Global Technical Services" → global ✅  tech~ ✅  → +8 pts  (same)
```

---

## Final Scores

| Candidate                  | WRatio | token_sort | token_set | partial | bonus | **Final** |
|----------------------------|--------|------------|-----------|---------|-------|-----------|
| **Global Technology Inc**  | 88 | 90 | 92 | 91 | +8 | **~93** ✅ |
| Global Technical Services  | 88 | 85 | 87 | 83 | +8 | **~89** |
| Digital Tech Global        | 88 | 78 | 82 | 75 | +8 | **~85** |

---

## Summary

| Scorer         | Strength                            |
|----------------|-------------------------------------|
| `WRatio`       | General similarity + typo tolerance |
| `token_sort`   | Word presence regardless of order   |
| `token_set`    | Ignores filler words like "Inc"     |
| `partial_ratio`| Short query vs longer candidate     |
| `token_bonus`  | Breaks ties on exact token matches  |

---



# 🤖 Using with ABBYY Vantage


Create a Custom Activity on the Skill Process (after the extraction).

Sample API Call 

```js
const name = doc.GetField("Vendor/Name").Text;
const state = doc.GetField("Vendor/State").Text;
const myObject = {
      "file_name": "Accounts.json",
      "limit": 1,
        "fields": {
              "Account Name": { "value": name, "weight": 0.6 },
              "State":        { "value": state,"weight": 0.4 }
          }
  };
const data = AdvCatSearch(myObject);
const record = data.records[0];
doc.GetField("Vendor/Score").Value = record.score;
doc.GetField("Vendor/Name").Value = record.columnValues["Name"];
doc.GetField("Vendor/City").Value = record.columnValues["City"];
doc.GetField("Vendor/State").Value = record.columnValues["State"];
doc.GetField("Vendor/ZipCode").Value = record.columnValues["ZipCode"];

// Search Function
function AdvCatSearch(myObject) {

    try {
        // create request and get result text	
        const request = Context.CreateHttpRequest();
        request.Url = "https://<APP_NAME>>.azurewebsites.net/api/AdvCatalogSearch2?code=YOUR_CODE";
        request.Method = "POST";
        request.SetHeader("Content-Type", "application/json");
        request.SetStringContent(JSON.stringify(myObject));
        request.Send();
        var responseObject = JSON.parse(request.ResponseText);
        var ret = responseObject;
        return ret;

    } catch (error) {
        Context.ErrorMessage = `Error while fetching result: ${error.message}`;
    }	
}
```

## Step 1 — Call API (Web Service Skill)

### Request

```json
{
  "file_name": "vendors.json",
  "limit": 1,
  "fields": {
    "Account Name": { "value": "Global tech LLC ", "weight": 0.7 },
    "State":        { "value": "FL","weight": 0.3 }
  }
}
```

---

# 💡 Best Practices

## 1. Use Stopwords

Remove generic words such as:

* ltd
* inc
* company
* services
* solutions

## 2. Keep Catalog Clean

* Avoid duplicates
* Normalize naming conventions

## 3. Limit Candidates

Use 3–10 candidates for best performance

## 4. Cache Behavior

* First request loads from Blob
* Subsequent requests use memory cache

## 5. 🎯 Customize the fields and the weight dinamically! 🎯

Depending on the OCR Results customize the parameters. 
If state is founded, and it ia a valid US state, include as paramter to filter que records, including specific weight.


---

# ⚠️ Notes

* Catalog updates do not automatically invalidate cache
* Cache resets on function restart
* Blob storage is the source of truth

# ⚠️ Special Note 

* Even saving the correct values on the fields using a Custom Activity, the error message related to catalog match will disappear, since it's comes from extraction time. So, to clean any error message, the user need select the select the unique value to clean the message.

---

# 🚀 Summary

* Upload catalogs via API
* Store them in Blob Storage
* Query using OCR text
* Use results inside Vantage for final decision
* Eliminate search errors in catalogs
* Improve the straight-through processing 

---

# 📌 Example Flow

1. Upload vendor list
2. Process invoices in Vantage
3. Call search  customizing paramters
4. Send candidates to Vantage
5. Select final vendor (best or add as suggestions to a field)

---

# ☁️ Azure Setup Guide

This section explains how to deploy and configure the API in Azure.

Requirments:
- Azure subscription 
- Azure Functon 
- Azure Storage Account (Blob) 

---

## 🧩 1. Create Azure Function App

1. Go to Azure Portal
2. Click **Create Resource**
3. Select **Function App**
4. Choose:

   * Runtime: Python
   * Version: 3.10+ recommended

---

## 📦 2. Deploy Code

Using Azure CLI:

```
func azure functionapp publish <APP_NAME>
```

Using Visual Code

Download the code and use Azure Tab to publish.

---

## 📁 3. Configure Storage Account

1. Create or use an existing Storage Account
2. Go to:

   * **Access Keys**
3. Copy the **Connection String**

---

## ⚙️ 4. Configure Environment Variables

Go to:

```
Function App → Settings → Environment Variables
```

Add:

```
AZURE_STORAGE_CONNECTION_STRING = <your_connection_string>
BLOB_CONTAINER_NAME = catalogs
ABBYY_AUTH_URL = https://vantage-us.abbyy.com/auth2/<<tenant_id>>/connect/
ABBYY_CATALOG_FILTER_URL = https://vantage-us.abbyy.com/api/workspace/catalogs/
ABBYY_CATALOG_FILTER_URL = https://vantage-us.abbyy.com/api/publicapi/v1/catalogs/
ABBYY_CLIENT_ID = <<client id>>
ABBYY_CLIENT_SECRET = <<client secret>>
```

Click:

* Apply
* Save
* Restart the Function App

---

## 🧪 5. Test Endpoints

### Upload Catalog

```
POST https://<APP_NAME>.azurewebsites.net/api/UploadCatalog
```

curl --location 'https://<APP_NAME>.azurewebsites.net/api/UploadCatalog?code=<<Your Code>>' \
--header 'Content-Type: application/json' \
--data '{
  "choices": [
    "Global Tech Solutions Ltd",
    "Advanced Medical Supplies Inc",
    "Prime Industrial Equipment Co",
    "United Logistics Group LLC",
    "Alpha Construction Services"
  ],
  "stopwords": [
    "ltd",
    "inc",
    "llc",
    "co",
    "company",
    "corp"
  ],
  "file_name": "vendors.json"
}'

### Upload Catalog from Vantage

```
POST https://<APP_NAME>.azurewebsites.net/api/UploadCatalogFromVantage
```

curl --location 'https://<APP_NAME>.azurewebsites.net/api/UploadCatalogFromVantage?code=<YOUR_CODE>' \
--header 'Content-Type: application/json' \
--data '{
  "catalog_name": "Vendors",
  "key_column": "Vendor Name",
  "file_name": "Vendors.json",
  "stopwords": ["INC", "LLC"]
}'


### Fuzzy Match

```
GET https://<APP_NAME>.azurewebsites.net/api/FuzzySearch
```

curl --location 'https://<APP_NAME>.azurewebsites.net/api/FuzzySearch?code=<YOUR CODE>' \
--header 'Content-Type: application/json' \
--data '{
  "text": "GLobal Tech",
  "limit": 10,
  "file_name": "accounts.json"
}'

### Advanced Search Catalog

```
GET https://<APP_NAME>.azurewebsites.net/api/AdvCatalogSearch
```

curl --location 'https://<APP_NAME>.azurewebsites.net/api/AdvCatalogSearch?code=<<YOUR CODE>>' \
--header 'Content-Type: application/json' \
--data '  
  "file_name": "vendors.json",
  "limit": 1,
  "fields": {
    "Account Name": { "value": "Global tech LLC ", "weight": 0.7 },
    "State":        { "value": "FL","weight": 0.3 }
  }'

---

## 🔍 6. Verify Blob Storage

1. Go to Storage Account
2. Open **Containers**
3. Select container: `catalogs`
4. Confirm JSON file is uploaded

---

## ⚠️ Common Issues

| Issue                 | Cause                     | Fix                               |
| --------------------- | ------------------------- | --------------------------------- |
| NoneType rstrip error | Missing connection string | Set environment variable          |
| Function not found    | Wrong structure           | Use v2 model with function_app.py |
| Blob not found        | Wrong file_name           | Check request payload             |


---

## ⚠️ Disclaimer ⚠️

This application is provided strictly as a **proof of concept and demonstration purposes only**.

It is intended to showcase potential integration capabilities and is **not production-ready**. Prior to any production deployment, a thorough technical review, security assessment, and architectural validation must be conducted to ensure compliance with the target environment's requirements, performance expectations, and organizational standards.

**This solution is not an ABBYY product and is not supported by ABBYY in any capacity.** It has been developed as a reference implementation and does not carry any ABBYY service-level agreements, warranties, or official support commitments.

All maintenance, customization, operational support, and lifecycle management of this application are the **sole responsibility of the implementing organization**. ABBYY shall not be held liable for any issues, data loss, or damages arising from the use or misuse of this demonstration code in any environment.

> Organizations considering adopting this solution in a production context are strongly encouraged to engage their internal engineering and security teams for a comprehensive review before any live deployment.

