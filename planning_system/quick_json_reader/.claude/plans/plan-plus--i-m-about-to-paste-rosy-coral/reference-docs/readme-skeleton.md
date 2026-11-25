# README.md structural skeleton (Phase E)

Path: `/home/aikenyon/.claude/skills/fastReader/README.md`. GitHub-flavored Markdown. Pure GFM (no HTML-only features). Every code block language-tagged.

Sections in order:

1. Title + one-sentence pitch.
2. Badges placeholder (HTML comment block only; no real badges).
3. Why — token-cost problem in 2–3 sentences + the Phase B measurement table.
4. Install / use (pre-repo **copy the folder** phrasing — NO `git clone`).
5. Five-minute tour: load → toc → drill → search. Each step = real copy-pasteable command + truncated real output.
6. Four scanners, one pass — table with `--sections | --indent-depth | --bracket-depth | --tag-depth` and a "good for" column.
7. Self-documenting CLI — call out `--help-examples` and `--help-use-cases`; one short example per subcommand.
8. Integrity warnings — condensed INTEGRITY block from SKILL.md.
9. Token-savings benchmark — full Phase B table + script path `/tmp/fastReader_token_measurements_script.sh`.
10. What fastReader is NOT — mirror SKILL.md.
11. Contributing / status — "Pre-repo. No issue tracker yet."
12. License placeholder — `TBD`.

Constraints recap:
- No `git clone` anywhere.
- No invented benchmark numbers — all values come from running `/tmp/fastReader_token_measurements_script.sh`.
- Every fenced `bash` block must actually execute on a real path; Phase F verifies this.
