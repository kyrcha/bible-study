# Bible Study · Καινή Διαθήκη

The 27 books of the New Testament, verse by verse, in three versions:

| Tag | Version | Source (public domain) |
|-----|---------|------------------------|
| `GRC` | Ancient Greek — Robinson‑Pierpont Byzantine Textform 2018 | [byztxt/byzantine-majority-text](https://github.com/byztxt/byzantine-majority-text) |
| `ELL` | Modern Greek — Neophytos Vamvas translation (1850) | [scrollmapper/bible_databases](https://github.com/scrollmapper/bible_databases) |
| `KJV` | King James Version (1769) | [scrollmapper/bible_databases](https://github.com/scrollmapper/bible_databases) |

## Layout

```
new-testament/
  books.json                 # book list used by the website
  README.md                  # index of all books
  01-matthew/
    README.md                # index of chapters
    chapter-01.md
    …
  …
  27-revelation/
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

`scripts/build_books.py` downloads the sources and creates any missing chapter files. It never overwrites
existing files unless you pass `--force` (which discards manual edits).
