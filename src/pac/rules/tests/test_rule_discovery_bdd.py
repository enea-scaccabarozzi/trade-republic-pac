from __future__ import annotations

import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel
from pytest_bdd import given, parsers, scenarios, then, when

from pac.rules.discovery import discover_rules

scenarios("../features/rule_discovery.feature")


@pytest.fixture
def context() -> dict[str, Any]:
    return {}


@when("the builtin rules package is scanned")
def scan_builtin(context: dict[str, Any]) -> None:
    context["rules"] = discover_rules()


@then(parsers.parse('the discovered rules include "{name}"'))
def rules_include(context: dict[str, Any], name: str) -> None:
    assert name in context["rules"]


@then("each discovered rule has a params_model attribute")
def each_has_params_model(context: dict[str, Any]) -> None:
    for name, cls in context["rules"].items():
        assert hasattr(cls, "params_model"), f"{name} missing params_model"


@then("each params_model is a Pydantic BaseModel subclass")
def each_params_is_basemodel(context: dict[str, Any]) -> None:
    for name, cls in context["rules"].items():
        assert issubclass(cls.params_model, BaseModel), f"{name} params_model invalid"


@given(
    "a package containing a module with no SignalRule subclass",
    target_fixture="context",
)
def no_rule_package(tmp_path: Path) -> dict[str, Any]:
    pkg_dir = tmp_path / "norule_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "helper.py").write_text("X = 42\n")
    sys.path.insert(0, str(tmp_path))
    return {"package": "norule_pkg", "tmp_path": tmp_path}


@when("that package is scanned")
def scan_custom_package(context: dict[str, Any]) -> None:
    try:
        context["rules"] = discover_rules(context["package"])
    finally:
        sys.path.remove(str(context["tmp_path"]))
        for key in list(sys.modules):
            if key.startswith(context["package"]):
                del sys.modules[key]


@then("no rules are discovered from that module")
def no_rules_found(context: dict[str, Any]) -> None:
    assert len(context["rules"]) == 0


@given(
    "a package with an abstract SignalRule subclass",
    target_fixture="context",
)
def abstract_rule_package(tmp_path: Path) -> dict[str, Any]:
    pkg_dir = tmp_path / "abstract_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "abstract_rule.py").write_text(
        textwrap.dedent(
            """\
        from abc import abstractmethod
        from pydantic import BaseModel
        from pac.rules.base import SignalRule
        from pac.models.signals import Signal
        from pac.analysis.deviation import DeviationReport
        from pac.models.portfolio import PortfolioSnapshot

        class SomeParams(BaseModel):
            pass

        class AbstractMiddle(SignalRule[SomeParams]):
            @property
            def name(self) -> str:
                return "abstract_middle"

            @abstractmethod
            def extra(self) -> None: ...
        """
        )
    )
    sys.path.insert(0, str(tmp_path))
    return {"package": "abstract_pkg", "tmp_path": tmp_path}


@then("the abstract class is not included in discovered rules")
def abstract_not_included(context: dict[str, Any]) -> None:
    assert "abstract_middle" not in context["rules"]
