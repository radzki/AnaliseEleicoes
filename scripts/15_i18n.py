"""Keep a translation of the page in step with the Portuguese (locales/pt-BR.json).

Usage:
  python -I scripts/15_i18n.py status <lang>               texts of locales/<lang>.json missing or translated
                                                           from Portuguese that has changed since
  python -I scripts/15_i18n.py todo <lang> <out.json>      the same texts, {key: current Portuguese}, to translate
  python -I scripts/15_i18n.py merge <lang> <in.json>...   add translations given as {key: text}, each marked as
                                                           translated from the current Portuguese

Each entry of locales/<lang>.json is {"text": ..., "from": <hash of the Portuguese>}; scripts/05_site.py
shows the Portuguese, marked, wherever "from" no longer matches, and stops when a translation's tags or
{placeholders} differ from the Portuguese. merge refuses those too.
"""
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

loc = Path(__file__).resolve().parent.parent / "locales"
sys.stdout.reconfigure(encoding="utf-8")
cmd, lang, *files = sys.argv[1:]
# the 404 page is one for the whole site, in Portuguese: nothing to translate there
PT = {k: v for k, v in json.loads((loc / "pt-BR.json").read_text(encoding="utf-8")).items() if not k.startswith("404.")}
path = loc / f"{lang}.json"
TR = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
TEXT_ATTRS = ("aria-label", "title", "alt", "placeholder")


def source_hash(text):  # as in scripts/05_site.py
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:10]


def shape(s):  # as in scripts/05_site.py
    tags = [re.sub(r'\s(?:%s)="[^"]*"' % "|".join(TEXT_ATTRS), "", t) for t in re.findall(r"<[^>]+>", s)]
    return Counter(tags), Counter(re.findall(r"\{\w+\}", s))


todo = [k for k, v in PT.items() if k not in TR or TR[k]["from"] != source_hash(v)]
if cmd == "status":
    gone = [k for k in TR if k not in PT]
    print(f"{lang}: {len(PT) - len(todo)} of {len(PT)} texts up to date; {sum(k not in TR for k in todo)} missing, "
          f"{sum(k in TR for k in todo)} out of date; {len(gone)} no longer in the Portuguese")
    for k in todo:
        print(f"  {'missing ' if k not in TR else 'outdated'} {k}: {PT[k][:90]}")
elif cmd == "todo":
    Path(files[0]).write_text(json.dumps({k: PT[k] for k in todo}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(todo)} texts -> {files[0]}")
elif cmd == "merge":
    new = {}
    for f in files:
        new.update(json.loads(Path(f).read_text(encoding="utf-8")))
    unknown = [k for k in new if k not in PT]
    bad = [k for k, v in new.items() if k in PT and shape(v) != shape(PT[k])]
    if unknown or bad:
        sys.exit(f"not merged: unknown keys {unknown[:10]}; tags or placeholders differ from the Portuguese in {bad[:10]}")
    for k, v in new.items():
        TR[k] = {"text": v, "from": source_hash(PT[k])}
    # same order as the Portuguese, so a diff of the two files lines up
    TR = {k: TR[k] for k in PT if k in TR} | {k: v for k, v in TR.items() if k not in PT}
    path.write_text(json.dumps(TR, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{lang}: merged {len(new)}; {len(PT) - len([k for k in PT if k not in TR or TR[k]['from'] != source_hash(PT[k])])}"
          f" of {len(PT)} texts up to date")
else:
    sys.exit(__doc__)
