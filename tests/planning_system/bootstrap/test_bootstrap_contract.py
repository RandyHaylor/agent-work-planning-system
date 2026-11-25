"""Contract tests for bootstrap (spec: planning/05-spec-bootstrap.md). Mocked storage, database setup,
authentication setup and prompt; [fake, real(xfail)] Bootstrapper. The password prompt is carried
code and runs now."""
import io

import pytest

from planning_system.contract import Invalid
from planning_system.server.bootstrap import Bootstrapper, TerminalPasswordPrompt
from planning_system.server.bootstrap.fakes import (FakeBootstrapper, InMemoryAuthenticationSetup,
                                                    RecordingDatabaseSetup, ScriptedPasswordPrompt)
from planning_system.server.storage.fakes import InMemoryStorage

LEVEL7 = pytest.mark.xfail(strict=False, reason="level 7")


@pytest.fixture(params=["fake", pytest.param("real", marks=LEVEL7)])
def make(request):
    cls = FakeBootstrapper if request.param == "fake" else Bootstrapper

    def build(fail_on_set=False):
        parts = dict(storage=InMemoryStorage(), database=RecordingDatabaseSetup(),
                     authentication=InMemoryAuthenticationSetup(fail_on_set), prompt=ScriptedPasswordPrompt())
        parts["bootstrapper"] = cls(parts["storage"], parts["database"], parts["authentication"], parts["prompt"])
        return parts
    return build


def test_1_first_run_ensures_db_migrates_asks_once_and_stores_in_one_transaction(make):
    w = make()
    result = w["bootstrapper"].bootstrap()
    assert not result.already_bootstrapped and result.messages
    assert w["database"].calls == ["ensure_database", "migrate"]
    assert w["prompt"].asked == 1
    assert w["authentication"].admin_password_set(w["storage"].stores)
    assert [r.mode for r in w["storage"].transactions.records if r.mode == "read_write"] == ["read_write"]


def test_2_second_run_asks_nothing_and_writes_nothing(make):
    w = make()
    w["bootstrapper"].bootstrap()
    writes = len([r for r in w["storage"].transactions.records if r.mode == "read_write"])
    result = w["bootstrapper"].bootstrap()
    assert result.already_bootstrapped and "already" in " ".join(result.messages)
    assert w["prompt"].asked == 1
    assert len([r for r in w["storage"].transactions.records if r.mode == "read_write"]) == writes


def test_3_failure_while_storing_rolls_back(make):
    w = make(fail_on_set=True)
    with pytest.raises(RuntimeError):
        w["bootstrapper"].bootstrap()
    assert not w["authentication"].admin_password_set(w["storage"].stores)
    assert w["storage"].transactions.records[-1].rolled_back


def test_5_set_admin_password_needs_a_prior_bootstrap_then_replaces(make):
    w = make()
    with pytest.raises(Invalid, match="bootstrap"):
        w["bootstrapper"].set_admin_password()
    w["bootstrapper"].bootstrap()
    w["prompt"].password = "a different one"
    w["bootstrapper"].set_admin_password()
    assert w["storage"].stores._admin_password == "hash:a different one"


# ---- password prompt (4), carried code

def test_4_env_override_skips_prompt_with_warning():
    err = io.StringIO()
    prompt = TerminalPasswordPrompt({"PLANNING_ADMIN_PASSWORD": "long enough pw"},
                                    read_secret=lambda _: pytest.fail("prompted"), out=io.StringIO(), err=err)
    assert prompt.ask() == "long enough pw"
    assert "warning" in err.getvalue()


def test_4b_env_password_failing_policy_is_rejected():
    prompt = TerminalPasswordPrompt({"PLANNING_ADMIN_PASSWORD": "short"}, err=io.StringIO())
    with pytest.raises(Invalid):
        prompt.ask()


def test_4c_interactive_asks_twice_rejects_short_and_mismatch_and_warns():
    answers = iter(["short", "long enough pw", "typo typo typo", "long enough pw", "long enough pw"])
    out = io.StringIO()
    prompt = TerminalPasswordPrompt({}, read_secret=lambda _: next(answers), out=out)
    assert prompt.ask() == "long enough pw"
    text = out.getvalue()
    assert "SAVE THIS PASSWORD" in text and "at least" in text and "do not match" in text


@LEVEL7
def test_6_real_postgres_bootstrap_then_admin_session():
    raise AssertionError("level 7: fresh planning_system db, bootstrap, POST /admin/sessions returns a token")
