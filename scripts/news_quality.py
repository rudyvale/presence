from decimal import Decimal
import re

SCALES = {"thousand": 10**3, "million": 10**6, "billion": 10**9, "trillion": 10**12, "k": 10**3, "m": 10**6, "b": 10**9, "bn": 10**9, "tn": 10**12}
SMALL = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
QUANTITY = re.compile(r"(?<![\w.])(?P<currency>[$€£])?\s*(?P<number>\d[\d,]*(?:\.\d+)?|" + "|".join(SMALL) + r")\s*(?P<scale>thousand|million|billion|trillion|bn|tn|[kmb])?\b(?:(?P<percent>\s*(?:%|percent\b|per\s+cent\b|pct\b))|(?P<points>\s*percentage\s+points?\b))?", re.I)


def quantities(text: str) -> set[tuple]:
    text = re.sub(r"\b(US|UK|DE|JP|FR)(\d{1,3})Y\b", r"\1 \2 years", text, flags=re.I)
    text = re.sub(r"(?<![\w.])(\d{1,3})\s*-?(?:yrs?|y)\b", r"\1 years", text, flags=re.I)
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


def validate_originality(body: str, evidence: str | list[str]) -> None:
    words = lambda value: re.findall(r"\w+", value.lower())
    blocks = [evidence] if isinstance(evidence, str) else evidence
    output = words(body)
    phrases = set()
    for block in blocks:
        source = words(block)
        for index in range(max(0, len(source) - 11)):
            phrase = source[index:index + 12]
            if sum(any(character.isalpha() for character in word) for word in phrase) >= 10:
                phrases.add(tuple(phrase))
    for index in range(max(0, len(output) - 11)):
        if tuple(output[index:index + 12]) in phrases:
            raise ValueError("Report repeats an extended source phrase: " + " ".join(output[index:index + 12]))


def validate_facts(facts, source: str) -> None:
    if not isinstance(facts, list) or not 7 <= len(facts) <= 16 or any(not text_field(fact, 650) for fact in facts):
        raise ValueError("Need 7 to 16 complete, plain-text source facts")
    if len(set(facts)) != len(facts) or len(" ".join(facts).split()) < 100:
        raise ValueError("Not enough distinct factual material for a report")
    validate_numbers(" ".join(facts), source, require_explicit_magnitudes=False)


def validate_fact_selection(indices, passages: list[dict]) -> list[str]:
    if not isinstance(indices, list) or not 8 <= len(indices) <= 12:
        raise ValueError("Select 8 to 12 evidence passage IDs")
    lookup = {passage["id"]: passage["text"] for passage in passages}
    if any(type(index) is not int or index not in lookup for index in indices) or len(set(indices)) != len(indices):
        raise ValueError("Evidence passage IDs must be distinct valid integers")
    facts = [lookup[index] for index in indices]
    if any(len(fact.split()) < 10 for fact in facts) or not 160 <= len(" ".join(facts).split()) <= 700:
        raise ValueError("Select 160 to 700 words of substantive source evidence")
    return facts


def validate_report_structure(report: dict) -> str:
    if not isinstance(report, dict) or set(report) != {"title", "summary", "paragraphs", "headings"}:
        raise ValueError("Report requires title, summary, paragraphs and headings")
    paragraphs, headings = report["paragraphs"], report["headings"]
    if not text_field(report["title"], 110) or not text_field(report["summary"], 280):
        raise ValueError("Invalid headline or summary")
    if not isinstance(paragraphs, list) or not 6 <= len(paragraphs) <= 14:
        raise ValueError(f"Report needs 6 to 14 paragraphs; received {len(paragraphs) if isinstance(paragraphs, list) else type(paragraphs).__name__}")
    for index, value in enumerate(paragraphs):
        if not text_field(value, 1400):
            if isinstance(value, str):
                marker = re.search(r"https?://|www\.|crypto[.\s-]+news", value, re.I)
                reason = f"source publisher or URL marker {marker.group(0)!r}" if marker else "HTML or control characters" if re.search(r"[\x00-\x1f<>]", value) else f"length {len(value)} or whitespace"
            else:
                reason = type(value).__name__
            raise ValueError(f"Paragraph {index} contains invalid text: {reason}")
    if not isinstance(headings, list) or len(headings) != 2 or any(not text_field(value, 75) for value in headings):
        raise ValueError("Report needs two short section headings")
    if any(paragraph.startswith(("#", "- ", "* ")) or not re.search(r'[.!?][”’\"]?$', paragraph) or paragraph.endswith("...") or "…" in paragraph for paragraph in paragraphs):
        raise ValueError("Report paragraphs must be complete sentences, without excerpt truncation or Markdown")
    if any(heading.startswith("#") for heading in headings):
        raise ValueError("Headings must contain plain text")
    body = " ".join(paragraphs)
    if not 220 <= len(body.split()) <= 750:
        raise ValueError(f"Report must contain 220 to 750 substantive words; received {len(body.split())}")
    short = [index for index, paragraph in enumerate(paragraphs) if len(paragraph.split()) < 15]
    if short:
        raise ValueError(f"Paragraphs {short} need at least 15 words each")
    output = " ".join([report["title"], report["summary"], *paragraphs, *headings])
    return output


def paragraph_target(source_words: int) -> int:
    return 12 if source_words >= 750 else 10 if source_words >= 450 else 8


def validate_completeness(report: dict, source_words: int) -> None:
    minimum = paragraph_target(source_words) * 35
    words = len(" ".join(report["paragraphs"]).split())
    if words < minimum:
        raise ValueError(f"Report is too compressed for {source_words} source words: needs at least {minimum} supported words, received {words}")


def validate_report(report: dict, item: dict) -> None:
    output = validate_report_structure(report)
    if item.get("length_policy") == 1:
        validate_completeness(report, item["source"]["word_count"])
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
    validate_originality(" ".join(report["paragraphs"]), item["source"].get("prose_blocks", [item["source"]["text"]]))
