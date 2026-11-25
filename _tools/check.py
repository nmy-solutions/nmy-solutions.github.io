"""Self-check for this hand-written two-language site. Stdlib only, not a build step.
Run before every push:  python3 _tools/check.py
(_tools/ is not published: Jekyll skips folders that start with an underscore.)"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ORIGIN = "https://nmy.agency"
errors = []


def url_of(path):
    rel = path.relative_to(ROOT).as_posix()
    return ORIGIN + "/" + (rel[: -len("index.html")] if rel.endswith("index.html") else rel)


def file_of(url):
    rel = url[len(ORIGIN):].lstrip("/")
    return ROOT / (rel + "index.html" if rel == "" or rel.endswith("/") else rel)


def parse(path):
    text = path.read_text(encoding="utf-8")
    head = text.split("</head>")[0]
    lang = re.search(r'<html[^>]*\blang="([^"]+)"', head)
    canon = re.search(r'<link rel="canonical" href="([^"]+)"', head)
    alts = dict(re.findall(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)"', head))
    return text, lang and lang.group(1), canon and canon.group(1), alts, "noindex" in head


pages = {p: parse(p) for p in sorted(ROOT.rglob("*.html")) if not any(part[0] in "._" for part in p.relative_to(ROOT).parts)}  # Jekyll does not publish these
indexable = {}
for p, (text, lang, canon, alts, noindex) in pages.items():
    name = p.relative_to(ROOT).as_posix()
    # every local link and asset must exist
    for ref in re.findall(r'(?:href|src)="([^"#?]+)', text) + re.findall(r'([^\s",]+\.webp) \d+w', text):
        if re.match(r"[a-z]+:", ref):
            continue
        target = (ROOT / ref.lstrip("/")) if ref.startswith("/") else (p.parent / ref)
        if target.is_dir():
            target = target / "index.html"
        if not target.exists():
            errors.append(f"{name}: broken link {ref}")
    if re.search(r'href="[^"]*index\.html', text):
        errors.append(f"{name}: link to index.html (use ./ or ../)")
    if noindex:
        if alts:
            errors.append(f"{name}: noindex page must not carry hreflang")
        continue
    indexable[p] = canon
    want_lang = "en" if name.startswith("en/") else "uk"
    if lang != want_lang:
        errors.append(f"{name}: <html lang> is {lang}, expected {want_lang}")
    form_lang = re.search(r'name="_lang" value="([^"]+)"', text)
    if form_lang and form_lang.group(1) != lang:
        errors.append(f"{name}: form _lang={form_lang.group(1)} but page lang={lang}")
    if canon != url_of(p):
        errors.append(f"{name}: canonical {canon!r} != {url_of(p)!r}")
    if set(alts) != {"uk", "en", "x-default"}:
        errors.append(f"{name}: hreflang set is {sorted(alts)}")
        continue
    if alts.get(lang) != canon:
        errors.append(f"{name}: hreflang={lang} is not the page's own canonical")
    if alts["x-default"] != alts["uk"]:
        errors.append(f"{name}: x-default must be the Ukrainian URL")
    for code, url in alts.items():
        target = file_of(url) if url.startswith(ORIGIN + "/") else None
        if target not in pages:
            errors.append(f"{name}: hreflang={code} -> {url} has no page")
        elif pages[target][3] != alts:
            errors.append(f"{name}: {target.relative_to(ROOT).as_posix()} does not link back with the same hreflang set")

locs = set(re.findall(r"<loc>([^<]+)</loc>", (ROOT / "sitemap.xml").read_text(encoding="utf-8")))
if locs != set(indexable.values()):
    errors.append(f"sitemap.xml differs from the page canonicals: {sorted(locs ^ set(indexable.values()))}")

print("\n".join(errors) if errors else f"OK: {len(indexable)} indexable pages, hreflang pairs, links and sitemap agree")
sys.exit(1 if errors else 0)
