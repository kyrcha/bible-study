/* Bible Study site.
 *
 * Content lives in markdown files under new-testament/<NN-book>/chapter-XX.md.
 * Without a token the files are fetched from this site (GitHub Pages redeploys on every push).
 * With a token they are read and written through the GitHub Contents API, so you always
 * see the latest commit and can save edits straight back to the repository.
 */
(() => {
  "use strict";

  // `def` is whether a column is shown until the reader changes it; Hebrew and JPS start hidden.
  const COLS = [
    { tag: "GRC", label: "Αρχαία Ελληνικά", lang: "grc", def: "1" },
    { tag: "ELL", label: "Νέα Ελληνικά", lang: "el", def: "1" },
    { tag: "KJV", label: "English", lang: "en", def: "1" },
    { tag: "HEB", label: "עברית · Hebrew", lang: "he", def: "0" },
    { tag: "JPS", label: "Jewish English", lang: "en", def: "0" },
  ];
  const TAGS = COLS.map((c) => c.tag).join("|");
  const TESTAMENTS = [
    { root: "old-testament", title: "Παλαιά Διαθήκη", en: "Old Testament" },
    { root: "new-testament", title: "Καινή Διαθήκη", en: "New Testament" },
  ];
  const POLL_MS = 60_000;

  const $ = (sel) => document.querySelector(sel);
  const view = $("#view");
  const statusEl = $("#status");

  // ---------- settings ----------
  const store = {
    get(k, d = "") { try { return localStorage.getItem("bs." + k) ?? d; } catch { return d; } },
    set(k, v) { try { v ? localStorage.setItem("bs." + k, v) : localStorage.removeItem("bs." + k); } catch {} },
  };

  function detectRepo() {
    const m = location.hostname.match(/^([^.]+)\.github\.io$/i);
    if (m) {
      const first = location.pathname.split("/").filter(Boolean)[0];
      return { owner: m[1], repo: first || `${m[1]}.github.io` };
    }
    return { owner: "kyrcha", repo: "bible-study" };
  }

  const cfg = {
    get owner() { return store.get("owner") || detectRepo().owner; },
    get repo() { return store.get("repo") || detectRepo().repo; },
    get branch() { return store.get("branch"); },
    get token() { return store.get("token"); },
  };

  let defaultBranch = null;
  async function branch() {
    if (cfg.branch) return cfg.branch;
    if (defaultBranch) return defaultBranch;
    const r = await gh(`/repos/${cfg.owner}/${cfg.repo}`);
    defaultBranch = r.default_branch;
    return defaultBranch;
  }

  // ---------- GitHub API ----------
  async function gh(path, opts = {}) {
    const res = await fetch("https://api.github.com" + path, {
      ...opts,
      cache: "no-store",
      headers: {
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        ...(cfg.token ? { Authorization: `Bearer ${cfg.token}` } : {}),
        ...(opts.body ? { "Content-Type": "application/json" } : {}),
      },
    });
    if (!res.ok) {
      let msg = res.statusText;
      try { msg = (await res.json()).message || msg; } catch {}
      const err = new Error(`GitHub ${res.status}: ${msg}`);
      err.status = res.status;
      throw err;
    }
    return res.json();
  }

  const b64encode = (str) => {
    const bytes = new TextEncoder().encode(str);
    let bin = "";
    for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    return btoa(bin);
  };
  const b64decode = (b64) => {
    const bin = atob(b64.replace(/\s/g, ""));
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return new TextDecoder().decode(bytes);
  };

  /** Load a repository file. Returns { text, sha } (sha only in API mode). */
  async function loadFile(path) {
    if (cfg.token) {
      const ref = await branch();
      const r = await gh(`/repos/${cfg.owner}/${cfg.repo}/contents/${encodePath(path)}?ref=${encodeURIComponent(ref)}`);
      return { text: b64decode(r.content), sha: r.sha };
    }
    const res = await fetch(path, { cache: "no-cache" });
    if (!res.ok) throw new Error(`Could not load ${path} (${res.status})`);
    return { text: await res.text(), sha: null };
  }

  async function saveFile(path, text, sha, message) {
    const ref = await branch();
    const r = await gh(`/repos/${cfg.owner}/${cfg.repo}/contents/${encodePath(path)}`, {
      method: "PUT",
      body: JSON.stringify({ message, content: b64encode(text), sha, branch: ref }),
    });
    return r.content.sha;
  }

  const encodePath = (p) => p.split("/").map(encodeURIComponent).join("/");

  // ---------- markdown chapter format ----------
  const VERSE_RE = /^##\s+(\d+)\s*$/;
  const NOTES_RE = /^##\s+Notes\s*$/i;
  const LINE_RE = new RegExp(`^\\*\\*(${TAGS})\\*\\*\\s?(.*)$`);

  function parseChapter(md) {
    const lines = md.replace(/\r\n/g, "\n").split("\n");
    const out = { title: "", verses: [], notes: "" };
    let cur = null, inNotes = false, inComment = false;
    const notes = [];
    for (const line of lines) {
      if (inNotes) { notes.push(line); continue; }
      if (inComment) { if (line.includes("-->")) inComment = false; continue; }
      if (line.trim().startsWith("<!--")) { if (!line.includes("-->")) inComment = true; continue; }
      if (!out.title && /^#\s+/.test(line)) { out.title = line.replace(/^#\s+/, "").trim(); continue; }
      if (NOTES_RE.test(line)) { inNotes = true; cur = null; continue; }
      const vm = line.match(VERSE_RE);
      if (vm) { cur = { n: +vm[1], extra: [] }; COLS.forEach((c) => (cur[c.tag] = "")); out.verses.push(cur); continue; }
      if (!cur) continue;
      const lm = line.match(LINE_RE);
      if (lm) cur[lm[1]] = lm[2].trim();
      else cur.extra.push(line);
    }
    out.notes = notes.join("\n").trim();
    for (const v of out.verses) v.extra = v.extra.join("\n").trim();
    return out;
  }

  /** Replace the text of one translation line of one verse, leaving everything else untouched. */
  function patchVerse(md, n, values) {
    const lines = md.replace(/\r\n/g, "\n").split("\n");
    let start = lines.findIndex((l) => (l.match(VERSE_RE) || [])[1] == n);
    if (start < 0) throw new Error(`Verse ${n} not found in file`);
    let end = start + 1;
    while (end < lines.length && !/^##\s/.test(lines[end])) end++;
    for (const [tag, text] of Object.entries(values)) {
      const clean = text.replace(/\s*\n\s*/g, " ").trim();
      const idx = lines.slice(start + 1, end).findIndex((l) => l.startsWith(`**${tag}**`));
      const newLine = `**${tag}** ${clean}`.trimEnd();
      if (idx >= 0) lines[start + 1 + idx] = newLine;
      else { lines.splice(end, 0, newLine, ""); end += 2; }
    }
    return lines.join("\n");
  }

  function patchNotes(md, notes) {
    const lines = md.replace(/\r\n/g, "\n").split("\n");
    const idx = lines.findIndex((l) => NOTES_RE.test(l));
    const head = idx >= 0 ? lines.slice(0, idx) : [...lines, ""];
    while (head.length && head[head.length - 1].trim() === "") head.pop();
    return [...head, "", "## Notes", "", notes.trim(), ""].join("\n");
  }

  // ---------- rendering helpers ----------
  const esc = (s) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  // Minimal, escape-first markdown (no raw HTML allowed): bold, italic, code, links, headings, lists, quotes.
  function mdInline(s) {
    return esc(s)
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*])\*([^*\s][^*]*?)\*/g, "$1<em>$2</em>")
      .replace(/\[([^\]]+)\]\(((?:https?:\/\/|#)[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  }
  function md(src) {
    const out = [];
    let list = null, para = [];
    const flushPara = () => { if (para.length) out.push(`<p>${mdInline(para.join(" "))}</p>`); para = []; };
    const flushList = () => { if (list) out.push(`<${list.tag}>${list.items.map((i) => `<li>${mdInline(i)}</li>`).join("")}</${list.tag}>`); list = null; };
    for (const line of src.split("\n")) {
      let m;
      if (!line.trim()) { flushPara(); flushList(); }
      else if ((m = line.match(/^(#{1,6})\s+(.*)$/))) { flushPara(); flushList(); const l = Math.min(m[1].length + 2, 6); out.push(`<h${l}>${mdInline(m[2])}</h${l}>`); }
      else if ((m = line.match(/^\s*([-*+]|\d+[.)])\s+(.*)$/))) {
        flushPara();
        const tag = /\d/.test(m[1]) ? "ol" : "ul";
        if (!list || list.tag !== tag) { flushList(); list = { tag, items: [] }; }
        list.items.push(m[2]);
      }
      else if ((m = line.match(/^>\s?(.*)$/))) { flushPara(); flushList(); out.push(`<blockquote>${mdInline(m[1])}</blockquote>`); }
      else { flushList(); para.push(line.trim()); }
    }
    flushPara(); flushList();
    return out.join("");
  }

  function setStatus(msg, kind = "") {
    if (!msg) { statusEl.hidden = true; return; }
    statusEl.hidden = false;
    statusEl.className = "status " + kind;
    statusEl.textContent = msg;
  }

  /** Columns the current testament has (the Hebrew and JPS exist only for the Old Testament). */
  function bookCols() {
    return COLS.filter((c) => !state.book || state.book.testament.sources[c.tag]);
  }
  function visibleCols() {
    return bookCols().filter((c) => store.get("col." + c.tag, c.def) === "1");
  }
  function updateToggles() {
    const have = new Set(bookCols().map((c) => c.tag));
    document.querySelectorAll("[data-col]").forEach((cb) => (cb.closest("label").hidden = !have.has(cb.dataset.col)));
  }

  // ---------- state ----------
  let books = [];
  const state = { book: null, chapter: 0, verse: 0, path: "", text: "", sha: null, editing: false };

  async function init() {
    document.querySelectorAll("[data-col]").forEach((cb) => {
      cb.checked = store.get("col." + cb.dataset.col, COLS.find((c) => c.tag === cb.dataset.col).def) === "1";
      cb.addEventListener("change", () => { store.set("col." + cb.dataset.col, cb.checked ? "1" : "0"); renderChapter(); });
    });
    $("#settingsBtn").addEventListener("click", openSettings);
    $("#prevBtn").addEventListener("click", () => step(-1));
    $("#nextBtn").addEventListener("click", () => step(1));
    $("#bookSelect").addEventListener("change", (e) => go(e.target.value, 1));
    $("#chapterSelect").addEventListener("change", (e) => go(state.book.slug, +e.target.value));
    window.addEventListener("hashchange", route);
    document.addEventListener("visibilitychange", () => { if (!document.hidden) poll(); });
    setInterval(poll, POLL_MS);

    try {
      const lists = await Promise.all(TESTAMENTS.map(async (t) => {
        const data = JSON.parse((await loadFile(`${t.root}/books.json`)).text);
        t.sources = data.sources || {};
        return data.books.map((b) => ({ ...b, testament: t }));
      }));
      books = lists.flat();
    } catch (e) {
      setStatus("Could not load the book list: " + e.message, "error");
      return;
    }
    $("#bookSelect").innerHTML = TESTAMENTS.map((t) => `<optgroup label="${t.title} · ${t.en}">${
      books.filter((b) => b.testament === t).map((b) => `<option value="${b.slug}">${esc(b.greek)} · ${esc(b.name)}</option>`).join("")
    }</optgroup>`).join("");
    route();
  }

  function go(slug, ch, v) { location.hash = `#/${slug}/${ch}${v ? "/" + v : ""}`; }

  function step(d) {
    if (!state.book) return;
    let i = books.indexOf(state.book), c = state.chapter + d;
    if (c < 1) { if (i === 0) return; i--; c = books[i].chapters; }
    else if (c > state.book.chapters) { if (i === books.length - 1) return; i++; c = 1; }
    go(books[i].slug, c);
  }

  async function route() {
    const [slug, ch, v] = location.hash.replace(/^#\/?/, "").split("/");
    const book = books.find((b) => b.slug === slug);
    if (!book) return renderHome();
    const chapter = Math.min(Math.max(+ch || 1, 1), book.chapters);
    const same = state.book === book && state.chapter === chapter;
    Object.assign(state, { book, chapter, verse: +v || 0 });
    updateToggles();
    $("#bookSelect").value = book.slug;
    $("#chapterSelect").innerHTML = Array.from({ length: book.chapters }, (_, i) => `<option value="${i + 1}">${i + 1}</option>`).join("");
    $("#chapterSelect").value = chapter;
    if (!same) await loadChapter();
    else renderChapter();
  }

  function chapterPath(book, ch) { return `${book.testament.root}/${book.folder}/chapter-${String(ch).padStart(book.pad || 2, "0")}.md`; }

  async function loadChapter() {
    state.path = chapterPath(state.book, state.chapter);
    state.editing = false;
    view.innerHTML = `<p class="muted">Loading…</p>`;
    try {
      const f = await loadFile(state.path);
      state.text = f.text; state.sha = f.sha;
      setStatus("");
      renderChapter();
      if (!state.verse) window.scrollTo(0, 0);
    } catch (e) {
      setStatus(e.message, "error");
      view.innerHTML = "";
    }
  }

  /** Re-fetch the open chapter and re-render if it changed elsewhere (e.g. edited on GitHub). */
  async function poll() {
    if (!state.path || state.editing || document.hidden) return;
    try {
      const f = await loadFile(state.path);
      if (f.text !== state.text) {
        state.text = f.text; state.sha = f.sha;
        renderChapter();
        setStatus("This chapter was updated — showing the latest version.");
        setTimeout(() => setStatus(""), 4000);
      }
    } catch { /* ignore transient errors */ }
  }

  // ---------- views ----------
  function renderHome() {
    state.book = null; state.path = "";
    updateToggles();
    $("#chapterSelect").innerHTML = "";
    view.innerHTML = `
      <div class="home">
        <h1>Αγία Γραφή · Holy Bible</h1>
        <p class="muted">Ancient Greek (Septuagint and Robinson‑Pierpont), Modern Greek (Vamvas 1850) and the King James Version, verse by verse.
        Every chapter is a markdown file in the repository — edit it on GitHub or right here.</p>
        ${TESTAMENTS.map((t) => `
          <h2 class="testament">${t.title} <span class="muted">· ${t.en}</span></h2>
          <div class="book-grid">
            ${books.filter((b) => b.testament === t).map((b) => `<a class="book-card" href="#/${b.slug}/1"><span class="gr">${esc(b.greek)}</span><span class="en">${esc(b.name)} · ${b.chapters} ch.</span></a>`).join("")}
          </div>`).join("")}
      </div>`;
  }

  function renderChapter() {
    if (!state.book) return;
    const ch = parseChapter(state.text);
    const cols = visibleCols();
    const canEdit = !!cfg.token;
    const ghUrl = `https://github.com/${cfg.owner}/${cfg.repo}/edit/${cfg.branch || defaultBranch || "main"}/${state.path}`;
    view.style.setProperty("--cols", cols.length || 1);
    view.innerHTML = `
      <div class="chapter-head">
        <h1>${esc(state.book.greek)} ${state.chapter}</h1>
        <span class="muted">${esc(state.book.name)} ${state.chapter}</span>
        <div class="actions">
          <a class="btn" href="${ghUrl}" target="_blank" rel="noopener">Edit on GitHub</a>
          <button type="button" id="rawBtn" ${canEdit ? "" : "disabled title='Connect GitHub (⚙) to edit here'"}>Edit markdown</button>
        </div>
      </div>
      <div class="colheads"><span></span>${cols.map((c) => `<span>${c.label} <span class="muted">· ${esc(state.book.testament.sources[c.tag] || "")}</span></span>`).join("")}<span></span></div>
      <div id="verses">
        ${ch.verses.map((v) => verseRow(v, cols, canEdit)).join("")}
      </div>
      <section class="notes">
        <h2>Σημειώσεις · Notes <button type="button" id="notesBtn" ${canEdit ? "" : "disabled"}>Edit</button></h2>
        <div id="notesBody">${ch.notes ? md(ch.notes) : `<p class="muted">No notes yet.</p>`}</div>
      </section>
      <div class="pager">
        <button type="button" id="pPrev">‹ Previous</button>
        <button type="button" id="pNext">Next ›</button>
      </div>`;

    $("#pPrev").onclick = () => step(-1);
    $("#pNext").onclick = () => step(1);
    $("#rawBtn").onclick = () => editRaw();
    $("#notesBtn").onclick = () => editNotes(ch.notes);
    view.querySelectorAll(".edit-btn").forEach((b) => (b.onclick = () => editVerse(+b.dataset.v)));

    if (state.verse) {
      const el = document.getElementById("v" + state.verse);
      if (el) { el.classList.add("target"); el.scrollIntoView({ block: "center" }); }
    }
  }

  function verseRow(v, cols, canEdit) {
    return `
      <div class="verse-row" id="v${v.n}">
        <a class="num" href="#/${state.book.slug}/${state.chapter}/${v.n}">${v.n}</a>
        ${cols.map((c) => `<div class="txt ${v[c.tag] ? "" : "empty"}" lang="${c.lang}"${c.lang === "he" ? ' dir="rtl"' : ""}><span class="lbl">${c.tag}</span>${mdInline(v[c.tag])}</div>`).join("")}
        ${canEdit ? `<button class="edit-btn" data-v="${v.n}" title="Edit verse ${v.n}" aria-label="Edit verse ${v.n}">✎</button>` : "<span></span>"}
        ${v.extra ? `<div class="extra">${md(v.extra)}</div>` : ""}
      </div>`;
  }

  // ---------- editing ----------
  function editVerse(n) {
    const v = parseChapter(state.text).verses.find((x) => x.n === n);
    const row = document.getElementById("v" + n);
    state.editing = true;
    row.innerHTML = `
      <span class="num">${n}</span>
      <div class="editor">
        ${bookCols().map((c) => `<label>${c.label}<textarea rows="3" data-tag="${c.tag}" lang="${c.lang}"${c.lang === "he" ? ' dir="rtl"' : ""}>${esc(v[c.tag])}</textarea></label>`).join("")}
        <div class="row"><button type="button" data-a="cancel">Cancel</button><button type="button" class="primary" data-a="save">Save</button></div>
      </div>`;
    row.querySelector("textarea").focus();
    row.querySelector('[data-a="cancel"]').onclick = () => { state.editing = false; renderChapter(); };
    row.querySelector('[data-a="save"]').onclick = async (e) => {
      const values = {};
      row.querySelectorAll("textarea").forEach((t) => (values[t.dataset.tag] = t.value));
      e.target.disabled = true;
      await commit((text) => patchVerse(text, n, values), `Edit ${state.book.name} ${state.chapter}:${n}`, true);
      e.target.disabled = false;
    };
  }

  function editNotes(current) {
    state.editing = true;
    const body = $("#notesBody");
    body.innerHTML = `
      <div class="editor" style="grid-column:auto">
        <textarea rows="10" id="notesText" placeholder="Markdown supported">${esc(current)}</textarea>
        <div class="row"><button type="button" data-a="cancel">Cancel</button><button type="button" class="primary" data-a="save">Save notes</button></div>
      </div>`;
    $("#notesText").focus();
    body.querySelector('[data-a="cancel"]').onclick = () => { state.editing = false; renderChapter(); };
    body.querySelector('[data-a="save"]').onclick = async (e) => {
      const notes = $("#notesText").value;
      e.target.disabled = true;
      await commit((text) => patchNotes(text, notes), `Update notes for ${state.book.name} ${state.chapter}`, true);
      e.target.disabled = false;
    };
  }

  function editRaw() {
    state.editing = true;
    const base = state.sha;
    view.innerHTML = `
      <div class="chapter-head"><h1>${esc(state.book.name)} ${state.chapter}</h1><span class="muted">${esc(state.path)}</span></div>
      <textarea class="raw" id="rawText" spellcheck="false">${esc(state.text)}</textarea>
      <div class="editor" style="grid-column:auto;margin-top:8px">
        <div class="row"><button type="button" data-a="cancel">Cancel</button><button type="button" class="primary" data-a="save">Commit</button></div>
      </div>`;
    view.querySelector('[data-a="cancel"]').onclick = () => { state.editing = false; renderChapter(); };
    view.querySelector('[data-a="save"]').onclick = async (e) => {
      const raw = $("#rawText").value;
      e.target.disabled = true;
      // Whole-file edits are not merged automatically: refuse if the file changed meanwhile.
      await commit(() => raw, `Edit ${state.book.name} ${state.chapter}`, false, base);
      e.target.disabled = false;
    };
  }

  /**
   * Fetch the latest file, apply `transform`, and commit.
   * If `mergeable`, a concurrent change is handled by re-applying the transform to the newest text.
   */
  async function commit(transform, message, mergeable, baseSha) {
    if (!cfg.token) { openSettings(); return; }
    setStatus("Saving…");
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        const latest = await loadFile(state.path);
        if (!mergeable && baseSha && latest.sha !== baseSha) {
          setStatus("The file was changed by someone else since you started editing. Copy your text, cancel, and try again.", "error");
          return;
        }
        const next = transform(latest.text);
        if (next === latest.text) { setStatus("No changes."); state.editing = false; state.text = latest.text; state.sha = latest.sha; renderChapter(); return; }
        const sha = await saveFile(state.path, next, latest.sha, message);
        Object.assign(state, { text: next, sha, editing: false });
        renderChapter();
        setStatus("Saved and committed to GitHub ✓");
        setTimeout(() => setStatus(""), 4000);
        return;
      } catch (e) {
        if ((e.status === 409 || e.status === 422) && mergeable && attempt < 2) continue;
        setStatus("Save failed: " + e.message, "error");
        return;
      }
    }
  }

  // ---------- settings dialog ----------
  function openSettings() {
    const dlg = $("#settingsDialog");
    const f = $("#settingsForm");
    f.owner.value = cfg.owner; f.repo.value = cfg.repo; f.branch.value = cfg.branch; f.token.value = cfg.token;
    dlg.showModal();
    dlg.onclose = async () => {
      if (dlg.returnValue === "save") {
        store.set("owner", f.owner.value.trim()); store.set("repo", f.repo.value.trim());
        store.set("branch", f.branch.value.trim()); store.set("token", f.token.value.trim());
      } else if (dlg.returnValue === "clear") {
        store.set("token", "");
      } else return;
      defaultBranch = null;
      if (cfg.token) {
        try { await branch(); setStatus(`Connected to ${cfg.owner}/${cfg.repo} (${await branch()}).`); }
        catch (e) { setStatus("GitHub connection failed: " + e.message, "error"); }
      } else setStatus("Read‑only mode.");
      if (state.book) loadChapter();
    };
  }

  // Exposed for tests.
  window.BibleStudy = { parseChapter, patchVerse, patchNotes, md, mdInline };
  init();
})();
