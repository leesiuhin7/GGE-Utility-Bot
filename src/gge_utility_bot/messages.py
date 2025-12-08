from dataclasses import dataclass


@dataclass(frozen=True)
class ConfigGet:
    bad_channel: str
    bad_path: str
    success: str


@dataclass(frozen=True)
class ConfigRemove:
    bad_channel: str
    failed: str
    success: str


@dataclass(frozen=True)
class ConfigSet:
    bad_channel: str
    bad_input: str
    failed: str
    success: str


@dataclass(frozen=True)
class Config:
    get: ConfigGet
    remove: ConfigRemove
    set: ConfigSet


@dataclass(frozen=True)
class PuppetStatus:
    success: str


@dataclass(frozen=True)
class Puppet:
    status: PuppetStatus


@dataclass(frozen=True)
class BattleReport:
    summary: str


@dataclass(frozen=True)
class Messages:
    battle_report: BattleReport
    config: Config
    puppet: Puppet


MESSAGES = Messages(
    battle_report=BattleReport(
        summary="Battle report summary.",
    ),
    config=Config(
        get=ConfigGet(
            bad_channel="Please use a channel that has been registered for configuration usage.",
            bad_path="Input path is invalid.",
            success="Accessing configuration succeeded.",
        ),
        remove=ConfigRemove(
            bad_channel="Please use a channel that has been registered for configuration usage.",
            failed="Removing configuration failed.",
            success="Removing configuration succeeded.",
        ),
        set=ConfigSet(
            bad_channel="Please use a channel that has been registered for configuration usage.",
            bad_input="Input value cannot be used to modify configuration.",
            failed="Modifying configuration failed.",
            success="Modifying configuration succeeded.",
        ),
    ),
    puppet=Puppet(
        status=PuppetStatus(
            success="Puppet status loaded successfully.",
        ),
    ),
)
