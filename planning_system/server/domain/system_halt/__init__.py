"""system_halt: the admin's stop switch for the whole system or one project (build log #68). Public: HaltSwitch,
HaltSwitchService, HaltStoragePort, Halt, HaltState. `fakes` stays a separate test-support submodule."""
from .halt_switch import HaltSwitchService
from .interface import HaltSwitch
from .ports import Clock, HaltStoragePort
from .types import Halt, HaltState

__all__ = ["Clock", "Halt", "HaltState", "HaltStoragePort", "HaltSwitch", "HaltSwitchService"]
