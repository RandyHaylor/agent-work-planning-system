# Spec: prompt_builder

DRAFT (agent-approved under the user's build handover; see BUILD-DECISIONS-LOG.md)

Our copy of ai-rule-builder (`~/ai_skills_agents_resources/ai-rule-builder`, commit 1c9a830): the Python package, data, tests and website, kept mostly intact. It holds each role's rules and pre-prompt guidance, serves them per role over HTTPS, and stores edited presets with the server's files. The planner launches its website so the user can view and edit presets.

## Recorded decisions this builds on

- Copy the whole tool, website included. User: "can't the website allow updating the presets in a cool way? I'd say pull it in because it was really useful, not built wrong. The agent planner can load the web interface for the user so the user can see and edit the presets, right?" (`05-module-specs.md`, Gap 1 item 5, CORRECTED). Adapted only as needed: role -> preset mapping, guidance served per role.
- Where presets are saved. User: "if it's pulled in then the prompts save along with the server's files somewhere maybe. doesn't really matter" (same item; the tool's `AI_PROMPT_BUILDER_HOME` is pointed at a folder the server reads).
- Contents: "per-role guides + per-level process guidance (levels 1-7, question rounds, module commandments) + session-start rule injections" (Gap 1 item 1, user chose 1a).
- Served per role; only the planner learns the system. User: "Spawned agents don't know about the system; the planner does. Only the planner needs system guidance. Workers don't learn the system (their task carries their context), but they should get a good bit of guidance on how to do work: my rules, how to do work right. Served per role." (Gap 1 item 2)
- Role templates with groupings of rules. User: "Use its generic templates for roles, with groupings of rules assigned to each role." (Gap 1 item 3)
- Copied in as our own tool. User: "just pull a copy down and modify it directly. No updates from upstream are expected ... Keep them as independent modules: no hard coding, no rigid coupling." (Reader direction change, said of fastReader; Gap 1 item 3 says the prompt builder is "Brought in the same way as fastReader").
- Dev managers. User: "if the task is very large, the planner can spawn a dev manager (also a planner) so it can remain higher level and not run out of context." (Build handover and process)
- The software-design rules "MUST inform the system itself and prompting we add" (`process-levels.md`, level 5).
- Routes: `GET /guidance/{role}` -> {role, template, text}; `GET /guidance/templates`, `GET /guidance/rules`; `planning guidance-editor` launches the website (`BUILD-PLAN.md`). Each HTTP module exposes `router: APIRouter` in `<module>/http_routes.py` (BUILD-DECISIONS-LOG #4).

## What is copied as-is

| From ai-rule-builder | To `planning_system/prompt_builder/` | Change |
|---|---|---|
| `ai_prompt_builder/rule_catalog.py`, `ruleset.py` | `ai_prompt_builder/` | none |
| `ai_prompt_builder/command_line.py`, `__main__.py`, `local_web_server.py` | `ai_prompt_builder/` | none (the editor reuses `start_server`) |
| `index.html`, `css/`, `js/`, `docs/` | same paths | none |
| `data/rule-categories.json` | same | append `planning/guidance-content/rule-categories-additions.json` |
| `data/presets/*.json`, `index.json` | same | add `planner.json`, `dev-manager.json` from `planning/guidance-content/presets/`; list them in `index.json` |
| `tests/` | `tests/planning_system/prompt_builder/` | paths only |
| `SKILL.md`, `README.md` | same | point at this module's commands |

The new presets are shipped (in `data/`), not user presets, so the user's edits on the website are saved as their own presets and never overwrite ours (the tool refuses a user preset named like a shipped one).

## What is added (nested modules)

```
prompt_builder/
  ai_prompt_builder/        the copied package (catalog, ruleset composition, CLI, local web server)
  data/                     copied catalog + presets, plus our additions; role-presets.json; session-injections.json
  index.html css/ js/ docs/ the copied website
  role_guidance/            NEW: role -> preset -> composed guidance text
    role_preset_map         reads data/role-presets.json; role name -> preset name
    session_injections      reads data/session-injections.json; blocks that apply to a role
    guidance_composer       injections for the role, then the preset's composed rules
  guidance_editor/          NEW: starts the copied local web server on the server's preset folder; returns its URL
  http_routes.py            NEW: FastAPI router mounted at /guidance
```

- `data/role-presets.json`: from `planning/guidance-content/role-presets.json`.
- `data/session-injections.json`: the repo's `agent_instruction_injections.json`, copied in its own format (`applies_to` per block).

## Types

```python
GuidanceRole = str          # a key in role-presets.json: "planner", "dev_manager", "worker", "admin"

@dataclass(frozen=True)
class RoleGuidance:
    role: GuidanceRole
    template: str           # the preset name, e.g. "Planner"
    text: str               # injections for the role, then the preset's rules, ready to hand to an agent

@dataclass(frozen=True)
class EditorSession:
    url: str                # http://127.0.0.1:<port>/
    store_folder: Path      # the folder presets are saved to
```

## Public interface

```python
class RolePresetMap:
    def preset_name_for(self, role: GuidanceRole) -> str        # raises NotFound for an unknown role
    def roles(self) -> dict[GuidanceRole, str]

class SessionInjections:
    def blocks_for(self, role: GuidanceRole) -> list[str]        # texts whose applies_to lists the role

class GuidanceComposer:
    def __init__(self, catalog: RuleCatalog, role_map: RolePresetMap, injections: SessionInjections)
    def guidance_for(self, role: GuidanceRole) -> RoleGuidance
        # catalog.find_preset -> ruleset.new_ruleset -> ruleset.compose_prompt_text; injections first

class GuidanceEditor:
    def __init__(self, store_folder: Path)
    def launch(self) -> EditorSession      # local_web_server.start_server(RuleBuilderSession(RuleCatalog(store_folder), None, None))
```

`RuleCatalog(user_folder=<configured folder>)` is always built with the configured folder, so `AI_PROMPT_BUILDER_HOME` is not needed inside the server; the editor sets it for the copied CLI.

### Configuration (section `prompt_builder`, handed in by `configuration/`)

- `preset_folder`: the folder the server reads and the website saves to, under the server's data folder (e.g. `<server data>/prompt_builder/`). Holds `customizations.json` and `presets/`.

### HTTP routes (`http_routes.py`, mounted at `/guidance`)

| Route | Who | Returns |
|---|---|---|
| `GET /guidance/{role}` | any authenticated principal | `RoleGuidance` |
| `GET /guidance/templates` | any authenticated principal | the role -> preset map and every preset (shipped and user) |
| `GET /guidance/rules` | any authenticated principal | every category with its options |

Reads only; the catalog is re-read per request so edits on the website show up at once.

### Launching the website

`planning guidance-editor` (cli) runs `GuidanceEditor.launch()` on the machine where the server's files are (localhost for this build) and prints the URL; the planner gives it to the user. The site is the copied one, bound to 127.0.0.1, unchanged; its "Send to local AI agent" button stays off (no send file).

## External integration tests (mock up front)

1. `GET /guidance/worker` returns template "Careful developer" and the text of its enabled rules under their headings, preceded by every injection whose `applies_to` lists `worker`.
2. `GET /guidance/planner` includes the process rules (levels, level 5, commandments, asking, approval, running tasks, references) and the Careful dev manager rules.
3. `GET /guidance/dev_manager` is the planner's rules plus the dev manager text at the start.
4. An unknown role returns 404.
5. A user preset saved in `preset_folder` (as the website saves it) and mapped to a role is served on the next request without a restart.
6. The website's `PUT /api/customizations` writes into `preset_folder`, never into the module's `data/`.
7. `GuidanceEditor.launch()` returns a 127.0.0.1 URL that serves `index.html` and `/api/session-settings` with `storeFolder` = `preset_folder`.
8. The copied tool's own tests pass unchanged (paths aside).
9. Every preset named in `role-presets.json` exists, and every entry in it resolves (`rulesNotFound` is empty).

Mocks: none needed beyond a temp `preset_folder` and FastAPI's test client with a stub `current_principal`.

## Open items (not decided; listed, not resolved)

- `agent_instruction_injections.json` was written for the old server: it names workorders, `kb_proposal`, "the reference run", and repeats rules now also in rule categories (do-not-add-or-change-details, batch questions, parallel work). It is copied as-is; its wording needs the user's review.
- Whether a planner may read `/guidance/dev_manager` to hand it on is assumed yes (any authenticated principal may read any role's guidance; it is not secret).
