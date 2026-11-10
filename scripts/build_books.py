#!/usr/bin/env python3
"""Generate the New Testament markdown files (one folder per book, one file per chapter).

Sources (all public domain):
  * Ancient Greek  - Robinson-Pierpont Byzantine Textform 2018
                     https://github.com/byztxt/byzantine-majority-text
  * Modern Greek   - Neophytos Vamvas translation (1850)
  * English        - King James Version (1769)
                     https://github.com/scrollmapper/bible_databases

Usage:
    python3 scripts/build_books.py            # create missing files only
    python3 scripts/build_books.py --force    # overwrite (DESTROYS manual edits!)

Existing chapter files are never overwritten without --force, because they are
meant to be edited by hand (on GitHub or through the website).
"""
import argparse
import csv
import io
import json
import os
import re
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "new-testament")

RP_URL = "https://raw.githubusercontent.com/byztxt/byzantine-majority-text/master/csv-unicode/ccat/no-variants/{}.csv"
SM_URL = "https://raw.githubusercontent.com/scrollmapper/bible_databases/master/formats/json/{}.json"

# (slug, English name, Greek title, RP file code, index in the 66-book list)
BOOKS = [
    ("matthew", "Matthew", "Κατά Ματθαίον", "MAT"),
    ("mark", "Mark", "Κατά Μάρκον", "MAR"),
    ("luke", "Luke", "Κατά Λουκάν", "LUK"),
    ("john", "John", "Κατά Ιωάννην", "JOH"),
    ("acts", "Acts", "Πράξεις των Αποστόλων", "ACT"),
    ("romans", "Romans", "Προς Ρωμαίους", "ROM"),
    ("1-corinthians", "1 Corinthians", "Προς Κορινθίους Α΄", "1CO"),
    ("2-corinthians", "2 Corinthians", "Προς Κορινθίους Β΄", "2CO"),
    ("galatians", "Galatians", "Προς Γαλάτας", "GAL"),
    ("ephesians", "Ephesians", "Προς Εφεσίους", "EPH"),
    ("philippians", "Philippians", "Προς Φιλιππησίους", "PHP"),
    ("colossians", "Colossians", "Προς Κολοσσαείς", "COL"),
    ("1-thessalonians", "1 Thessalonians", "Προς Θεσσαλονικείς Α΄", "1TH"),
    ("2-thessalonians", "2 Thessalonians", "Προς Θεσσαλονικείς Β΄", "2TH"),
    ("1-timothy", "1 Timothy", "Προς Τιμόθεον Α΄", "1TI"),
    ("2-timothy", "2 Timothy", "Προς Τιμόθεον Β΄", "2TI"),
    ("titus", "Titus", "Προς Τίτον", "TIT"),
    ("philemon", "Philemon", "Προς Φιλήμονα", "PHM"),
    ("hebrews", "Hebrews", "Προς Εβραίους", "HEB"),
    ("james", "James", "Ιακώβου", "JAM"),
    ("1-peter", "1 Peter", "Πέτρου Α΄", "1PE"),
    ("2-peter", "2 Peter", "Πέτρου Β΄", "2PE"),
    ("1-john", "1 John", "Ιωάννου Α΄", "1JO"),
    ("2-john", "2 John", "Ιωάννου Β΄", "2JO"),
    ("3-john", "3 John", "Ιωάννου Γ΄", "3JO"),
    ("jude", "Jude", "Ιούδα", "JUD"),
    ("revelation", "Revelation", "Αποκάλυψις Ιωάννου", "REV"),
]


def fetch(url):
    with urllib.request.urlopen(url, timeout=120) as r:
        return r.read().decode("utf-8")


def clean(text):
    text = text.replace("¶", "")
    return re.sub(r"\s+", " ", text).strip()


def load_scrollmapper(name):
    data = json.loads(fetch(SM_URL.format(name)))
    nt = data["books"][39:]
    assert len(nt) == 27, name
    out = []
    for book in nt:
        chapters = {}
        for ch in book["chapters"]:
            chapters[ch["chapter"]] = {v["verse"]: clean(v["text"]) for v in ch["verses"] if v["text"].strip()}
        out.append(chapters)
    return out


def load_rp(code):
    chapters = {}
    for row in csv.DictReader(io.StringIO(fetch(RP_URL.format(code)))):
        chapters.setdefault(int(row["chapter"]), {})[int(row["verse"])] = clean(row["text"])
    return chapters


def render_chapter(book, chapter, grc, ell, kjv):
    slug, en, el, _ = book
    lines = [
        f"# {en} {chapter} · {el} {chapter}",
        "",
        "<!--",
        "Format: each verse starts with a '## <number>' heading followed by up to three lines:",
        "  **GRC** Ancient Greek (Robinson-Pierpont 2018)",
        "  **ELL** Modern Greek (Vamvas 1850)",
        "  **KJV** King James Version (1769)",
        "Anything under '## Notes' is free-form markdown for your own study notes.",
        "-->",
        "",
    ]
    verses = sorted(set(grc) | set(ell) | set(kjv))
    for v in verses:
        lines += [f"## {v}", ""]
        lines += [f"**GRC** {grc.get(v, '')}".rstrip(), ""]
        lines += [f"**ELL** {ell.get(v, '')}".rstrip(), ""]
        lines += [f"**KJV** {kjv.get(v, '')}".rstrip(), ""]
    lines += ["## Notes", "", ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="overwrite existing chapter files")
    args = ap.parse_args()

    print("Downloading KJV and Vamvas ...")
    kjv_all = load_scrollmapper("KJV")
    ell_all = load_scrollmapper("GreVamvas")

    manifest = []
    written = skipped = 0
    for i, book in enumerate(BOOKS):
        slug, en, el, code = book
        print(f"  {en}")
        grc_book = load_rp(code)
        folder_name = f"{i + 1:02d}-{slug}"
        folder = os.path.join(OUT, folder_name)
        os.makedirs(folder, exist_ok=True)
        n_chapters = max(len(kjv_all[i]), len(ell_all[i]), len(grc_book))
        width = 2
        for c in range(1, n_chapters + 1):
            path = os.path.join(folder, f"chapter-{c:0{width}d}.md")
            if os.path.exists(path) and not args.force:
                skipped += 1
                continue
            with open(path, "w", encoding="utf-8") as f:
                f.write(render_chapter(book, c, grc_book.get(c, {}), ell_all[i].get(c, {}), kjv_all[i].get(c, {})))
            written += 1
        readme = os.path.join(folder, "README.md")
        if not os.path.exists(readme) or args.force:
            with open(readme, "w", encoding="utf-8") as f:
                f.write(f"# {en} · {el}\n\n")
                f.write("Each chapter file contains the Ancient Greek (GRC), Modern Greek (ELL) and King James (KJV) text verse by verse.\n\n")
                for c in range(1, n_chapters + 1):
                    f.write(f"- [Chapter {c}](chapter-{c:02d}.md)\n")
        manifest.append({"slug": slug, "folder": folder_name, "name": en, "greek": el, "chapters": n_chapters})

    with open(os.path.join(OUT, "books.json"), "w", encoding="utf-8") as f:
        json.dump({"testament": "New Testament", "books": manifest}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8") as f:
        f.write("# New Testament · Καινή Διαθήκη\n\n")
        for b in manifest:
            f.write(f"- [{b['name']} · {b['greek']}]({b['folder']}/README.md) — {b['chapters']} chapters\n")
    print(f"Done: {written} chapter files written, {skipped} existing files kept.")


if __name__ == "__main__":
    main()
