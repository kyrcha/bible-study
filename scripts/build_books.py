#!/usr/bin/env python3
"""Generate the Old and New Testament markdown files (one folder per book, one file per chapter).

Sources:
  * Ancient Greek NT - Robinson-Pierpont Byzantine Textform 2018 (public domain)
                       https://github.com/byztxt/byzantine-majority-text
  * Ancient Greek OT - Septuagint, H. B. Swete edition (1909-1930; public-domain text,
                       digitised by https://github.com/eliranwong/LXX-Swete-1930)
  * Modern Greek     - Neophytos Vamvas translation (1850)
  * English          - King James Version (1769)
  * Hebrew OT        - Westminster Leningrad Codex (Masoretic text)
  * Jewish English   - Jewish Publication Society translation (1917)
                       https://github.com/scrollmapper/bible_databases

The Hebrew (HEB) and JPS lines are added to Old Testament verses in KJV numbering. Existing
chapter files are never rewritten; missing version lines are inserted into them instead, so
manual edits are preserved.

Usage:
    python3 scripts/build_books.py            # create missing files only
    python3 scripts/build_books.py --force    # overwrite (DESTROYS manual edits!)
    python3 scripts/build_books.py --only ot  # just one testament (ot / nt)

Existing chapter files are never overwritten without --force, because they are
meant to be edited by hand (on GitHub or through the website).
"""
import argparse
import collections
import csv
import io
import json
import os
import re
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NT_DIR = os.path.join(ROOT, "new-testament")
OT_DIR = os.path.join(ROOT, "old-testament")

RP_URL = "https://raw.githubusercontent.com/byztxt/byzantine-majority-text/master/csv-unicode/ccat/no-variants/{}.csv"
LXX_URL = "https://raw.githubusercontent.com/eliranwong/LXX-Swete-1930/master/{}"
SM_URL = "https://raw.githubusercontent.com/scrollmapper/bible_databases/master/formats/json/{}.json"

# (slug, English name, Greek title, Robinson-Pierpont file code)
NT_BOOKS = [
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

# (slug, English name, Greek title, Swete book code)
OT_BOOKS = [
    ("genesis", "Genesis", "Γένεσις", "Gen"),
    ("exodus", "Exodus", "Έξοδος", "Exo"),
    ("leviticus", "Leviticus", "Λευιτικόν", "Lev"),
    ("numbers", "Numbers", "Αριθμοί", "Num"),
    ("deuteronomy", "Deuteronomy", "Δευτερονόμιον", "Deu"),
    ("joshua", "Joshua", "Ιησούς του Ναυή", "Jos"),
    ("judges", "Judges", "Κριταί", "Jdg"),
    ("ruth", "Ruth", "Ρουθ", "Rut"),
    ("1-samuel", "1 Samuel", "Βασιλειών Α΄", "1Sa"),
    ("2-samuel", "2 Samuel", "Βασιλειών Β΄", "2Sa"),
    ("1-kings", "1 Kings", "Βασιλειών Γ΄", "1Ki"),
    ("2-kings", "2 Kings", "Βασιλειών Δ΄", "2Ki"),
    ("1-chronicles", "1 Chronicles", "Παραλειπομένων Α΄", "1Ch"),
    ("2-chronicles", "2 Chronicles", "Παραλειπομένων Β΄", "2Ch"),
    ("ezra", "Ezra", "Έσδρας", "Ezr"),
    ("nehemiah", "Nehemiah", "Νεεμίας", "Neh"),
    ("esther", "Esther", "Εσθήρ", "Est"),
    ("job", "Job", "Ιώβ", "Job"),
    ("psalms", "Psalms", "Ψαλμοί", "Psa"),
    ("proverbs", "Proverbs", "Παροιμίαι", "Pro"),
    ("ecclesiastes", "Ecclesiastes", "Εκκλησιαστής", "Ecc"),
    ("song-of-solomon", "Song of Solomon", "Άσμα Ασμάτων", "Sol"),
    ("isaiah", "Isaiah", "Ησαΐας", "Isa"),
    ("jeremiah", "Jeremiah", "Ιερεμίας", "Jer"),
    ("lamentations", "Lamentations", "Θρήνοι", "Lam"),
    ("ezekiel", "Ezekiel", "Ιεζεκιήλ", "Eze"),
    ("daniel", "Daniel", "Δανιήλ", "Dat"),  # Theodotion's Daniel, the text read in the Church
    ("hosea", "Hosea", "Ωσηέ", "Hos"),
    ("joel", "Joel", "Ιωήλ", "Joe"),
    ("amos", "Amos", "Αμώς", "Amo"),
    ("obadiah", "Obadiah", "Αβδιού", "Oba"),
    ("jonah", "Jonah", "Ιωνάς", "Jon"),
    ("micah", "Micah", "Μιχαίας", "Mic"),
    ("nahum", "Nahum", "Ναούμ", "Nah"),
    ("habakkuk", "Habakkuk", "Αμβακούμ", "Hab"),
    ("zephaniah", "Zephaniah", "Σοφονίας", "Zep"),
    ("haggai", "Haggai", "Αγγαίος", "Hag"),
    ("zechariah", "Zechariah", "Ζαχαρίας", "Zec"),
    ("malachi", "Malachi", "Μαλαχίας", "Mal"),
]

SOURCES = {
    "nt": {"GRC": "Robinson-Pierpont 2018", "ELL": "Vamvas 1850", "KJV": "King James Version 1769"},
    "ot": {"GRC": "Septuagint, Swete 1909-1930", "ELL": "Vamvas 1850", "KJV": "King James Version 1769",
           "HEB": "Westminster Leningrad Codex", "JPS": "Jewish Publication Society 1917"},
}
TAGS = ["GRC", "ELL", "KJV", "HEB", "JPS"]


def fetch(url):
    with urllib.request.urlopen(url, timeout=120) as r:
        return r.read().decode("utf-8")


def clean(text):
    text = text.replace("¶", "")
    return re.sub(r"\s+", " ", text).strip()


_SM_CACHE = {}


def load_scrollmapper(name, testament):
    if name not in _SM_CACHE:
        _SM_CACHE[name] = json.loads(fetch(SM_URL.format(name)))["books"]
    books = _SM_CACHE[name][39:] if testament == "nt" else _SM_CACHE[name][:39]
    out = []
    for book in books:
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


# ---------------------------------------------------------------------------
# Septuagint (Swete) -> KJV versification
# ---------------------------------------------------------------------------
SIGLA_RE = re.compile(r"[⸂⸃⸆]")
BRACKET_RE = re.compile(r"\[(?!\d+\])|(?<!\[\d)(?<!\[\d\d)\]")


def clean_lxx(text):
    text = SIGLA_RE.sub("", text)
    text = BRACKET_RE.sub("", text)  # editorial brackets, but keep markers like [1]
    return clean(text)


def load_lxx():
    """{book_code: {chapter: {verse: text}}} in Swete's own numbering."""
    words = {}
    for line in fetch(LXX_URL.format("01-Swete_word_with_punctuations.csv")).splitlines():
        if "\t" in line:
            i, w = line.split("\t", 1)
            words[int(i)] = w
    refs = []
    for line in fetch(LXX_URL.format("00-Swete_versification.csv")).splitlines():
        if "\t" in line:
            i, r = line.split("\t")
            refs.append((int(i), r))
    end_all = max(words) + 1
    out = collections.defaultdict(lambda: collections.defaultdict(dict))
    for k, (start, ref) in enumerate(refs):
        end = refs[k + 1][0] if k + 1 < len(refs) else end_all
        m = re.match(r"(\w+)\.(\d+):(\d+)$", ref)
        text = clean_lxx(" ".join(words[j] for j in range(start, end) if j in words))
        out[m[1]][int(m[2])][int(m[3])] = text
    return out


def ordered(ch):
    return [ch[v] for v in sorted(ch)]


def assign(seq, slots, target):
    """Pour a list of LXX verses into a list of KJV (chapter, verse) slots.

    When the Greek has more verses than the English (psalm titles counted as their own
    verse), the extra leading verses are merged into the first English verse.
    """
    seq = [t for t in seq if t]
    extra = len(seq) - len(slots)
    if extra > 0:
        seq = [" ".join(seq[: extra + 1])] + seq[extra + 1:]
    for slot, text in zip(slots, seq):
        target[slot[0]][slot[1]] = text


# LXX psalm numbers -> KJV psalm numbers (groups that must be mapped together)
def psalm_groups():
    groups = [([c], [c]) for c in range(1, 9)]
    groups.append(([9], [9, 10]))
    groups += [([c], [c + 1]) for c in range(10, 113)]
    groups.append(([113], [114, 115]))
    groups.append(([114, 115], [116]))
    groups += [([c], [c + 1]) for c in range(116, 146)]
    groups.append(([146, 147], [147]))
    groups += [([c], [c]) for c in range(148, 151)]
    return groups


# LXX Jeremiah (chapter, first verse, last verse) -> KJV (chapter, first verse)
JEREMIAH = [((25, 14, 99), (49, 34)), ((26, 2, 99), (46, 2)), ((27, 1, 99), (50, 1)), ((28, 1, 99), (51, 1)),
            ((29, 1, 7), (47, 1)), ((29, 8, 99), (49, 7)), ((30, 1, 5), (49, 1)), ((30, 6, 11), (49, 28)),
            ((30, 12, 99), (49, 23)), ((31, 1, 99), (48, 1)), ((32, 1, 99), (25, 15)),
            ((51, 1, 30), (44, 1)), ((51, 31, 99), (45, 1))] + [((c, 1, 99), (c - 7, 1)) for c in range(33, 51)]


def fix_boundaries(lxx, kjv):
    """Move verses across chapter breaks where the Greek/Hebrew and English chapters split differently
    (e.g. KJV Jonah 1:17 = LXX 2:1, KJV Genesis 31:55 = LXX 32:1)."""
    chapters = sorted(set(lxx) | set(kjv))
    for c in chapters:
        if c + 1 not in lxx or c not in lxx:
            continue
        kc, kn = len(kjv.get(c, {})), len(kjv.get(c + 1, {}))
        lc, ln = len(lxx[c]), len(lxx[c + 1])
        if kc > lc and ln > kn and kc - lc == ln - kn:
            k = kc - lc
            nxt = ordered(lxx[c + 1])
            for i, t in enumerate(nxt[:k]):
                lxx[c][lc + 1 + i] = t
            lxx[c + 1] = {i + 1: t for i, t in enumerate(nxt[k:])}
        elif lc > kc and kn > ln and lc - kc == kn - ln:
            k = lc - kc
            cur = ordered(lxx[c])
            lxx[c] = {i + 1: t for i, t in enumerate(cur[:kc])}
            lxx[c + 1] = {i + 1: t for i, t in enumerate(cur[kc:] + ordered(lxx[c + 1]))}


def align_lxx(code, src, kjv):
    """Return ({chapter: {verse: text}}, {(chapter, verse): [notes]}) in KJV numbering."""
    out = collections.defaultdict(dict)
    notes = collections.defaultdict(list)
    src = {c: dict(vs) for c, vs in src.items()}
    if code == "Psa":
        for lxx_cs, kjv_cs in psalm_groups():
            seq = [t for c in lxx_cs for t in ordered(src.get(c, {}))]
            slots = [(c, v) for c in kjv_cs for v in sorted(kjv.get(c, {}))]
            if len(seq) > len(slots):
                assign(seq, slots, out)  # titles counted as verses: merge them into verse 1
            else:
                # Same or fewer verses (the Greek joins a few): align by verse number so a
                # missing verse does not shift the rest of the psalm.
                base = 0
                for c in lxx_cs:
                    for v, t in src.get(c, {}).items():
                        if base + v - 1 < len(slots):
                            kc, kv = slots[base + v - 1]
                            out[kc][kv] = t
                    base += max(src.get(c, {0: ""}))
        if 151 in src:
            out[151] = dict(src[151])
            notes[(151, 1)].append("Psalm 151 is found only in the Septuagint.")
        return out, notes
    if code == "Jer":
        for c in range(1, 26):
            for v, t in src.get(c, {}).items():
                if c != 25 or v <= 13:
                    out[c][v] = t
        out[52] = dict(src.get(52, {}))
        for (lc, v0, v1), (kc, k0) in JEREMIAH:
            for v, t in sorted(src.get(lc, {}).items()):
                if v0 <= v <= v1:
                    out[kc][k0 + v - v0] = t
        # LXX 26:1 closes the Elam oracle (= KJV 49:34b); the Greek has nothing for KJV 46:1.
        out[49][34] = out[49].get(34, "") + " " + src[26][1]
        return out, notes
    if code == "Mal":
        # The Septuagint puts "Remember the law of Moses" (KJV 4:4) at the very end.
        src[4] = {1: src[4][1], 2: src[4][2], 3: src[4][3], 4: src[4][6], 5: src[4][4], 6: src[4][5]}
    if code == "Dat":
        # Prayer of Azariah and Song of the Three Young Men (LXX 3:24-90) have no KJV counterpart.
        ch3 = src[3]
        song = " ".join(ch3[v] for v in range(24, 91) if v in ch3)
        notes[(3, 23)].append("*Προσευχή Αζαρίου και Ύμνος των τριών παίδων (LXX 3:24–90):* " + song)
        src[3] = {i + 1: t for i, t in enumerate([ch3[v] for v in sorted(ch3) if v < 24 or v > 90])}
    if code == "1Ki":
        # 3 Kingdoms 20 and 21 appear in the opposite order to the Hebrew/English 1 Kings 21 and 20.
        src[20], src[21] = src[21], src[20]
    fix_boundaries(src, kjv)
    for c, vs in src.items():
        out[c].update(vs)
    return out, notes


# ---------------------------------------------------------------------------
# Hebrew-numbered texts (WLC, JPS) -> KJV versification
# ---------------------------------------------------------------------------
def load_by_name(name, cleaner=clean):
    if name not in _SM_CACHE:
        _SM_CACHE[name] = json.loads(fetch(SM_URL.format(name)))["books"]
    return {b["name"]: {c["chapter"]: {v["verse"]: cleaner(v["text"]) for v in c["verses"] if v["text"].strip()}
                        for c in b["chapters"]} for b in _SM_CACHE[name]}


def clean_wlc(text):
    return clean(re.sub(r"׃[\d\s]+$", "׃", text.replace("‍", "")))


# Known places where the Hebrew splits a verse differently and the totals cannot balance.
# {book: {hebrew_chapter: function(verse) -> (kjv_chapter, kjv_verse)}}
HEBREW_FIXES = {
    "Num": {25: lambda v: (26, 1) if v == 19 else (25, v)},           # Heb 25:19 = KJV 26:1a
    "1Sa": {21: lambda v: (20, 42) if v == 1 else (21, v - 1)},       # Heb 21:1 = KJV 20:42b
    "1Ki": {22: lambda v: (22, v) if v <= 43 else (22, v - 1)},       # Heb 22:43-44 = KJV 22:43
    "1Ch": {12: lambda v: (12, v) if v <= 4 else (12, v - 1)},        # Heb 12:4-5 = KJV 12:4
    "Neh": {7: lambda v: (7, v) if v <= 67 else (7, v + 1)},          # KJV 7:68 is not in the Hebrew
    "Isa": {64: lambda v: (64, v + 1)},                               # KJV 64:1 = Heb 63:19b
}


def hebrew_map(code, heb, kjv):
    """Return {(heb_chapter, heb_verse): (kjv_chapter, kjv_verse)} for one book.

    Runs of chapters whose verse totals agree are poured into the KJV slots in order (chapter
    breaks in different places: Malachi 3:19-24 = KJV 4:1-6, Joel 3-4, Jonah 2:1 = KJV 1:17 ...).
    Psalm titles counted as verses are joined to verse 1. Anything else is matched by number.
    """
    mapping = {}
    fixes = HEBREW_FIXES.get(code, {})
    for c, fn in fixes.items():
        for v in heb.get(c, {}):
            mapping[(c, v)] = fn(v)
    chapters = [c for c in sorted(set(kjv) | set(heb)) if c not in fixes]
    keys = lambda c: [(c, v) for v in sorted(heb.get(c, {}))]
    slots = lambda c: [(c, v) for v in sorted(kjv.get(c, {}))]
    if code == "Psa":
        for c in chapters:
            k, s_ = keys(c), slots(c)
            extra = len(k) - len(s_)
            if extra > 0:
                for key in k[: extra + 1]:
                    mapping[key] = s_[0]
                mapping.update(zip(k[extra + 1:], s_[1:]))
            else:
                mapping.update({key: key for key in k})
        return mapping
    i = 0
    while i < len(chapters):
        for j in range(i, min(i + 4, len(chapters))):
            run = chapters[i:j + 1]
            k = [x for c in run for x in keys(c)]
            s_ = [x for c in run for x in slots(c)]
            if len(k) == len(s_):
                mapping.update(zip(k, s_))
                i = j + 1
                break
        else:
            mapping.update({key: key for key in keys(chapters[i])})
            i += 1
    return mapping


def apply_map(mapping, src):
    out = collections.defaultdict(dict)
    for c in sorted(src):
        for v in sorted(src[c]):
            kc, kv = mapping.get((c, v), (c, v))
            out[kc][kv] = (out[kc].get(kv, "") + " " + src[c][v]).strip()
    return out


def normalise_jps(name, src):
    """This JPS edition prints each Decalogue's short commandments as a single verse; restore Hebrew numbering."""
    merged = {"Exodus": (20, 13), "Deuteronomy": (5, 17)}
    if name in merged:
        c, at = merged[name]
        src = dict(src)
        src[c] = {(v + 3 if v > at else v): t for v, t in src[c].items()}
    return src


# ---------------------------------------------------------------------------
# Markdown output
# ---------------------------------------------------------------------------
def render_chapter(book, chapter, texts, sources, notes=None):
    """texts: {tag: {verse: text}} for the tags this testament has."""
    slug, en, el, _ = book
    notes = notes or {}
    tags = [t for t in TAGS if t in sources]
    labels = {"GRC": "Ancient Greek", "ELL": "Modern Greek", "KJV": "English", "HEB": "Hebrew", "JPS": "Jewish English"}
    lines = [f"# {en} {chapter} · {el} {chapter}", "", "<!--",
             f"Format: each verse starts with a '## <number>' heading followed by up to {len(tags)} lines:"]
    lines += [f"  **{t}** {labels[t]} ({sources[t]})" for t in tags]
    lines += ["Any other text under a verse is shown as a note on that verse.",
              "Anything under '## Notes' is free-form markdown for your own study notes.", "-->", ""]
    verses = sorted(set().union(*[set(texts.get(t, {})) for t in tags]))
    for v in verses:
        lines += [f"## {v}", ""]
        for t in tags:
            lines += [f"**{t}** {texts.get(t, {}).get(v, '')}".rstrip(), ""]
        for n in notes.get(v, []):
            lines += [n, ""]
    lines += ["## Notes", "", ""]
    return "\n".join(lines)


def add_missing_lines(path, texts, tags):
    """Insert version lines that an existing chapter file lacks, keeping everything else as is."""
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    out, i, changed = [], 0, False
    labels = {"HEB": "Hebrew", "JPS": "Jewish English"}
    kjv_doc = next((k for k, l in enumerate(lines) if l.startswith("  **KJV** ")), None)
    if kjv_doc is not None:
        doc = [f"  **{t}** {labels[t]} ({SOURCES['ot'][t]})" for t in labels
               if t in tags and not any(l.startswith(f"  **{t}** ") for l in lines)]
        if doc:
            lines[kjv_doc + 1:kjv_doc + 1] = doc
            changed = True
    verse_re = re.compile(r"^##\s+(\d+)\s*$")
    while i < len(lines):
        m = verse_re.match(lines[i])
        out.append(lines[i])
        i += 1
        if not m:
            continue
        v = int(m[1])
        block = []
        while i < len(lines) and not lines[i].startswith("## "):
            block.append(lines[i])
            i += 1
        present = {t for t in tags if any(l.startswith(f"**{t}**") for l in block)}
        missing = [t for t in tags if t not in present and texts.get(t, {}).get(v)]
        if missing:
            last = max((k for k, l in enumerate(block) if re.match(r"^\*\*[A-Z]{3}\*\*", l)), default=-1)
            insert = []
            for t in missing:
                insert += ["", f"**{t}** {texts[t][v]}"]
            block[last + 1:last + 1] = insert
            changed = True
        out += block
    if changed:
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(out))
    return changed


def write_testament(key, out_dir, books, grc_for, force):
    title = {"nt": "New Testament · Καινή Διαθήκη", "ot": "Old Testament · Παλαιά Διαθήκη"}[key]
    print(f"Building {title} ...")
    kjv_all = load_scrollmapper("KJV", key)
    ell_all = load_scrollmapper("GreVamvas", key)
    manifest, written, skipped, updated = [], 0, 0, 0
    if key == "ot":
        wlc = load_by_name("WLC", clean_wlc)
        jps = load_by_name("JPS")
    for i, book in enumerate(books):
        slug, en, el, code = book
        print(f"  {en}")
        grc_book, notes = grc_for(code, kjv_all[i])
        texts = {"GRC": grc_book, "ELL": ell_all[i], "KJV": kjv_all[i]}
        if key == "ot":
            kjv_name = _SM_CACHE["KJV"][i]["name"]
            mapping = hebrew_map(code, wlc[kjv_name], kjv_all[i])
            texts["HEB"] = apply_map(mapping, wlc[kjv_name])
            texts["JPS"] = apply_map(mapping, normalise_jps(kjv_name, jps[kjv_name]))
        n_chapters = max(len(kjv_all[i]), len(ell_all[i]), max(grc_book or [0]))
        pad = max(2, len(str(n_chapters)))
        folder_name = f"{i + 1:02d}-{slug}"
        folder = os.path.join(out_dir, folder_name)
        os.makedirs(folder, exist_ok=True)
        for c in range(1, n_chapters + 1):
            path = os.path.join(folder, f"chapter-{c:0{pad}d}.md")
            ch_texts = {t: texts[t].get(c, {}) for t in texts}
            if os.path.exists(path) and not force:
                updated += add_missing_lines(path, ch_texts, [t for t in TAGS if t in SOURCES[key]])
                skipped += 1
                continue
            ch_notes = {v: ns for (nc, v), ns in notes.items() if nc == c}
            with open(path, "w", encoding="utf-8") as f:
                f.write(render_chapter(book, c, ch_texts, SOURCES[key], ch_notes))
            written += 1
        readme = os.path.join(folder, "README.md")
        if not os.path.exists(readme) or force:
            with open(readme, "w", encoding="utf-8") as f:
                f.write(f"# {en} · {el}\n\n")
                f.write("Each chapter file contains the Ancient Greek (GRC), Modern Greek (ELL) and King James (KJV) "
                        + ("text, plus the Hebrew (HEB) and JPS 1917 (JPS), " if key == "ot" else "text ")
                        + "verse by verse.\n\n")
                for c in range(1, n_chapters + 1):
                    f.write(f"- [Chapter {c}](chapter-{c:0{pad}d}.md)\n")
        entry = {"slug": slug, "folder": folder_name, "name": en, "greek": el, "chapters": n_chapters}
        if pad != 2:
            entry["pad"] = pad
        manifest.append(entry)

    with open(os.path.join(out_dir, "books.json"), "w", encoding="utf-8") as f:
        json.dump({"testament": title, "sources": SOURCES[key], "books": manifest}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    with open(os.path.join(out_dir, "README.md"), "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n")
        for b in manifest:
            f.write(f"- [{b['name']} · {b['greek']}]({b['folder']}/README.md) — {b['chapters']} chapters\n")
    print(f"  {written} chapter files written, {skipped} existing files kept ({updated} given missing lines).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="overwrite existing chapter files")
    ap.add_argument("--only", choices=["ot", "nt"], help="build just one testament")
    args = ap.parse_args()

    if args.only in (None, "ot"):
        lxx = load_lxx()
        write_testament("ot", OT_DIR, OT_BOOKS, lambda code, kjv: align_lxx(code, lxx[code], kjv), args.force)
    if args.only in (None, "nt"):
        write_testament("nt", NT_DIR, NT_BOOKS, lambda code, kjv: (load_rp(code), {}), args.force)


if __name__ == "__main__":
    main()
