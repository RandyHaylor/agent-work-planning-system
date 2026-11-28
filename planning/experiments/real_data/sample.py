"""Real-data sample (user 2026-11-28: "planning/ docs"): agent-written sentences from this repo's planning docs,
each with the user's verbatim quotes from the same bullet as its references.
Usage (repo root): uv run python -I planning/experiments/real_data/sample.py [count]
Writes samples.json: [{id, doc, sentence, bullet, quotes[]}]."""
from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))

from planning_system.local_client.review_mode.sentence_splitter import SentenceSplitter  # noqa: E402

DOCS = ["planning/process-levels.md", "planning/05-module-specs.md", "planning/01-what-were-doing.md",
        "planning/02-definition-of-done.md", "planning/03-high-level-plan.md", "planning/04-design.md"]
QUOTE = re.compile(r'(?:User|user)[^:"]{0,40}:\s*"((?:[^"\\]|\\.)+)"')
LONG_QUOTE = re.compile(r'"((?:[^"\\]|\\.)+)"')       # in these docs, long quoted spans are the user's words


def user_quotes(bullet: str) -> list[str]:
    return [q for q in LONG_QUOTE.findall(bullet) if len(q.split()) >= 6]
MARKUP = re.compile(r"\*\*|`|\[([^\]]+)\]\([^)]+\)")


def bullets(text: str):
    """Top-level list items and paragraphs, continuation lines joined."""
    block: list[str] = []
    for line in text.splitlines() + [""]:
        starts_item = re.match(r"^\s{0,3}(?:[-*]|\d+\.)\s", line)
        if (starts_item or not line.strip() or line.startswith("#")) and block:
            yield " ".join(part.strip() for part in block)
            block = []
        if line.strip() and not line.startswith("#"):
            block.append(line)


def agent_text(bullet: str) -> str:
    """The bullet without the user quotes and their 'User: ...' lead-ins."""
    stripped = QUOTE.sub(" ", bullet)
    for quote in user_quotes(stripped):
        stripped = stripped.replace(f'"{quote}"', " ")
    stripped = re.sub(r"\b(?:User|Then|Also)[^:.]{0,40}:\s*(?=\s|$)", " ", stripped)
    stripped = re.sub(r"^\s*(?:[-*]|\d+\.)\s*", "", stripped)
    return MARKUP.sub(lambda m: m.group(1) or "", stripped).strip()


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    splitter, pool = SentenceSplitter(), []
    for doc in DOCS:
        path = REPO / doc
        if not path.exists():
            continue
        for bullet in bullets(path.read_text()):
            quotes = user_quotes(bullet)
            if not quotes or not QUOTE.search(bullet):
                continue
            for sentence in splitter.split(agent_text(bullet)):
                if len(sentence.split()) >= 6 and sentence[0].isalpha() and sentence[0].isupper() \
                        and '"' not in sentence and not sentence.lower().startswith("user"):
                    pool.append({"doc": doc, "sentence": sentence, "bullet": bullet, "quotes": quotes})
    random.Random(20261128).shuffle(pool)
    samples = [{"id": f"r{i + 1:02d}", **s} for i, s in enumerate(pool[:count])]
    (HERE / "samples.json").write_text(json.dumps(samples, indent=1))
    print(f"pool {len(pool)} sentences; wrote {len(samples)} samples")
    for s in samples[:5]:
        print(s["id"], s["doc"], "|", s["sentence"][:110], "| quotes:", len(s["quotes"]))


if __name__ == "__main__":
    main()
