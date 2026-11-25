---
name: ai-prompt-builder
description: Build a prompt for an AI agent with the user — the rules it works by (naming, testing, scope, escalation, research, documentation, response format, and more) plus what is actually to be done — step by step or in a web page, and produce the text to paste. Its rule catalog and presets double as a checklist of the requirements to gather from a user before any piece of work, so none (testing, documentation, research, scope, paid runs...) is left out. Use when the user wants to write a prompt or ruleset for an agent, set up how an agent should work, write instructions for a deployed agent, prepare a handoff document, gather the requirements for a task, or mentions "prompt builder", "ruleset", "agent rules" or "prompt rules".
---

# AI Prompt Builder

A ruleset is a list of rules, each with an on/off switch and one chosen option, plus
optional **custom text** that says what is actually to be done. Presets are ready-made
rulesets. Everything is a JSON file; the tool composes the text to paste.

## The rules are your checklist

The rule catalog is a list of the requirements a piece of work needs settled — testing,
documentation, research, scope, naming, escalation, paid runs, response format and more —
each with the realistic choices. **Use it as your guide for what to ask the user**, so no
requirement is silently left to your own assumption:

- Before gathering requirements for any task, read the catalog (`categories`, and
  `category <id>` for the full text of the options) and make sure each rule that matters
  for this work has an answer from the user.
- The presets show which rules belong together for a kind of work (`presets --json`):
  *Careful developer* for building, *Bug fix*, *Research*, *Document writer* and so on. Use the
  matching preset as a starting point for what to cover.
- An answer the user did not give is not yours to fill in: ask, or mark it plainly as an
  open question.

## Running the tool

Python 3.9 or newer, standard library only, any operating system. From this skill's folder:

```
python -m ai_prompt_builder <command> ...        (use python3 where python is Python 2)
```

From any other folder, run it with this skill's folder as the working directory, or set
`PYTHONPATH` to it. `python -m ai_prompt_builder --help` and `<command> --help` list every
option.

| Command | What it does |
|---|---|
| `presets` | list presets (`--json` for machine-readable) |
| `categories` | list every rule and its options |
| `category <id>` | show one rule's options in full |
| `new <file> [--preset NAME] [--blank]` | start a ruleset file |
| `show <file> [--full]` | the ruleset: order, on/off, chosen option |
| `set <file> <rule> [--option ID] [--on/--off] [--text T / --text-file F] [--reset-text]` | change one rule |
| `all <file> on / off / reset-text` | change every rule |
| `move <file> <rule> <position>` | reorder (1 = first) |
| `remove <file> <rule>` | take a rule out of this ruleset (it becomes "not added yet"; `set` adds it back) |
| `delete-rule <rule>` | delete a rule from the catalog for good — only when the user asks for exactly that |
| `custom-text <file> [--text T / --text-file F] [--at end/start] [--on/--off]` | the optional custom text |
| `compose <file> [--out F]` | the text to paste |
| `add-option <rule> --name N --text T` | the user's own option, kept for later |
| `add-category "Name"` | the user's own rule |
| `save-preset <file> "Name"` | keep a ruleset as the user's preset |
| `serve [...]` | open the web page (see below) |
| `wait-for-send <send file>` | wait for the page's Send to local AI agent button |
| `where` | the folder the user's own options and presets are saved in |

Use `--text-file` for anything multi-line or containing quotes. The user's own options and
presets are saved under `~/.ai-prompt-builder` (or `.ai-prompt-builder` in the current project
if that folder exists, or `$AI_PROMPT_BUILDER_HOME`).

## Working with the user

1. **Ask how they want to start:** from a preset (show `presets`), or by going through the
   rules one at a time. Offer the web page as a third way (below).
2. **Start the file:** `new ruleset.json --preset "<name>"`, or `--blank` to go rule by rule.
3. **Going through the rules:** for each rule in `categories`, show its options (short names;
   the full text on request with `category <id>`), ask which one, or off, then `set`. Ask
   one rule at a time. Offer to edit an option's text, or to save an edited text as a new
   option with `add-option`.
4. **Custom text:** ask whether this is a general ruleset or a specific request. For a
   specific request, the custom text is where the actual task goes; ask whether it goes at
   the end (default) or the beginning.
5. **Show the result** with `compose`, change anything they want, then **offer to save it as
   a preset** with `save-preset`.
6. Never add rules, options or text the user did not choose. Their own words go in as they
   gave them.

## Putting the finished prompt to use

Offer the user these ways to apply it, and let them choose:

- **This task, now:** follow it yourself for the work at hand.
- **A spawned agent:** pass the composed text as that agent's instructions.
- **Standing rules in this harness:** most harnesses have places for instructions that are
  loaded automatically — for this project or session, or for every session (globally).
  Do not assume where or how: **research it for the harness you are running in**, from its
  current official documentation (for example, the project and user instruction files and
  settings it reads at start-up, and how they combine). Then tell the user what you found —
  the options, where each file lives, and what each one affects — and offer to add the rules
  there, at the level they pick. Show the exact change before writing it, add to existing
  instructions rather than replacing them, and mention how to undo it.

Things a ruleset is good for, to suggest when it fits: the standing instructions of a
deployed agent, the rules section of a handoff document, a team's shared way of working,
or a one-off prompt for a specific task.

## Letting the user edit in the web page

```
python -m ai_prompt_builder serve --ruleset-file ruleset.json --send-to-agent-file /tmp/ruleset-sent.json
```

- Run it in the background. Its **first line of output is JSON** with the `url`; give that
  URL to the user. It binds to this computer only, on a free port the system chooses, so
  several can run at once — one per session.
- `--ruleset-file` opens that ruleset in the page. Without it, the default preset opens.
- `--send-to-agent-file` turns on the page's **Send to local AI agent** button. Pick a path in
  your session's temporary folder. Clicking the button writes the ruleset and its composed
  text to that file, and also saves the ruleset back to `--ruleset-file`.
- To be told when the user clicks it, run (in the background, so you are notified when it
  exits):

  ```
  python -m ai_prompt_builder wait-for-send /tmp/ruleset-sent.json
  ```

  It exits as soon as the button is clicked and prints JSON with `composedText` and the
  ruleset's name. If your harness cannot run a background command, read the send file
  when the user says they are done.
- Stop the server when finished (end the background process).

Options and presets the user adds in the page are saved in the same folder the commands
use, so the two always agree.

## File format

```json
{
  "format": "ai-prompt-builder/ruleset@1",
  "name": "My ruleset",
  "entries": [
    {"categoryId": "testing", "optionId": "tdd-module-level", "enabled": true, "editedText": null}
  ],
  "customText": {"text": "Build ...", "placement": "end", "enabled": true}
}
```

`editedText`, when not null, replaces the option's text. Prefer the commands over editing
the file by hand.
