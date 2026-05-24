import json
import os
import io
import urllib.request
import urllib.parse
import boto3
from botocore.exceptions import ClientError
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# pyzbar + Pillow only available when the Lambda Layer is attached
try:
    from pyzbar.pyzbar import decode as _pyzbar_decode
    from PIL import Image as _PILImage
    _PYZBAR = True
except ImportError:
    _PYZBAR = False

s3 = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime")
ssm = boto3.client("ssm")

BUCKET = os.environ["BUCKET_NAME"]
BEDROCK_MODEL_ID = os.environ["BEDROCK_MODEL_ID"]
ET = ZoneInfo("America/New_York")
UTC = timezone.utc

_ssm_cache: dict = {}
_history_cache: list[dict] | None = None
_usda_food_cache: dict[int, dict] = {}  # fdcId → full food detail (nutrients + portions)

GROUP_WINDOW_SECONDS = 60


def _increment_usage(event_type: str, count: int = 1):
    """Increment a monthly usage counter in S3. Non-fatal. Safe at concurrency=1."""
    month = datetime.now(ET).strftime("%Y-%m")
    key = f"diet/usage/{month}.json"
    try:
        try:
            obj = s3.get_object(Bucket=BUCKET, Key=key)
            data = json.loads(obj["Body"].read())
        except ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "AccessDenied"):
                data = {}
            else:
                return
        data["month"] = month
        data[event_type] = data.get(event_type, 0) + count
        data["updated_at"] = datetime.now(UTC).isoformat()
        s3.put_object(Bucket=BUCKET, Key=key, Body=json.dumps(data), ContentType="application/json")
    except Exception as e:
        print(f"Usage tracking error ({event_type}): {e}")


def _get_param(name: str) -> str:
    if name not in _ssm_cache:
        _ssm_cache[name] = ssm.get_parameter(Name=name, WithDecryption=True)["Parameter"]["Value"]
    return _ssm_cache[name]


def lambda_handler(event, context):
    global _history_cache
    _history_cache = None  # refresh history each invocation
    messages = [json.loads(r["body"]) for r in event["Records"]]

    frontend_msgs          = [m for m in messages if m.get("source") == "frontend"]
    recipe_msgs            = [m for m in messages if m.get("source") == "recipe"]
    recipe_replace_msgs    = [m for m in messages if m.get("source") == "recipe_replace"]
    usage_event_msgs       = [m for m in messages if m.get("source") == "usage_event"]
    restaurant_lookup_msgs = [m for m in messages if m.get("source") == "restaurant_lookup"]
    item_prefetch_msgs     = [m for m in messages if m.get("source") == "item_prefetch"]
    telegram_msgs          = [m for m in messages if m.get("source") not in (
        "frontend", "recipe", "recipe_replace", "usage_event", "restaurant_lookup", "item_prefetch")]

    for msg in frontend_msgs:
        _process_frontend_entry(msg)
    for msg in recipe_msgs:
        _process_recipe(msg)
    for msg in recipe_replace_msgs:
        _process_recipe_replace(msg)
    for msg in usage_event_msgs:
        _process_usage_event(msg)
    for msg in restaurant_lookup_msgs:
        _process_restaurant_lookup(msg)
    for msg in item_prefetch_msgs:
        _process_item_prefetch(msg)

    telegram_msgs.sort(key=lambda m: m["timestamp"])
    for group in _group_by_proximity(telegram_msgs):
        _process_group(group)


def _group_by_proximity(messages: list[dict]) -> list[list[dict]]:
    if not messages:
        return []
    groups, current = [], [messages[0]]
    prev_ts = datetime.fromisoformat(messages[0]["timestamp"])
    for msg in messages[1:]:
        ts = datetime.fromisoformat(msg["timestamp"])
        if (ts - prev_ts).total_seconds() <= GROUP_WINDOW_SECONDS:
            current.append(msg)
        else:
            groups.append(current)
            current = [msg]
        prev_ts = ts
    groups.append(current)
    return groups


def _process_group(group: list[dict]):
    texts = [m["text"] for m in group if m.get("text") and not m["text"].startswith("/")]
    photo_keys = [m["photo_s3_key"] for m in group if m.get("photo_s3_key")]

    if not texts and not photo_keys:
        return

    first_ts = datetime.fromisoformat(group[0]["timestamp"])
    et_dt = first_ts.astimezone(ET)
    et_date = et_dt.date().isoformat()
    message_ids = [m["message_id"] for m in group]

    daily = _read_daily(et_date)
    processed_ids = {mid for e in daily["entries"] for mid in e["message_ids"]}
    if any(mid in processed_ids for mid in message_ids):
        print(f"Group {message_ids} already processed, skipping")
        return

    photos = []
    barcode_data: list[dict] = []
    for key in photo_keys:
        obj = s3.get_object(Bucket=BUCKET, Key=key)
        photo_bytes = obj["Body"].read()
        photos.append(photo_bytes)
        for bc in _extract_barcodes(photo_bytes):
            result = _lookup_openfoodfacts(bc)
            status = result["name"] if result.get("found") else "not found"
            print(f"Barcode {bc} -> {status}")
            barcode_data.append(result)

    components = _extract_components(texts, photos, barcode_data)

    entry = {
        "message_ids": message_ids,
        "timestamp": et_dt.isoformat(),
        "raw_texts": texts,
        "photo_s3_keys": photo_keys,
        "components": components,
    }

    daily["entries"].append(entry)
    daily["entries"].sort(key=lambda e: e["timestamp"])
    _write_daily(et_date, daily)
    print(f"Wrote {len(components)} components for group {message_ids} to diet/{et_date}.json")


def _process_frontend_entry(msg: dict):
    date = msg["date"]
    client_id = msg.get("client_id") or msg.get("message_id", "unknown")
    timestamp = msg.get("timestamp", datetime.now(ET).isoformat())

    daily = _read_daily(date)
    processed_ids = {mid for e in daily["entries"] for mid in e["message_ids"]}
    if client_id in processed_ids:
        print(f"Frontend entry {client_id} already processed, skipping")
        return

    items = msg.get("items", [])
    resolved_items = [it for it in items if it.get("source") in ("openfoodfacts", "history", "restaurant")]
    text_items = [it for it in items if it.get("source") == "text"]

    components: list[dict] = []

    for it in resolved_items:
        qty = it.get("quantity_g") or 0
        per100 = it.get("nutrition_per_100g") or {}
        comp: dict = {
            "name": it.get("name", "Unknown"),
            "quantity_g": qty,
            "source": it.get("source"),
            "nutrition_per_100g": per100,
        }
        if it.get("barcode"):
            comp["barcode"] = it["barcode"]
        if it.get("unit"):
            comp["unit"] = it["unit"]
        if it.get("quantity") is not None:
            comp["quantity"] = it["quantity"]
        components.append(comp)

    components = _compute_totals(components)

    if text_items:
        text_lines = []
        for it in text_items:
            qty_str = f"{it.get('quantity', 1)} {it.get('unit', 'serving')}"
            qty_g = it.get("quantity_g")
            if qty_g:
                qty_str += f" (~{round(qty_g)}g)"
            text_lines.append(f"{qty_str} {it.get('description', '')}")
        text_components = _extract_components(text_lines, [])  # already has totals
        components.extend(text_components)

    entry = {
        "message_ids": [client_id],
        "timestamp": timestamp,
        "raw_texts": [it.get("description", "") for it in text_items],
        "photo_s3_keys": [],
        "source": "frontend",
        "components": components,
    }

    daily["entries"].append(entry)
    daily["entries"].sort(key=lambda e: e["timestamp"])
    _write_daily(date, daily)
    print(f"Wrote {len(components)} frontend components for {client_id} to diet/{date}.json")


def _process_recipe(msg: dict):
    client_id = msg.get("client_id") or msg.get("message_id", str(uuid.uuid4()))
    name = msg.get("name") or "Unnamed Recipe"
    items = msg.get("items", [])
    saved_at = msg.get("date", datetime.now(ET).date().isoformat())

    recipes = _read_recipes()
    if any(r.get("id") == client_id for r in recipes):
        print(f"Recipe {client_id} already saved, skipping")
        return

    recipe = {"id": client_id, "name": name, "saved_at": saved_at, "items": items}
    recipes.append(recipe)
    _write_recipes(recipes)
    print(f"Saved recipe '{name}' ({len(items)} items) as {client_id}")


def _read_recipes() -> list:
    try:
        obj = s3.get_object(Bucket=BUCKET, Key="diet/recipes.json")
        return json.loads(obj["Body"].read())
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "AccessDenied"):
            return []
        raise


def _write_recipes(recipes: list):
    s3.put_object(
        Bucket=BUCKET,
        Key="diet/recipes.json",
        Body=json.dumps(recipes, indent=2),
        ContentType="application/json",
        CacheControl="no-cache",
    )


def _process_recipe_replace(msg: dict):
    recipes = msg.get("recipes", [])
    _write_recipes(recipes)
    print(f"Replaced full recipe list ({len(recipes)} recipes)")


# ── barcode extraction ────────────────────────────────────────────────────────

def _extract_barcodes(photo_bytes: bytes) -> list[str]:
    if not _PYZBAR:
        return []
    try:
        from PIL import ImageOps
        img = _PILImage.open(io.BytesIO(photo_bytes))
        # Try original, then rotations (handles barcodes on cylindrical cans),
        # then grayscale + autocontrast (handles glare on shiny packaging).
        attempts = [img, img.rotate(90, expand=True), img.rotate(270, expand=True),
                    img.rotate(180, expand=True)]
        gray = img.convert("L")
        attempts += [gray, ImageOps.autocontrast(gray)]
        for attempt in attempts:
            results = _pyzbar_decode(attempt)
            if results:
                return [r.data.decode("utf-8") for r in results if r.data]
        return []
    except Exception as e:
        print(f"pyzbar error: {e}")
        return []


# ── history context ───────────────────────────────────────────────────────────

def _get_history() -> list[dict]:
    global _history_cache
    if _history_cache is not None:
        return _history_cache
    entries = []
    today = datetime.now(ET).date()
    for i in range(7):
        date_str = (today - timedelta(days=i)).isoformat()
        data = _read_daily(date_str)
        entries.extend(data.get("entries", []))
    _history_cache = entries
    return entries


def _recent_items_hint() -> str:
    """One-liner injected into every prompt so the model can reference past items without calling search_history."""
    history = _get_history()
    seen: dict[str, str] = {}
    for entry in history:
        for comp in entry.get("components", []):
            name = comp.get("name", "")
            if name and name not in seen:
                seen[name] = comp.get("barcode", "")
    if not seen:
        return ""
    parts = []
    for name, barcode in list(seen.items())[:20]:
        s = f'"{name}"'
        if barcode:
            s += f" [barcode:{barcode}]"
        parts.append(s)
    return "Recently logged (last 7 days): " + ", ".join(parts)


def _search_history(query: str) -> dict:
    history = _get_history()
    q = query.lower()
    matches = []
    seen_names: set[str] = set()
    for entry in history:
        text_hit = any(q in t.lower() for t in entry.get("raw_texts", []))
        for comp in entry.get("components", []):
            name = comp.get("name", "")
            if (q in name.lower() or text_hit) and name not in seen_names:
                seen_names.add(name)
                result: dict = {
                    "name": name,
                    "logged_at": entry["timestamp"],
                    "source": comp.get("source", ""),
                    "nutrition_per_100g": comp.get("nutrition_per_100g", {}),
                }
                if comp.get("barcode"):
                    result["barcode"] = comp["barcode"]
                matches.append(result)
    return {"matches": matches[:5], "total_found": len(matches)}


# ── unit conversion ───────────────────────────────────────────────────────────

_WEIGHT_TO_G: dict[str, float] = {
    "g": 1.0, "gram": 1.0, "grams": 1.0,
    "kg": 1000.0, "kilogram": 1000.0, "kilograms": 1000.0,
    "oz": 28.3495, "ounce": 28.3495, "ounces": 28.3495,
    "lb": 453.592, "pound": 453.592, "pounds": 453.592, "lbs": 453.592,
}

_VOL_TO_ML: dict[str, float] = {
    "ml": 1.0, "milliliter": 1.0, "milliliters": 1.0, "millilitre": 1.0,
    "l": 1000.0, "liter": 1000.0, "liters": 1000.0,
    "tsp": 4.92892, "teaspoon": 4.92892, "teaspoons": 4.92892,
    "tbsp": 14.7868, "tablespoon": 14.7868, "tablespoons": 14.7868,
    "cup": 236.588, "cups": 236.588,
    "fl oz": 29.5735, "floz": 29.5735, "fluid ounce": 29.5735, "fluid ounces": 29.5735,
    "pt": 473.176, "pint": 473.176, "pints": 473.176,
    "qt": 946.353, "quart": 946.353, "quarts": 946.353,
}

_LIQUID_DENSITY: dict[str, float] = {
    "water": 1.0,
    "milk": 1.03, "skim milk": 1.035, "whole milk": 1.03, "almond milk": 1.01,
    "oil": 0.91, "olive oil": 0.911, "vegetable oil": 0.91, "canola oil": 0.914,
    "butter": 0.911,
    "honey": 1.42,
    "maple syrup": 1.32, "syrup": 1.32,
    "juice": 1.04, "orange juice": 1.04, "apple juice": 1.05,
    "coffee": 1.0, "tea": 1.0, "beer": 1.01, "wine": 0.99,
    "cream": 1.005, "heavy cream": 1.005, "half and half": 1.02,
    "broth": 1.0, "chicken broth": 1.0, "beef broth": 1.0, "stock": 1.0,
    "soy sauce": 1.19, "vinegar": 1.01,
    "ketchup": 1.12, "tomato sauce": 1.06,
    "yogurt": 1.1, "coconut milk": 0.96,
}


def _fetch_usda_food(fdc_id: int) -> dict:
    """Fetch and cache full USDA food detail (nutrients + portions)."""
    if fdc_id in _usda_food_cache:
        return _usda_food_cache[fdc_id]
    params = urllib.parse.urlencode({"api_key": _get_param(os.environ["USDA_API_KEY_PARAM"])})
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
    """Extract nutrient name→value dict from a USDA food detail response."""
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


def _fetch_usda_portions(fdc_id: int) -> list:
    return _fetch_usda_food(fdc_id).get("foodPortions", [])


def _convert_food_unit(amount: float, from_unit: str, food_name: str) -> dict:
    u = from_unit.lower().strip()

    if u in _WEIGHT_TO_G:
        return {"grams": round(amount * _WEIGHT_TO_G[u], 1), "method": "weight_conversion"}

    if u in _VOL_TO_ML:
        ml = amount * _VOL_TO_ML[u]
        usda = _search_usda(food_name)
        if usda.get("found") and usda.get("fdc_id"):
            portions = _fetch_usda_portions(usda["fdc_id"])
            aliases = {u, u.rstrip("s"), u + "s"}
            for p in portions:
                mu = p.get("measureUnit", {})
                keys = {mu.get("abbreviation", "").lower(), mu.get("name", "").lower(), p.get("modifier", "").lower()} - {""}
                if keys & aliases:
                    grams_per = (p.get("gramWeight") or 0) / (p.get("amount") or 1)
                    return {"grams": round(amount * grams_per, 1), "method": "usda_portions", "usda_food": usda["name"]}
        food_lower = food_name.lower()
        for key, density in _LIQUID_DENSITY.items():
            if key in food_lower:
                return {"grams": round(ml * density, 1), "method": f"liquid_density:{key}"}
        return {"grams": round(ml, 1), "method": "assumed_water_density"}

    # Named measures (piece, slice, whole…) — try USDA portions
    usda = _search_usda(food_name)
    if usda.get("found") and usda.get("fdc_id"):
        portions = _fetch_usda_portions(usda["fdc_id"])
        for p in portions:
            mu = p.get("measureUnit", {})
            keys = {mu.get("abbreviation", "").lower(), mu.get("name", "").lower(), p.get("modifier", "").lower()} - {""}
            if u in keys:
                grams_per = (p.get("gramWeight") or 0) / (p.get("amount") or 1)
                return {"grams": round(amount * grams_per, 1), "method": "usda_portions", "usda_food": usda["name"]}

    return {"error": f"Unknown unit '{from_unit}'"}


# ── restaurant lookup ─────────────────────────────────────────────────────────

def _restaurant_cache_key(restaurant: str, location: str) -> str:
    return hashlib.sha256(f"{restaurant.lower().strip()}|{location.lower().strip()}".encode()).hexdigest()[:16]


def _get_restaurant_cache(restaurant: str, location: str) -> dict | None:
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=f"cache/restaurant/{_restaurant_cache_key(restaurant, location)}.json")
        data = json.loads(obj["Body"].read())
        cached_at = datetime.fromisoformat(data["cached_at"])
        if datetime.now(UTC) - cached_at < timedelta(days=7):
            return data["result"]
    except Exception:
        pass
    return None


def _set_restaurant_cache(restaurant: str, location: str, result: dict):
    s3.put_object(
        Bucket=BUCKET,
        Key=f"cache/restaurant/{_restaurant_cache_key(restaurant, location)}.json",
        Body=json.dumps({"cached_at": datetime.now(UTC).isoformat(), "result": result}, indent=2),
        ContentType="application/json",
    )


def _search_restaurant_menu(restaurant_name: str, location: str, items: list[str]) -> dict:
    tavily_param = os.environ.get("TAVILY_API_KEY_PARAM", "")
    if not tavily_param:
        return {"found": False, "error": "Restaurant lookup not configured"}

    cached = _get_restaurant_cache(restaurant_name, location)
    if cached:
        print(f"Restaurant cache hit: {restaurant_name} ({location})")
        return cached

    query = f"{restaurant_name} {location} menu nutrition calories"
    if items:
        query += " " + ", ".join(items[:3])
    req_data = json.dumps({"query": query, "search_depth": "basic", "include_answer": True, "max_results": 5}).encode()
    req = urllib.request.Request(
        "https://api.tavily.com/search",
        data=req_data,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {_get_param(tavily_param)}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        _increment_usage("tavily_calls")
        result = {
            "found": True,
            "answer": data.get("answer", ""),
            "results": [
                {"title": r["title"], "url": r["url"], "content": r["content"][:600]}
                for r in data.get("results", [])[:5]
            ],
        }
        _set_restaurant_cache(restaurant_name, location, result)
        return result
    except Exception as e:
        return {"found": False, "error": str(e)}


# ── Claude agentic loop ───────────────────────────────────────────────────────

TOOLS = [
    {
        "toolSpec": {
            "name": "search_usda",
            "description": (
                "Search USDA FoodData Central by food name. "
                "Best for whole foods and generic ingredients. "
                "Returns nutrition per 100g."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Food name, e.g. 'chicken breast', 'banana'"}
                    },
                    "required": ["query"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "search_history",
            "description": (
                "Search the last 7 days of food log history for a specific previously-logged food item. "
                "Use ONLY when the input explicitly references something logged before — "
                "e.g. 'same as yesterday', '10 more X', 'another Y'. "
                "Do NOT use for generic ingredients (spinach, cheese, tomato) — use search_usda for those. "
                "Call at most once per input. Returns matching components with nutrition data and barcodes."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Food name or keyword to look up in history"}
                    },
                    "required": ["query"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "convert_food_unit",
            "description": (
                "Convert a measured food quantity to grams. "
                "Call when the input has a volume or weight unit — e.g. '2 tbsp peanut butter', '1 cup oats', '8 fl oz milk'. "
                "Do NOT call when quantity is already in grams, or for whole-count items (1 banana, 2 eggs). "
                "Uses USDA portion data for solids and density tables for liquids."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "amount": {"type": "number", "description": "Numeric quantity, e.g. 2.0"},
                        "from_unit": {"type": "string", "description": "Unit string, e.g. 'tbsp', 'cup', 'oz', 'ml'"},
                        "food_name": {"type": "string", "description": "Food name for portion lookup, e.g. 'peanut butter'"},
                    },
                    "required": ["amount", "from_unit", "food_name"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "search_restaurant_menu",
            "description": (
                "Look up a specific restaurant's menu items and nutritional info. "
                "Use ONLY when the input names a specific restaurant AND location — "
                "e.g. 'Small Kraken from Uncharted, Portland ME'. "
                "Do NOT call for home-cooked food, unnamed restaurants, or generic cuisines."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "restaurant_name": {"type": "string", "description": "Restaurant name, e.g. 'Uncharted'"},
                        "location": {"type": "string", "description": "City and state, e.g. 'Portland, ME'"},
                        "items": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Specific menu items to look up",
                        },
                    },
                    "required": ["restaurant_name", "location", "items"],
                }
            },
        }
    },
]

SYSTEM_PROMPT = """\
You are a nutrition tracking assistant. Parse food log entries into structured nutritional data.

The input has two sections:

KNOWN ITEMS (when present): Products identified by barcode scan with confirmed nutrition data.
  - Copy the nutrition_per_100g values EXACTLY as given — do NOT look these up with any tool.
  - Do NOT call search_history or search_usda for KNOWN ITEMS.
  - Your only job for these items is to estimate quantity_g from the context text or standard serving.
  - Set source to "openfoodfacts" and include the barcode field.
  - If TEXT ITEMS describe the same product as a KNOWN ITEM (e.g. "half bottle of X" when X is in KNOWN ITEMS), use the KNOWN ITEM nutrition and estimate quantity_g from the text — do not create a duplicate component for the text.
  - If serving_quantity_g and servings_per_container are provided, use them to estimate per-piece weight (e.g. 1 strip = serving_quantity_g grams).
  - If all items are in KNOWN ITEMS, output JSON immediately with no tool calls.

TEXT ITEMS: Free-text descriptions of food. For these:
  - For whole foods and generic ingredients: call search_usda per main ingredient, then estimate totals.
  - When a measured volume or weight unit is given (2 tbsp, 1 cup, 8 fl oz, 3 oz): call convert_food_unit to get grams for quantity_g. Skip for whole-count items (1 banana, 2 eggs) or quantities already in grams.
  - When the text names a specific restaurant AND location (e.g. "Small Kraken from Uncharted, Portland ME"): call search_restaurant_menu; set source to "restaurant".
  - When an item name matches something in the "Recently logged" hint that has a [barcode:...] tag — call search_history to retrieve the barcode-confirmed nutrition; prefer this over search_usda for that item. Set source to "history".
  - When the text explicitly references a previously logged item by occurrence ("same as before", "10 more X"): call search_history ONCE, use the returned data, set source to "history".
  - Do NOT call search_history for generic ingredients with no barcode in the hint — use search_usda for those.
  - USDA results include serving_size_g when available — use it as a reference for "1 serving".
  - Use your knowledge to estimate when tools return no result.

Sanity-check before outputting: verify (nutrition_per_100g.calories_kcal × quantity_g / 100) is plausible:
  - Half a sandwich: 250–500 kcal. Full restaurant entrée: 400–900 kcal. Side dish: 50–300 kcal.
  - Small candy/mint: 5–50 kcal. A cookie: 60–150 kcal. Fruit slice: 30–120 kcal.
  - If any component exceeds these ranges significantly, reduce quantity_g before output.

After all tool calls, respond with ONLY this JSON (no markdown, no explanation):
{
  "components": [
    {
      "name": "descriptive name",
      "quantity_g": 355,
      "source": "openfoodfacts" | "usda" | "history" | "restaurant" | "claude_estimate",
      "barcode": "...",
      "nutrition_per_100g": {
        "calories_kcal": 0,
        "protein_g": 0,
        "total_fat_g": 0,
        "saturated_fat_g": 0,
        "monounsaturated_fat_g": null,
        "polyunsaturated_fat_g": null,
        "omega3_g": null,
        "trans_fat_g": null,
        "total_carbohydrate_g": 0,
        "fiber_g": null,
        "sugar_g": null,
        "added_sugar_g": null,
        "starch_g": null,
        "cholesterol_mg": null,
        "sodium_mg": null,
        "potassium_mg": null,
        "calcium_mg": null,
        "iron_mg": null,
        "magnesium_mg": null,
        "zinc_mg": null,
        "vitamin_a_ug": null,
        "vitamin_c_mg": null,
        "vitamin_d_ug": null,
        "vitamin_b12_ug": null,
        "folate_ug": null
      }
    }
  ]
}

quantity_g: grams for solids, ml for liquids. ALWAYS provide a non-zero value — use the stated quantity, or estimate a typical serving if not stated.
All nutrition_per_100g fields required; use 0 if unknown.
NEVER ask for clarification. If data is unavailable, make your best estimate and output the JSON.\
"""


def _extract_components(texts: list[str], photos: list[bytes], barcode_data: list[dict] | None = None) -> list[dict]:
    user_content = []
    for photo in photos:
        user_content.append({"image": {"format": "jpeg", "source": {"bytes": photo}}})

    parts: list[str] = []
    resolved = [bd for bd in (barcode_data or []) if bd.get("found")]
    if resolved:
        parts.append("KNOWN ITEMS (barcode-resolved — copy nutrition exactly, only estimate quantity_g):")
        for bd in resolved:
            label = bd["name"] + (f" ({bd['brands']})" if bd.get("brands") else "")
            srv = bd.get("serving_size", "")
            parts.append(
                f"- {label} [barcode:{bd['barcode']}]"
                + (f"  (standard serving: {srv})" if srv else "") + "\n"
                f"  nutrition_per_100g: {json.dumps(bd['nutrition_per_100g'])}"
            )
        parts.append("")

    text_section = texts if texts else ([] if resolved else ["Identify this food from the barcode."])
    if text_section:
        if resolved:
            parts.append("TEXT ITEMS:")
        parts.extend(text_section)

    hint = _recent_items_hint()
    if hint:
        parts.append(f"\n{hint}")
    user_content.append({"text": "\n".join(parts)})

    messages = [{"role": "user", "content": user_content}]

    for _ in range(12):
        response = bedrock.converse(
            modelId=BEDROCK_MODEL_ID,
            system=[{"text": SYSTEM_PROMPT}],
            messages=messages,
            toolConfig={"tools": TOOLS},
        )
        _increment_usage("bedrock_calls")
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
                        print(f"Parse error: {e}, raw: {block['text'][:300]}")
                        messages.append({"role": "user", "content": [{"text": 'Your response was not valid JSON. Output ONLY the JSON object — no markdown, no prose, no explanation. Start with { and end with }.'}]})
                        retrying = True
                        break
            if not retrying:
                return []

        if stop_reason == "tool_use":
            results = []
            for block in output["content"]:
                if "toolUse" in block:
                    tool = block["toolUse"]
                    result = _call_tool(tool["name"], tool["input"])
                    found = result.get("found", result.get("total_found", "?"))
                    print(f"Tool {tool['name']}({tool['input']}) -> {found}")
                    results.append({
                        "toolResult": {
                            "toolUseId": tool["toolUseId"],
                            "content": [{"json": result}],
                        }
                    })
            if not results:
                break
            messages.append({"role": "user", "content": results})

    print("Max agentic loop rounds exceeded")
    return []


def _call_tool(name: str, inp: dict) -> dict:
    if name == "lookup_openfoodfacts":
        return _lookup_openfoodfacts(inp["barcode"])
    if name == "search_usda":
        return _search_usda(inp["query"])
    if name == "search_history":
        return _search_history(inp["query"])
    if name == "convert_food_unit":
        return _convert_food_unit(inp["amount"], inp["from_unit"], inp["food_name"])
    if name == "search_restaurant_menu":
        return _search_restaurant_menu(inp["restaurant_name"], inp["location"], inp.get("items", []))
    return {"error": f"Unknown tool: {name}"}


RESTAURANT_LOOKUP_PROMPT = """\
You are a restaurant location finder. Given web search results, extract specific restaurant locations matching the user's query.
Return ONLY valid JSON, no other text:
{"candidates": [{"name": "Restaurant Name", "address": "Full address, City, State", "notes": "cuisine or brief description"}]}
Include 1-5 candidates ordered by likelihood. If nothing matches clearly, return {"candidates": []}.\
"""


def _process_restaurant_lookup(msg: dict):
    client_id = msg.get("client_id") or str(uuid.uuid4())
    restaurant = msg.get("restaurant", "").strip()
    location = msg.get("location", "").strip()
    result_key = f"diet/restaurant_lookup/{client_id}.json"

    if not restaurant:
        s3.put_object(Bucket=BUCKET, Key=result_key, Body=json.dumps({"candidates": []}), ContentType="application/json")
        return

    tavily_param = os.environ.get("TAVILY_API_KEY_PARAM", "")
    candidates = []

    if tavily_param:
        query = f"{restaurant} {location} restaurant address location"
        req_data = json.dumps({
            "query": query, "search_depth": "basic", "include_answer": True, "max_results": 5,
        }).encode()
        req = urllib.request.Request(
            "https://api.tavily.com/search",
            data=req_data,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {_get_param(tavily_param)}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
            _increment_usage("tavily_calls")

            context = f"Query: {restaurant}" + (f" in {location}" if location else "") + "\n\n"
            if data.get("answer"):
                context += f"Search answer: {data['answer']}\n\n"
            context += "Search results:\n"
            for r in data.get("results", [])[:5]:
                context += f"- {r['title']}: {r['content'][:400]}\n"

            response = bedrock.converse(
                modelId=BEDROCK_MODEL_ID,
                system=[{"text": RESTAURANT_LOOKUP_PROMPT}],
                messages=[{"role": "user", "content": [{"text": context}]}],
            )
            _increment_usage("bedrock_calls")
            text = response["output"]["message"]["content"][0]["text"]
            start, end = text.find("{"), text.rfind("}") + 1
            if start >= 0 and end > start:
                candidates = json.loads(text[start:end]).get("candidates", [])
        except Exception as e:
            print(f"Restaurant lookup error: {e}")

    s3.put_object(
        Bucket=BUCKET,
        Key=result_key,
        Body=json.dumps({"candidates": candidates, "restaurant": restaurant, "location": location}),
        ContentType="application/json",
    )
    print(f"Restaurant lookup '{restaurant}' ({location}): {len(candidates)} candidates → {result_key}")


def _process_item_prefetch(msg: dict):
    client_id = msg.get("client_id") or str(uuid.uuid4())
    description = msg.get("description", "").strip()
    result_key = f"diet/prefetch/{client_id}.json"

    if not description:
        s3.put_object(Bucket=BUCKET, Key=result_key, Body=json.dumps({"components": []}), ContentType="application/json")
        return

    components = _extract_components([description], [])

    s3.put_object(
        Bucket=BUCKET,
        Key=result_key,
        Body=json.dumps({"components": components, "description": description}),
        ContentType="application/json",
    )
    print(f"Item prefetch '{description}': {len(components)} components → {result_key}")


def _process_usage_event(msg: dict):
    event_type = msg.get("event_type", "off_lookups")
    if event_type in {"off_lookups", "restaurant_searches"}:
        _increment_usage(event_type)


def _lookup_openfoodfacts(barcode: str) -> dict:
    url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
    req = urllib.request.Request(url, headers={"User-Agent": "ctbus-health/1.0 (https://github.com/Ulthran/ctbus_health)"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        if data.get("status") != 1:
            return {"found": False, "barcode": barcode}
        p = data["product"]
        n = p.get("nutriments", {})
        try:
            serving_qty_g = float(p["serving_quantity"]) if p.get("serving_quantity") else None
        except (ValueError, TypeError):
            serving_qty_g = None
        try:
            spc = float(p["servings_per_container"]) if p.get("servings_per_container") else None
        except (ValueError, TypeError):
            spc = None
        return {
            "found": True,
            "barcode": barcode,
            "name": p.get("product_name", ""),
            "brands": p.get("brands", ""),
            "serving_size": p.get("serving_size", ""),
            "serving_quantity_g": serving_qty_g,
            "servings_per_container": spc,
            "nutrition_per_100g": _off_nutrition(n),
        }
    except Exception as e:
        return {"found": False, "error": str(e), "barcode": barcode}


def _mg(val_g) -> float | None:
    return round(val_g * 1000, 2) if val_g is not None else None


def _off_nutrition(n: dict) -> dict:
    return {
        "calories_kcal": n.get("energy-kcal_100g"),
        "protein_g": n.get("proteins_100g"),
        "total_fat_g": n.get("fat_100g"),
        "saturated_fat_g": n.get("saturated-fat_100g"),
        "monounsaturated_fat_g": n.get("monounsaturated-fat_100g"),
        "polyunsaturated_fat_g": n.get("polyunsaturated-fat_100g"),
        "omega3_g": n.get("omega-3-fat_100g"),
        "trans_fat_g": n.get("trans-fat_100g"),
        "total_carbohydrate_g": n.get("carbohydrates_100g"),
        "fiber_g": n.get("fiber_100g"),
        "sugar_g": n.get("sugars_100g"),
        "added_sugar_g": n.get("added-sugars_100g"),
        "starch_g": n.get("starch_100g"),
        "cholesterol_mg": _mg(n.get("cholesterol_100g")),
        "sodium_mg": _mg(n.get("sodium_100g")),
        "potassium_mg": _mg(n.get("potassium_100g")),
        "calcium_mg": _mg(n.get("calcium_100g")),
        "iron_mg": _mg(n.get("iron_100g")),
        "magnesium_mg": _mg(n.get("magnesium_100g")),
        "zinc_mg": _mg(n.get("zinc_100g")),
        "vitamin_a_ug": n.get("vitamin-a_100g"),
        "vitamin_c_mg": n.get("vitamin-c_100g"),
        "vitamin_d_ug": n.get("vitamin-d_100g"),
        "vitamin_b12_ug": n.get("vitamin-b12_100g"),
        "folate_ug": n.get("vitamin-b9_100g"),
    }


def _search_usda(query: str) -> dict:
    api_key = _get_param(os.environ["USDA_API_KEY_PARAM"])
    params = urllib.parse.urlencode({
        "query": query,
        "dataType": "Foundation,SR Legacy",
        "pageSize": 3,
        "api_key": api_key,
    })
    url = f"https://api.nal.usda.gov/fdc/v1/foods/search?{params}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        _increment_usage("usda_calls")
        foods = data.get("foods", [])
        if not foods:
            return {"found": False, "query": query}
        f = foods[0]
        fdc_id = f.get("fdcId")
        # Fetch full detail for complete nutrient panel (search API only returns ~10 fields)
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
                "starch_g": nm.get("Starch"),
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


def _read_daily(date: str) -> dict:
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=f"diet/{date}.json")
        return json.loads(obj["Body"].read())
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            return {"date": date, "entries": []}
        raise


def _write_daily(date: str, data: dict):
    s3.put_object(
        Bucket=BUCKET,
        Key=f"diet/{date}.json",
        Body=json.dumps(data, indent=2),
        ContentType="application/json",
        CacheControl="no-cache",
    )
    _update_diet_index(date)


def _update_diet_index(date: str):
    key = "diet/index.json"
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=key)
        dates = json.loads(obj["Body"].read())
    except ClientError as e:
        dates = [] if e.response["Error"]["Code"] == "NoSuchKey" else None
    except Exception:
        dates = None
    if dates is None:
        return
    if date not in dates:
        dates.append(date)
        dates.sort(reverse=True)
        s3.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=json.dumps(dates),
            ContentType="application/json",
            CacheControl="no-cache",
        )
