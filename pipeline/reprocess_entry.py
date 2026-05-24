#!/usr/bin/env python3
"""
Re-process a specific failed entry in a daily diet file.

Finds an entry by client_id, re-runs Claude extraction on its raw_texts,
patches the components in-place, and writes back to S3.

Usage:
    python pipeline/reprocess_entry.py --date 2026-05-22 --id 634c0c9c-60cd-4b51-beb6-e63b680e3cf6
"""
import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import boto3

BUCKET = "ctbus-health-data"
MODEL = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
USDA_API_KEY = "fzjxJGoTfAqe0Kjx1t2SkcgzjtsNWqCjWrqiXxWy"
TAVILY_API_KEY = "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"

ET = ZoneInfo("America/New_York")

s3 = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

_usda_food_cache: dict[int, dict] = {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Date of the entry, e.g. 2026-05-22")
    parser.add_argument("--id", required=True, dest="client_id", help="client_id / message_id of the entry to re-process")
    args = parser.parse_args()

    key = f"diet/{args.date}.json"
    print(f"Reading s3://{BUCKET}/{key} ...")
    obj = s3.get_object(Bucket=BUCKET, Key=key)
    daily = json.loads(obj["Body"].read())

    target = None
    for entry in daily["entries"]:
        if args.client_id in entry.get("message_ids", []):
            target = entry
            break

    if not target:
        print(f"Entry {args.client_id} not found in {args.date}")
        sys.exit(1)

    raw_texts = target.get("raw_texts", [])
    print(f"Found entry: {args.client_id}")
    print(f"  raw_texts: {raw_texts}")
    print(f"  current components: {len(target.get('components', []))}")

    if not raw_texts:
        print("No raw_texts to re-process")
        sys.exit(1)

    print("Re-running extraction...")
    components = _extract_components(raw_texts)
    print(f"Got {len(components)} components")

    for c in components:
        total_kcal = (c.get("nutrition_total") or {}).get("calories_kcal")
        print(f"  - {c['name']}: {c.get('quantity_g')}g  ~{total_kcal:.0f} kcal" if total_kcal else f"  - {c['name']}: {c.get('quantity_g')}g")

    target["components"] = components
    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=json.dumps(daily, indent=2),
        ContentType="application/json",
    )
    print(f"Written back to s3://{BUCKET}/{key}")


# ── USDA ──────────────────────────────────────────────────────────────────────

def _fetch_usda_food(fdc_id: int) -> dict:
    if fdc_id in _usda_food_cache:
        return _usda_food_cache[fdc_id]
    params = urllib.parse.urlencode({"api_key": USDA_API_KEY})
    url = f"https://api.nal.usda.gov/fdc/v1/food/{fdc_id}?{params}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        _usda_food_cache[fdc_id] = data
        return data
    except Exception:
        _usda_food_cache[fdc_id] = {}
        return {}


def _nm_from_detail(detail: dict) -> dict:
    nm: dict = {}
    for n in detail.get("foodNutrients", []):
        if "nutrient" in n:
            name, value = n["nutrient"].get("name", ""), n.get("amount")
        elif "nutrientName" in n:
            name, value = n.get("nutrientName", ""), n.get("value")
        else:
            continue
        if name and value is not None and name not in nm:
            nm[name] = value
    return nm


def _search_usda(query: str) -> dict:
    params = urllib.parse.urlencode({
        "query": query,
        "dataType": "Foundation,SR Legacy",
        "pageSize": 3,
        "api_key": USDA_API_KEY,
    })
    url = f"https://api.nal.usda.gov/fdc/v1/foods/search?{params}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        foods = data.get("foods", [])
        if not foods:
            return {"found": False, "query": query}
        f = foods[0]
        fdc_id = f.get("fdcId")
        detail = _fetch_usda_food(fdc_id)
        nm = _nm_from_detail(detail) if detail else {n["nutrientName"]: n["value"] for n in f.get("foodNutrients", [])}
        kcal = nm.get("Energy") or nm.get("Energy (Atwater General Factors)") or nm.get("Energy (Atwater Specific Factors)")
        serving_size = detail.get("servingSize") if detail else None
        serving_unit = (detail.get("servingSizeUnit") or "g").upper() if detail else "G"
        return {
            "found": True,
            "name": (detail.get("description") or f.get("description", "")).strip(),
            "fdc_id": fdc_id,
            "serving_size_g": round(serving_size, 1) if serving_size and serving_unit == "G" else None,
            "nutrition_per_100g": {
                "calories_kcal": kcal,
                "protein_g": nm.get("Protein"),
                "total_fat_g": nm.get("Total lipid (fat)"),
                "saturated_fat_g": nm.get("Fatty acids, total saturated"),
                "monounsaturated_fat_g": nm.get("Fatty acids, total monounsaturated"),
                "polyunsaturated_fat_g": nm.get("Fatty acids, total polyunsaturated"),
                "omega3_g": nm.get("Fatty acids, total omega-3"),
                "trans_fat_g": nm.get("Fatty acids, total trans"),
                "total_carbohydrate_g": nm.get("Carbohydrate, by difference"),
                "fiber_g": nm.get("Fiber, total dietary"),
                "sugar_g": nm.get("Sugars, total including NLEA") or nm.get("Sugars, total"),
                "added_sugar_g": nm.get("Sugars, added"),
                "cholesterol_mg": nm.get("Cholesterol"),
                "sodium_mg": nm.get("Sodium, Na"),
                "potassium_mg": nm.get("Potassium, K"),
                "calcium_mg": nm.get("Calcium, Ca"),
                "iron_mg": nm.get("Iron, Fe"),
                "magnesium_mg": nm.get("Magnesium, Mg"),
                "zinc_mg": nm.get("Zinc, Zn"),
                "vitamin_a_ug": nm.get("Vitamin A, RAE"),
                "vitamin_c_mg": nm.get("Vitamin C, total ascorbic acid"),
                "vitamin_d_ug": nm.get("Vitamin D (D2 + D3)") or nm.get("Vitamin D"),
                "vitamin_b12_ug": nm.get("Vitamin B-12"),
                "folate_ug": nm.get("Folate, total") or nm.get("Folate, DFE"),
            },
        }
    except Exception as e:
        return {"found": False, "error": str(e), "query": query}


# ── unit conversion ────────────────────────────────────────────────────────────

_WEIGHT_TO_G: dict[str, float] = {
    "g": 1.0, "gram": 1.0, "grams": 1.0,
    "kg": 1000.0, "kilogram": 1000.0, "kilograms": 1000.0,
    "oz": 28.3495, "ounce": 28.3495, "ounces": 28.3495,
    "lb": 453.592, "pound": 453.592, "pounds": 453.592, "lbs": 453.592,
}

_VOL_TO_ML: dict[str, float] = {
    "ml": 1.0, "milliliter": 1.0, "milliliters": 1.0,
    "tsp": 4.92892, "teaspoon": 4.92892, "teaspoons": 4.92892,
    "tbsp": 14.7868, "tablespoon": 14.7868, "tablespoons": 14.7868,
    "cup": 236.588, "cups": 236.588,
    "fl oz": 29.5735, "floz": 29.5735,
}

_LIQUID_DENSITY: dict[str, float] = {
    "water": 1.0, "milk": 1.03, "oil": 0.91, "coffee": 1.0,
}


def _convert_food_unit(amount: float, from_unit: str, food_name: str) -> dict:
    u = from_unit.lower().strip()
    if u in _WEIGHT_TO_G:
        return {"grams": round(amount * _WEIGHT_TO_G[u], 1), "method": "weight_conversion"}
    if u in _VOL_TO_ML:
        ml = amount * _VOL_TO_ML[u]
        food_lower = food_name.lower()
        for key, density in _LIQUID_DENSITY.items():
            if key in food_lower:
                return {"grams": round(ml * density, 1), "method": f"liquid_density:{key}"}
        return {"grams": round(ml, 1), "method": "assumed_water_density"}
    return {"error": f"Unknown unit '{from_unit}'"}


# ── restaurant lookup ─────────────────────────────────────────────────────────

def _search_restaurant_menu(restaurant_name: str, location: str, items: list[str]) -> dict:
    query = f"{restaurant_name} {location} menu nutrition calories"
    if items:
        query += " " + ", ".join(items[:3])
    req_data = json.dumps({"query": query, "search_depth": "basic", "include_answer": True, "max_results": 5}).encode()
    req = urllib.request.Request(
        "https://api.tavily.com/search",
        data=req_data,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {TAVILY_API_KEY}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        return {
            "found": True,
            "answer": data.get("answer", ""),
            "results": [
                {"title": r["title"], "url": r["url"], "content": r["content"][:600]}
                for r in data.get("results", [])[:5]
            ],
        }
    except Exception as e:
        return {"found": False, "error": str(e)}


# ── Claude agentic loop ───────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a nutrition tracking assistant. Parse food log entries into structured nutritional data.

TEXT ITEMS: Free-text descriptions of food. For these:
  - For whole foods and generic ingredients: call search_usda per main ingredient, then estimate totals.
  - When the text names a specific restaurant AND location: call search_restaurant_menu; set source to "restaurant".
  - Use your knowledge to estimate when tools return no result.

Sanity-check before outputting: verify (nutrition_per_100g.calories_kcal × quantity_g / 100) is plausible:
  - Half a sandwich: 250–500 kcal. Full restaurant entrée: 400–900 kcal. Side dish: 50–300 kcal.

You MUST respond with ONLY this JSON object — no markdown fences, no prose, no explanation, nothing before { or after }:
{
  "components": [
    {
      "name": "descriptive name",
      "quantity_g": 355,
      "source": "usda" | "restaurant" | "claude_estimate",
      "nutrition_per_100g": {
        "calories_kcal": 0, "protein_g": 0, "total_fat_g": 0,
        "saturated_fat_g": null, "monounsaturated_fat_g": null, "polyunsaturated_fat_g": null,
        "omega3_g": null, "trans_fat_g": null, "total_carbohydrate_g": 0,
        "fiber_g": null, "sugar_g": null, "added_sugar_g": null, "starch_g": null,
        "cholesterol_mg": null, "sodium_mg": null, "potassium_mg": null,
        "calcium_mg": null, "iron_mg": null, "magnesium_mg": null, "zinc_mg": null,
        "vitamin_a_ug": null, "vitamin_c_mg": null, "vitamin_d_ug": null,
        "vitamin_b12_ug": null, "folate_ug": null
      }
    }
  ]
}

NEVER ask for clarification. NEVER output anything except the JSON object.\
"""

TOOLS = [
    {
        "toolSpec": {
            "name": "search_usda",
            "description": "Search USDA FoodData Central by food name. Best for whole foods and ingredients. Returns nutrition per 100g.",
            "inputSchema": {"json": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
        }
    },
    {
        "toolSpec": {
            "name": "convert_food_unit",
            "description": "Convert a measured food quantity to grams. Use for volume/weight units like tbsp, cup, oz.",
            "inputSchema": {"json": {"type": "object", "properties": {
                "amount": {"type": "number"},
                "from_unit": {"type": "string"},
                "food_name": {"type": "string"},
            }, "required": ["amount", "from_unit", "food_name"]}},
        }
    },
    {
        "toolSpec": {
            "name": "search_restaurant_menu",
            "description": "Look up a specific restaurant's menu items and nutritional info. Use when input names a specific restaurant AND location.",
            "inputSchema": {"json": {"type": "object", "properties": {
                "restaurant_name": {"type": "string"},
                "location": {"type": "string"},
                "items": {"type": "array", "items": {"type": "string"}},
            }, "required": ["restaurant_name", "location", "items"]}},
        }
    },
]


def _extract_components(texts: list[str]) -> list[dict]:
    messages = [{"role": "user", "content": [{"text": "\n".join(texts)}]}]

    for _ in range(12):
        response = bedrock.converse(
            modelId=MODEL,
            system=[{"text": SYSTEM_PROMPT}],
            messages=messages,
            toolConfig={"tools": TOOLS},
        )
        stop_reason = response["stopReason"]
        output = response["output"]["message"]
        if not output.get("content"):
            break
        messages.append(output)

        if stop_reason == "end_turn":
            retrying = False
            for block in output["content"]:
                if "text" in block:
                    try:
                        text = block["text"].strip()
                        if "```" in text:
                            text = text.split("```")[1].lstrip("json").strip()
                        parsed = json.loads(text)
                        comps = parsed if isinstance(parsed, list) else parsed.get("components", [])
                        return _compute_totals([c for c in comps if isinstance(c, dict)])
                    except (json.JSONDecodeError, IndexError, KeyError) as e:
                        print(f"  parse error: {e}, raw: {block['text'][:300]}")
                        messages.append({"role": "user", "content": [{"text": 'Your response was not valid JSON. Output ONLY the JSON object — no markdown, no prose, no explanation. Start with { and end with }.'}]})
                        retrying = True
                        break
            if not retrying:
                return []

        if stop_reason == "tool_use":
            tool_results = []
            for block in output["content"]:
                if "toolUse" in block:
                    tool = block["toolUse"]
                    result = _call_tool(tool["name"], tool["input"])
                    found = result.get("found", "?")
                    print(f"  tool {tool['name']}({tool['input']}) -> {found}")
                    tool_results.append({
                        "toolResult": {
                            "toolUseId": tool["toolUseId"],
                            "content": [{"json": result}],
                        }
                    })
            if not tool_results:
                break
            messages.append({"role": "user", "content": tool_results})

    print("  max rounds exceeded")
    return []


def _call_tool(name: str, inp: dict) -> dict:
    if name == "search_usda":
        return _search_usda(inp["query"])
    if name == "convert_food_unit":
        return _convert_food_unit(inp["amount"], inp["from_unit"], inp["food_name"])
    if name == "search_restaurant_menu":
        return _search_restaurant_menu(inp["restaurant_name"], inp["location"], inp.get("items", []))
    return {"error": f"Unknown tool: {name}"}


def _compute_totals(components: list[dict]) -> list[dict]:
    for c in components:
        per_100 = c.get("nutrition_per_100g", {})
        qty = c.get("quantity_g") or 0
        if qty and per_100:
            c["nutrition_total"] = {
                k: round(v * qty / 100, 2) if v is not None else None
                for k, v in per_100.items()
            }
    return components


if __name__ == "__main__":
    main()
