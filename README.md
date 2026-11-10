# Bible Study · Αγία Γραφή

The 39 books of the Old Testament and the 27 books of the New Testament, verse by verse, in three versions:

| Tag | Version | Source |
|-----|---------|--------|
| `GRC` | Ancient Greek, Old Testament — Septuagint, H. B. Swete edition (1909–1930) | [eliranwong/LXX-Swete-1930](https://github.com/eliranwong/LXX-Swete-1930) |
| `GRC` | Ancient Greek, New Testament — Robinson‑Pierpont Byzantine Textform 2018 | [byztxt/byzantine-majority-text](https://github.com/byztxt/byzantine-majority-text) |
| `ELL` | Modern Greek — Neophytos Vamvas translation (1850) | [scrollmapper/bible_databases](https://github.com/scrollmapper/bible_databases) |
| `KJV` | King James Version (1769) | [scrollmapper/bible_databases](https://github.com/scrollmapper/bible_databases) |

All of these texts are in the public domain. The Swete digitisation is distributed in its repository under the GPL‑3.0.

## Layout

```
old-testament/
  books.json                 # book list used by the website
  README.md                  # index of all books
  01-genesis/
    README.md                # index of chapters
    chapter-01.md
    …
  19-psalms/
    chapter-001.md           # Psalms uses three digits (150 psalms, plus Psalm 151)
  …
  39-malachi/
new-testament/
  01-matthew/ … 27-revelation/
```

Each chapter file looks like this:

```markdown
# John 3 · Κατά Ιωάννην 3

## 16

**GRC** Οὕτως γὰρ ἠγάπησεν ὁ θεὸς τὸν κόσμον, …

**ELL** Διότι τόσον ηγάπησεν ο Θεός τον κόσμον, …

**KJV** For God so loved the world, …

A note about this verse — any other text under a verse heading is shown as a verse note.

## Notes

Free‑form markdown study notes for the whole chapter.
```

Rules the website relies on: a verse starts with `## <number>`, each version is a line starting with
`**GRC**`, `**ELL**` or `**KJV**`, and `## Notes` (if present) is the last section. Everything else is up to you.

Where the editions number verses differently (e.g. Romans 16:25‑27, which the Byzantine text places after 14:23,
or verses such as Luke 17:36 and Acts 24:7 that it does not contain), the missing version is simply left empty.

### Old Testament alignment

All three versions use the KJV verse numbering, which Vamvas shares. The Septuagint text is rearranged to fit it:

- **Psalms:** Septuagint numbering is converted (LXX 22 → Psalm 23, LXX 9 → Psalms 9–10, LXX 113 → 114–115,
  LXX 114–115 → 116, LXX 146–147 → 147). Psalm titles are joined to verse 1, as in the KJV. Psalm 151 has only the Greek.
- **Jeremiah:** the Septuagint's different chapter order (oracles against the nations in chapters 25–31) is mapped back to
  the Hebrew/English order.
- **Daniel:** Theodotion's text. The Prayer of Azariah and Song of the Three (LXX 3:24–90) appear as a note on 3:23.
- **1 Kings 20–21, Malachi 4,** and chapter breaks that fall in different places (e.g. Jonah 1:17 = LXX 2:1) are adjusted.
- The Septuagint really does differ from the Hebrew text in places (Exodus 35–40, 1 Samuel 17–18, 1 Kings, Job, Proverbs,
  Jeremiah, Esther additions). Verses with no Greek counterpart have an empty `GRC` line; Greek‑only verses have empty
  `ELL`/`KJV` lines. In books whose order differs (notably Proverbs 24–31) verses are matched by number only.

## Website

`index.html` + `assets/` is a static site that reads the markdown files directly — there is no build step, so
any change to a chapter file shows up on the site.

- **Reading:** works with no setup. Pick a book and chapter, toggle columns, link to a verse
  (`#/john/3/16`). The open chapter is re‑checked every minute and refreshes automatically when it changes.
- **Editing on GitHub:** use the *Edit on GitHub* button (or edit any `.md` file in the repo). Pushing to
  `main` redeploys the site.
- **Editing on the site:** click ⚙ and paste a
  [fine‑grained personal access token](https://github.com/settings/personal-access-tokens/new) limited to this
  repository with **Contents: Read and write**. The token stays in your browser's local storage. You can then
  edit a single verse (✎), the chapter notes, or the whole markdown file; each save is a commit. In this mode the
  site reads straight from the GitHub API, so it always shows the latest commit, even before Pages redeploys.
  Verse and notes edits are re‑applied on top of the newest version if someone else changed the file meanwhile.

### Deploying with GitHub Pages

1. Merge into `main`.
2. In **Settings → Pages**, set **Source** to **GitHub Actions**.
3. The workflow in `.github/workflows/pages.yml` publishes the site on every push to `main`
   (at `https://<owner>.github.io/bible-study/`).

### Running locally

```sh
python3 -m http.server 8000
# open http://localhost:8000
```

## Regenerating the text

`scripts/build_books.py` downloads the sources and creates any missing chapter files (`--only ot` or `--only nt` to build
one Testament). It never overwrites
existing files unless you pass `--force` (which discards manual edits).
