from decimal import Decimal
import re

SCALES = {"thousand": 10**3, "million": 10**6, "billion": 10**9, "trillion": 10**12, "k": 10**3, "m": 10**6, "b": 10**9, "bn": 10**9, "tn": 10**12}
SMALL = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
QUANTITY = re.compile(r"(?<![\w.])(?P<currency>[$€£])?\s*(?P<number>\d[\d,]*(?:\.\d+)?|" + "|".join(SMALL) + r")\s*(?P<scale>thousand|million|billion|trillion|bn|tn|[kmb])?\b(?:(?P<percent>\s*(?:%|percent\b))|(?P<points>\s*percentage\s+points?\b))?", re.I)


def quantities(text: str) -> set[tuple]:
    found = set()
    for match in QUANTITY.finditer(text):
        value = match["number"].lower()
        scale = (match["scale"] or "").lower()
        if value in SMALL and not scale and not match["percent"] and not match["points"] and not match["currency"] and not re.match(r"[-\s]*(?:years?|days?|months?|hours?)\b", text[match.end():], re.I):
            continue
        amount = Decimal(SMALL[value]) if value in SMALL else Decimal(value.replace(",", ""))
        amount *= SCALES.get(scale, 1)
        found.add((str(amount.normalize()), "points" if match["points"] else "percent" if match["percent"] else match["currency"] or "number"))
    return found


def validate_numbers(output: str, evidence: str, require_explicit_magnitudes: bool = True) -> None:
    if require_explicit_magnitudes:
        spans = [(match.start(), match.end()) for match in QUANTITY.finditer(output) if match["scale"]]
        for magnitude in re.finditer(r"\b(?:thousands?|millions?|billions?|trillions?)\b", output, re.I):
            if not any(start <= magnitude.start() < end for start, end in spans):
                raise ValueError("An unquantified magnitude cannot replace a supported numerical value")
    unsupported = quantities(output) - quantities(evidence)
    if unsupported:
        raise ValueError("Unsupported number, currency, percentage or magnitude: " + str(sorted(unsupported)))


def text_field(value, limit: int = 5000) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value == value.strip() and len(value) <= limit and not re.search(r"[\x00-\x1f<>]|https?://|www\.|crypto[.\s-]+news|\]\(", value, re.I)


def validate_originality(body: str, evidence: str) -> None:
    words = lambda value: re.findall(r"\w+", value.lower())
    source, output = words(evidence), words(body)
    phrases = {tuple(source[index:index + 12]) for index in range(max(0, len(source) - 11))}
    for index in range(max(0, len(output) - 11)):
        if tuple(output[index:index + 12]) in phrases:
            raise ValueError("Report repeats an extended source phrase: " + " ".join(output[index:index + 12]))


def validate_facts(facts, source: str) -> None:
    if not isinstance(facts, list) or not 7 <= len(facts) <= 16 or any(not text_field(fact, 650) for fact in facts):
        raise ValueError("Need 7 to 16 complete, plain-text source facts")
    if len(set(facts)) != len(facts) or len(" ".join(facts).split()) < 100:
        raise ValueError("Not enough distinct factual material for a report")
    validate_numbers(" ".join(facts), source, require_explicit_magnitudes=False)


def validate_fact_quotes(cards, passages: list[dict]) -> list[str]:
    if not isinstance(cards, list) or not 8 <= len(cards) <= 12:
        raise ValueError("Select 8 to 12 evidence quotations")
    normalize = lambda value: " ".join(value.replace("’", "'").replace("“", '"').replace("”", '"').split())
    lookup = {passage["id"]: passage["text"] for passage in passages}
    facts = []
    for card in cards:
        if not isinstance(card, dict) or set(card) != {"paragraph", "quote"} or type(card["paragraph"]) is not int or card["paragraph"] not in lookup:
            raise ValueError("Each evidence quotation needs a valid paragraph ID")
        quote = card["quote"]
        if not isinstance(quote, str) or not 10 <= len(quote.split()) <= 100 or not re.search(r'[.!?][”’\"]?$', quote):
            raise ValueError("Evidence must contain complete sentences of 10 to 100 words")
        if normalize(quote) not in normalize(lookup[card["paragraph"]]):
            raise ValueError("Evidence quotation is not verbatim in its cited paragraph")
        if normalize(quote) in {normalize(fact) for fact in facts}:
            raise ValueError("Evidence quotations must be distinct")
        facts.append(quote)
    if len(" ".join(facts).split()) < 160:
        raise ValueError("Not enough source evidence for a complete report")
    return facts


def validate_report_structure(report: dict) -> str:
    if not isinstance(report, dict) or set(report) != {"title", "summary", "paragraphs", "headings"}:
        raise ValueError("Report requires title, summary, paragraphs and headings")
    paragraphs, headings = report["paragraphs"], report["headings"]
    if not text_field(report["title"], 110) or not text_field(report["summary"], 280):
        raise ValueError("Invalid headline or summary")
    if not isinstance(paragraphs, list) or not 6 <= len(paragraphs) <= 10 or any(not text_field(value, 1400) for value in paragraphs):
        raise ValueError("Report needs 6 to 10 complete paragraphs")
    if not isinstance(headings, list) or len(headings) != 2 or any(not text_field(value, 75) for value in headings):
        raise ValueError("Report needs two short section headings")
    if any(paragraph.startswith(("#", "- ", "* ")) or not re.search(r'[.!?][”’\"]?$', paragraph) or paragraph.endswith("...") or "…" in paragraph for paragraph in paragraphs):
        raise ValueError("Report paragraphs must be complete sentences, without excerpt truncation or Markdown")
    if any(heading.startswith("#") for heading in headings):
        raise ValueError("Headings must contain plain text")
    body = " ".join(paragraphs)
    if not 220 <= len(body.split()) <= 520 or any(len(paragraph.split()) < 15 for paragraph in paragraphs):
        raise ValueError("Report must contain 220 to 520 substantive words")
    output = " ".join([report["title"], report["summary"], *paragraphs, *headings])
    return output


def validate_report(report: dict, item: dict) -> None:
    output = validate_report_structure(report)
    if re.sub(r"\W+", "", report["title"]).lower() == re.sub(r"\W+", "", item["title"]).lower():
        raise ValueError("Write a distinct headline")
    evidence = item["title"] + " " + item["source"]["text"]
    validate_numbers(output, evidence)
    if re.search(r"\b(?:millions|billions|trillions)\b", report["title"], re.I):
        raise ValueError("Headline magnitudes need an explicit supported quantity")
    for acronym in re.findall(r"\b[A-Z]{2,6}\b", output):
        if not re.search(r"\b" + re.escape(acronym) + r"\b", evidence, re.I):
            raise ValueError("Unsupported acronym or ticker: " + acronym)
    for phrase in ("at the forefront", "game-changer", "revolutionary", "safe-haven asset", "all applicable laws", "resilience and adaptability", "significant step", "positioning itself as a leader", "significantly enhance", "investors should", "suggesting caution for investors"):
        if phrase in output.lower():
            raise ValueError("Unsupported promotional or background claim")
    validate_originality(" ".join(report["paragraphs"]), evidence)
