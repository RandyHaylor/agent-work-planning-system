# User-approved decisions (do not drift from these)

1. **Benchmark suite must be multi-case.** JSONL alone is too homogeneous to be the headline.
   Required target categories (one file each, real on-disk paths recorded in the benchmark script):
   - Large HTML reference doc (hundreds of KB, nested `<section>/<h*>/<pre><code>`).
   - Large XML doc (API spec, sitemap, or config dump).
   - Original (non-stripped) Claude Code plan file from `~/.claude/plans/` — NOT one of the user's trimmed working plans.
   - Markdown technical doc with embedded code blocks (code-reference doc — the "massive speed-up" case the user called out).
   - 7 MB session JSONL at `~/.claude/projects/-home-aikenyon-my-projects-quick-json-viewer-project-quick-json-reader/8539d3f6-21f1-421c-bef6-a4a7970c8b2f.jsonl` — included as a single baseline row only.
   If a category has no suitable file on disk, ASK the user — do not silently generate or skip.

2. **README install phrasing = pre-repo "copy the folder".** No `git clone`, no `git init`, no repo creation.

3. **Use every relevant new display feature in benchmark commands**: `--show-line-range-count` (verified to exist), plus node-id / child-count display IF they exist. Phase A must read `cli.py` and `scanner.py` to confirm what is actually implemented; anything referenced but not implemented goes into Phase C as a candidate addition, NOT silently pretended-about.

4. **User is a senior engineer.** Do not assume he made mistakes. Do not alter his instructions.

5. **Every number in README / SKILL.md must be measured, not guessed.** Cite the file and date.

6. **No git actions in this project at all** (no init, no commit, no push, no branch).
