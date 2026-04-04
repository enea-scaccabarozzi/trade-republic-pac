from __future__ import annotations

import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel
from pytest_bdd import given, parsers, scenarios, then, when

from pac.delivery.discovery import discover_channels

scenarios("../features/channel_discovery.feature")


@pytest.fixture
def context() -> dict[str, Any]:
    return {}


@when("the builtin channels package is scanned")
def scan_builtin(context: dict[str, Any]) -> None:
    context["channels"] = discover_channels()


@then(parsers.parse('the discovered channels include "{name}"'))
def channels_include(context: dict[str, Any], name: str) -> None:
    assert name in context["channels"]


@then("each discovered channel has a config_model attribute")
def each_has_config_model(context: dict[str, Any]) -> None:
    for name, cls in context["channels"].items():
        assert hasattr(cls, "config_model"), f"{name} missing config_model"


@then("each config_model is a Pydantic BaseModel subclass")
def each_config_is_basemodel(context: dict[str, Any]) -> None:
    for name, cls in context["channels"].items():
        assert issubclass(cls.config_model, BaseModel), f"{name} config_model invalid"


@given(
    "a channels package containing a subdirectory with no channel.py",
    target_fixture="context",
)
def no_channel_py_package(tmp_path: Path) -> dict[str, Any]:
    pkg_dir = tmp_path / "nochfile_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")
    sub = pkg_dir / "somechannel"
    sub.mkdir()
    (sub / "__init__.py").write_text("")
    (sub / "helpers.py").write_text("X = 42\n")
    sys.path.insert(0, str(tmp_path))
    return {"package": "nochfile_pkg", "tmp_path": tmp_path}


@when("that channels package is scanned")
def scan_custom_package(context: dict[str, Any]) -> None:
    try:
        context["channels"] = discover_channels(context["package"])
    finally:
        sys.path.remove(str(context["tmp_path"]))
        for key in list(sys.modules):
            if key.startswith(context["package"]):
                del sys.modules[key]


@then("no channels are discovered from that subdirectory")
def no_channels_found(context: dict[str, Any]) -> None:
    assert len(context["channels"]) == 0


@given(
    "a channels package with an abstract DeliveryChannel subclass",
    target_fixture="context",
)
def abstract_channel_package(tmp_path: Path) -> dict[str, Any]:
    pkg_dir = tmp_path / "absch_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")
    sub = pkg_dir / "abstract_ch"
    sub.mkdir()
    (sub / "__init__.py").write_text("")
    (sub / "channel.py").write_text(
        textwrap.dedent(
            """\
        from abc import abstractmethod
        from pydantic import BaseModel
        from pac.delivery.base import DeliveryChannel, RenderedMessage

        class AbstractConfig(BaseModel):
            pass

        class AbstractChannel(DeliveryChannel[AbstractConfig]):
            name = "abstract_ch"

            @property
            def supported_formats(self) -> list[str]:
                return []

            @abstractmethod
            def extra(self) -> None: ...
        """
        )
    )
    sys.path.insert(0, str(tmp_path))
    return {"package": "absch_pkg", "tmp_path": tmp_path}


@then("the abstract class is not included in discovered channels")
def abstract_not_included(context: dict[str, Any]) -> None:
    assert "abstract_ch" not in context["channels"]
