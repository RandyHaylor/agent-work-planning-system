"""Builds the phone labelling page from samples.json (labels saved to the artifact's db, collection `labels`,
doc id = sample id, body {label: backed|guess|neutral, note}).
Usage: python3 -I build_page.py OUT.html"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
samples = json.loads((HERE / "samples.json").read_text())
data = json.dumps([{"id": s["id"], "doc": s["doc"].replace("planning/", ""), "sentence": s["sentence"],
                    "quotes": s["quotes"]} for s in samples]).replace("<", "\\u003c")

PAGE = r"""<title>Claim Labelling</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* Layout: one column of review cards; a sticky progress bar; three big answer buttons per card. */
:root {
  --bg: #f5f6f4; --surface: #ffffff; --fg: #1d2420; --muted: #5d6862; --line: #d9ddd8;
  --accent: #2f6b4f; --backed: #2f6b4f; --guess: #b0412e; --neutral: #6a6f8a; --quote-bg: #eef2ee;
  --sans: "IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, "SFMono-Regular", Menlo, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #121614; --surface: #1b211e; --fg: #e4e9e5; --muted: #9aa59f; --line: #2e3632;
  --accent: #7cc49f; --backed: #7cc49f; --guess: #f08a76; --neutral: #a9adcc; --quote-bg: #222a26; color-scheme: dark } }
:root[data-theme="dark"] {
  --bg: #121614; --surface: #1b211e; --fg: #e4e9e5; --muted: #9aa59f; --line: #2e3632;
  --accent: #7cc49f; --backed: #7cc49f; --guess: #f08a76; --neutral: #a9adcc; --quote-bg: #222a26; color-scheme: dark }
body { background: var(--bg); color: var(--fg); font-family: var(--sans); font-size: 16px; line-height: 1.5;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  padding-block: 0 48px; }
body::before { content: ""; position: fixed; inset: 0 0 auto; height: env(safe-area-inset-top, 0px); z-index: 10; background: var(--bg); }
main { max-width: 680px; margin: 0 auto; display: grid; gap: 16px; }
header.top { position: sticky; top: env(safe-area-inset-top, 0px); z-index: 5; background: var(--bg);
  padding-block: 14px 10px; border-bottom: 1px solid var(--line); display: grid; gap: 8px; }
h1 { font-size: 1.25rem; margin: 0; text-wrap: balance; }
.how { color: var(--muted); font-size: 0.9rem; margin: 0; }
.bar { height: 6px; background: var(--line); border-radius: 3px; overflow: hidden; }
.bar > i { display: block; height: 100%; background: var(--accent); width: 0; transition: width .2s; }
.count { font-family: var(--mono); font-size: 0.85rem; color: var(--muted); font-variant-numeric: tabular-nums; }
.status { font-size: 0.85rem; color: var(--muted); }
.card { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 16px; display: grid; gap: 12px; }
.card.done { border-color: var(--accent); }
.meta { font-family: var(--mono); font-size: 0.78rem; color: var(--muted); letter-spacing: .02em; }
.claim { font-size: 1.05rem; font-weight: 500; margin: 0; }
.quotes { display: grid; gap: 8px; }
.quotes .lbl { font-size: 0.72rem; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); }
blockquote { margin: 0; padding: 8px 12px; background: var(--quote-bg); border-radius: 6px; font-size: 0.92rem; }
.choices { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.choices button { font: inherit; font-weight: 600; font-size: 0.95rem; padding: 12px 6px; border-radius: 8px; cursor: pointer;
  background: transparent; color: var(--fg); border: 2px solid var(--line); min-width: 0; }
.choices button[data-v="backed"][aria-pressed="true"] { border-color: var(--backed); color: var(--backed); }
.choices button[data-v="guess"][aria-pressed="true"] { border-color: var(--guess); color: var(--guess); }
.choices button[data-v="neutral"][aria-pressed="true"] { border-color: var(--neutral); color: var(--neutral); }
.choices button:focus-visible, textarea:focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }
textarea { font: inherit; font-size: 0.9rem; width: 100%; box-sizing: border-box; min-height: 2.6em; resize: vertical;
  border: 1px solid var(--line); border-radius: 6px; padding: 8px; background: var(--bg); color: var(--fg); }
@media (prefers-reduced-motion: reduce) { .bar > i { transition: none; } }
</style>
<main>
  <header class="top">
    <h1>Is each agent sentence backed by your quotes?</h1>
    <p class="how"><b>Backed</b>: the quotes state or approve everything it says. <b>Guess</b>: it adds or changes something you didn't say. <b>Neutral</b>: it makes no claim (structure, status).</p>
    <div class="bar"><i id="bar"></i></div>
    <div><span class="count" id="count">0 / 0 labelled</span> · <span class="status" id="status">Connecting…</span></div>
  </header>
  <div id="list"></div>
</main>
<script type="application/json" id="samples">__DATA__</script>
<script>
const SAMPLES = JSON.parse(document.getElementById("samples").textContent);
const labels = {};          // id -> {label, note}
let db = null;

function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }

function renderCount() {
  const n = SAMPLES.filter(s => labels[s.id] && labels[s.id].label).length;
  document.getElementById("count").textContent = n + " / " + SAMPLES.length + " labelled";
  document.getElementById("bar").style.width = (100 * n / SAMPLES.length) + "%";
}

function renderCard(card, s) {
  const current = labels[s.id] || {};
  card.classList.toggle("done", !!current.label);
  card.querySelectorAll(".choices button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.v === current.label)));
  const note = card.querySelector("textarea");
  if (document.activeElement !== note) note.value = current.note || "";
}

async function save(id, patch) {
  labels[id] = Object.assign({}, labels[id], patch);
  renderCard(document.getElementById("card-" + id), SAMPLES.find(s => s.id === id));
  renderCount();
  if (!db) { setStatus("Not saved: storage is unavailable in this view."); return; }
  try { await db.collection("labels").doc(id).set({label: labels[id].label || null, note: labels[id].note || ""}); setStatus("Saved"); }
  catch (e) { setStatus("Not saved (" + (e && e.code || "error") + "). Try again."); }
}

function setStatus(t) { document.getElementById("status").textContent = t; }

function build() {
  const list = document.getElementById("list");
  list.style.display = "grid"; list.style.gap = "16px";
  SAMPLES.forEach((s, i) => {
    const card = el("section", "card"); card.id = "card-" + s.id;
    card.append(el("div", "meta", s.id + " · " + s.doc));
    card.append(el("p", "claim", s.sentence));
    const q = el("div", "quotes"); q.append(el("div", "lbl", "Your quotes in the same item"));
    s.quotes.forEach(t => q.append(el("blockquote", null, "“" + t + "”")));
    card.append(q);
    const choices = el("div", "choices");
    [["backed", "Backed"], ["guess", "Guess"], ["neutral", "Neutral"]].forEach(([v, label]) => {
      const b = el("button", null, label); b.type = "button"; b.dataset.v = v; b.id = s.id + "-" + v;
      b.addEventListener("click", () => save(s.id, {label: v})); choices.append(b);
    });
    card.append(choices);
    const note = el("textarea"); note.id = s.id + "-note"; note.placeholder = "Optional note (what's guessed?)";
    let timer = null;
    note.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => save(s.id, {note: note.value}), 800); });
    card.append(note);
    list.append(card);
    renderCard(card, s);
  });
  renderCount();
}

build();

(async () => {
  try { db = await window.claude?.use("db"); } catch (e) { db = null; }
  if (!db) { setStatus("Storage unavailable here; open this page in claude.ai while signed in."); return; }
  const timeout = setTimeout(() => setStatus("Can't reach saved labels yet…"), 10000);
  db.collection("labels").onSnapshot(snap => {
    if (!snap.metadata.fromCache) { clearTimeout(timeout); setStatus("Ready"); }
    snap.docs.forEach(d => { if (!labels[d.id] || document.activeElement?.id !== d.id + "-note") labels[d.id] = Object.assign({}, d.data()); });
    SAMPLES.forEach(s => renderCard(document.getElementById("card-" + s.id), s));
    renderCount();
  }, err => { clearTimeout(timeout); setStatus("Saved labels unavailable (" + err.code + ")."); });
})();
</script>
"""

Path(sys.argv[1]).write_text(PAGE.replace("__DATA__", data))
print("wrote", sys.argv[1])
