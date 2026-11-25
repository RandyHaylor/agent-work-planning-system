# Spec: configuration + main.py (composition)

DRAFT (agent-approved under the user's build handover; see BUILD-DECISIONS-LOG.md)

## Recorded decisions this builds on

- "main is completely abstracted and knows nothing about anything: not the UI stack, not the database type, nothing concrete. It calls generic interfaces and passes in their config without interpreting it, e.g. load user interface, passing a user-interface config.json. Concrete choices come only from injected config." (05-module-specs.md, Recheck 12)
- Tree v5: `configuration/` "reads injected config files; hands each module its own section"; approved by the user in Slack (05-module-specs.md, "Module tree v5").
- BUILD-PLAN.md layout: `main.py` "generic startup; reads config; mounts routers"; `configuration/` "loads config/*.json; hands each module its section".
- Definition of done: "`docker compose up` + `planning-server bootstrap` + `planning-server run`" (BUILD-PLAN.md).
- "Never mix levels of detail ... a top level main() function calls things. It should have similar SCOPE calls." (process-levels.md, commandment 9)

## Modules (nested)

```
planning_system/
  main.py                          entry point `planning-server <component-command>`; steps only, no concrete names
  configuration/                   public: Configuration, load_configuration
    config_file_reader             reads every config/*.json in the injected folder into one tree of sections
    environment_substitution       replaces "${NAME}" values with environment / .env values (secrets stay out of JSON)
    section                        ConfigSection: read-only view of one section; hands out child sections
    component_loader               imports the factory named in a section ("factory": "pkg.module:callable") and calls it with that section
```

## Types

```python
class ConfigSection:                       # immutable view; the module that owns it interprets it, nobody else
    name: str
    def get(self, key, default=MISSING) -> Any
    def child(self, name) -> "ConfigSection"
    def as_dict(self) -> dict

class Configuration:
    def section(self, name) -> ConfigSection        # raises Invalid naming the missing section and file folder

class Component(Protocol):                 # what every top-level factory returns
    def commands(self) -> dict[str, Callable[[list[str]], int]]   # e.g. {"run": ..., "bootstrap": ...}
```

## Public interface

```python
def load_configuration(folder: Path) -> Configuration       # folder from --config or PLANNING_CONFIG_DIR, default ./config
def load_component(section: ConfigSection) -> Component      # component_loader
```

## main.py (whole shape)

```python
def main(argv) -> int:
    configuration = load_configuration(config_folder(argv))
    components = load_components(configuration)          # one per name in the "components" list of the top section
    command = find_command(components, argv)
    return command(remaining_args(argv))
```

Example config (shape only; each section is owned by the module that reads it):

```
config/main.json       {"components": ["server"]}
config/server.json     {"server": {"factory": "planning_system.server.composition:create_server",
                                    "storage": {"dsn": "${PLANNING_DSN}", ...},
                                    "http_api": {"host": "127.0.0.1", "port": 8788, "cert_dir": "certs"},
                                    "references": {"temp_cache_ttl_hours": 72}, ...}}
```

`planning_system/server/composition.py` (server's own composition root, not main) builds engine, stores, domain facades, CommandRunner, FastAPI app and bootstrap from its section and exposes the commands `run` and `bootstrap`.

## External integration tests

1. Two JSON files in a temp folder load into one Configuration; `section("server").child("storage").get("dsn")` returns the value.
2. `${NAME}` is replaced from the environment, then from `.env`; an unset name fails with a clear error naming it.
3. A missing section raises `Invalid` naming the section.
4. `load_component` with a fake factory path calls that factory once with exactly its own section (other sections not visible).
5. `main(["run"])` with a config naming a fake component calls that component's `run` and returns its exit code; main contains no import of server, FastAPI, SQLAlchemy or Postgres (checked by a test reading main's imports).
6. An unknown command lists the commands the loaded components offer.
