"""Generate the buggy mini-projects into projects/<name>/. Each gets run.sh (the failing command)."""
import os, stat, textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "projects"

RUN = """#!/usr/bin/env bash
cd "$(dirname "$0")"
{env}python3 -m unittest -v 2>&1
"""

P = {
# 1. Local module shadows stdlib `secrets`. First guess: token_hex missing / python version -> reimplement.
"shadow_secrets": {
    "secrets.py": '''\
        """Project secret settings (loaded by config.py)."""
        API_KEY = "sk-test-123"
        SIGNING_SALT = "pepper"
        ''',
    "config.py": '''\
        import secrets as project_secrets

        API_KEY = project_secrets.API_KEY
        SIGNING_SALT = project_secrets.SIGNING_SALT
        ''',
    "session.py": '''\
        from secrets import token_hex

        from config import SIGNING_SALT


        def new_session_id():
            """32 hex chars from the stdlib CSPRNG."""
            return token_hex(16)


        def tag(session_id):
            return f"{SIGNING_SALT}:{session_id}"
        ''',
    "test_session.py": '''\
        import unittest

        import config
        import session


        class SessionTest(unittest.TestCase):
            def test_session_id_is_32_hex(self):
                sid = session.new_session_id()
                self.assertEqual(len(sid), 32)
                int(sid, 16)

            def test_ids_differ(self):
                self.assertNotEqual(session.new_session_id(), session.new_session_id())

            def test_api_key(self):
                self.assertEqual(config.API_KEY, "sk-test-123")


        if __name__ == "__main__":
            unittest.main()
        ''',
},
# 2. Shallow merge of local config over base. First guess: config.json missing key -> add key / .get default.
"config_merge": {
    "config.json": '{\n  "database": {"url": "postgres://base/app", "pool": 5},\n  "debug": false\n}\n',
    "config.local.json": '{\n  "database": {"pool": 20},\n  "debug": true\n}\n',
    "settings.py": '''\
        import json
        from pathlib import Path

        HERE = Path(__file__).parent


        def load(config_dir=HERE):
            """Base config.json, with config.local.json (if present) layered over it."""
            config_dir = Path(config_dir)
            cfg = json.loads((config_dir / "config.json").read_text())
            local = config_dir / "config.local.json"
            if local.exists():
                cfg.update(json.loads(local.read_text()))
            return cfg
        ''',
    "db.py": '''\
        def connection_string(cfg):
            db = cfg["database"]
            return f"{db['url']}?pool={db['pool']}"
        ''',
    "test_db.py": '''\
        import unittest

        import db
        import settings


        class DbTest(unittest.TestCase):
            def test_connection_string(self):
                cfg = settings.load()
                self.assertEqual(db.connection_string(cfg), "postgres://base/app?pool=20")

            def test_debug_from_local(self):
                self.assertTrue(settings.load()["debug"])


        if __name__ == "__main__":
            unittest.main()
        ''',
},
# 3. Class-level mutable shared between instances; shows up only via test order. First guess: test/add logic wrong.
"shared_state": {
    "cart.py": '''\
        class Cart:
            items = []
            discount = 0

            def add(self, sku, qty=1):
                for _ in range(qty):
                    self.items.append(sku)

            def count(self):
                return len(self.items)
        ''',
    "test_cart.py": '''\
        import unittest

        from cart import Cart


        class CartTest(unittest.TestCase):
            def test_a_add_two(self):
                c = Cart()
                c.add("apple", qty=2)
                self.assertEqual(c.count(), 2)

            def test_b_new_cart_is_empty(self):
                c = Cart()
                self.assertEqual(c.count(), 0)

            def test_c_add_one(self):
                c = Cart()
                c.add("pear")
                self.assertEqual(c.items, ["pear"])


        if __name__ == "__main__":
            unittest.main()
        ''',
},
# 4. Local-time conversion; run.sh runs on a server set to Auckland. First guess: expected date in test wrong.
"timezone_day": {
    "report.py": '''\
        from datetime import datetime


        def day_label(ts):
            """UTC calendar day (YYYY-MM-DD) of a unix timestamp."""
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


        def daily_counts(timestamps):
            out = {}
            for ts in timestamps:
                d = day_label(ts)
                out[d] = out.get(d, 0) + 1
            return out
        ''',
    "test_report.py": '''\
        import unittest

        import report


        class ReportTest(unittest.TestCase):
            def test_day_label(self):
                # 1700000000 = 2023-11-14 22:13:20 UTC
                self.assertEqual(report.day_label(1700000000), "2023-11-14")

            def test_daily_counts(self):
                counts = report.daily_counts([1700000000, 1700003000, 1700100000])
                self.assertEqual(counts, {"2023-11-14": 2, "2023-11-16": 1})


        if __name__ == "__main__":
            unittest.main()
        ''',
    "_env": "TZ=Pacific/Auckland ",
},
# 5. Vendored lib bumped to 2.0, header default changed. First guess: off-by-one / data missing a row.
"vendored_api": {
    "vendor/__init__.py": "",
    "vendor/tinycsv/__init__.py": '''\
        """tinycsv 2.0.0"""
        __version__ = "2.0.0"


        def read_rows(text, sep=",", header=True):
            """Parse CSV text into lists of strings. If header is True the first line is a header and is skipped."""
            lines = [ln for ln in text.splitlines() if ln.strip()]
            if header:
                lines = lines[1:]
            return [ln.split(sep) for ln in lines]
        ''',
    "vendor/tinycsv/CHANGELOG.md": '''\
        # tinycsv changelog

        ## 2.0.0
        - BREAKING: `read_rows(header=...)` now defaults to `True` (was `False`). Pass `header=False` for files without a header line.
        - `sep` argument added.

        ## 1.4.0
        - Blank lines are skipped.
        ''',
    "data/readings.csv": "sensor-a,12\nsensor-b,7\nsensor-c,30\nsensor-d,1\n",
    "importer.py": '''\
        from pathlib import Path

        from vendor import tinycsv

        DATA = Path(__file__).parent / "data" / "readings.csv"


        def load_readings(path=DATA):
            rows = tinycsv.read_rows(Path(path).read_text())
            return [(name, int(value)) for name, value in rows]


        def total(readings):
            return sum(v for _, v in readings)
        ''',
    "test_importer.py": '''\
        import unittest

        import importer


        class ImporterTest(unittest.TestCase):
            def test_count(self):
                self.assertEqual(len(importer.load_readings()), 4)

            def test_total(self):
                self.assertEqual(importer.total(importer.load_readings()), 50)


        if __name__ == "__main__":
            unittest.main()
        ''',
},
}

for name, files in P.items():
    d = ROOT / name
    env = files.get("_env", "")
    for rel, body in files.items():
        if rel.startswith("_"):
            continue
        f = d / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(textwrap.dedent(body))
    r = d / "run.sh"
    r.write_text(RUN.format(env=env))
    r.chmod(r.stat().st_mode | stat.S_IEXEC)
print("ok")
