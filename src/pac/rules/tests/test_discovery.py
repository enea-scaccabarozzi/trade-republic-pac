from __future__ import annotations

import sys
import textwrap
from pathlib import Path

from pydantic import BaseModel

from pac.rules.base import SignalRule
from pac.rules.discovery import discover_rules


class TestDiscoverRules:
    def test_discovers_all_builtin_rules(self) -> None:
        rules = discover_rules()
        assert len(rules) == 9
        assert "threshold_deviation" in rules
        assert "cycle_inversion" in rules
        assert "pac_plan" in rules
        assert "equity_drawdown" in rules
        assert "gold_equity_divergence" in rules
        assert "volatility_regime" in rules
        assert "relative_strength" in rules
        assert "death_cross" in rules
        assert "crisis_composite" in rules

    def test_each_rule_has_params_model(self) -> None:
        rules = discover_rules()
        for name, rule_cls in rules.items():
            assert hasattr(rule_cls, "params_model"), f"{name} missing params_model"
            assert issubclass(rule_cls.params_model, BaseModel)

    def test_discovered_rules_are_signal_rule_subclasses(self) -> None:
        rules = discover_rules()
        for name, rule_cls in rules.items():
            assert issubclass(rule_cls, SignalRule), f"{name} not a SignalRule subclass"

    def test_custom_package_with_rule(self, tmp_path: Path) -> None:
        pkg_dir = tmp_path / "fake_rules"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")
        (pkg_dir / "good_rule.py").write_text(
            textwrap.dedent(
                """\
            from pydantic import BaseModel
            from pac.rules.base import SignalRule
            from pac.models.signals import Signal
            from pac.analysis.deviation import DeviationReport
            from pac.models.portfolio import PortfolioSnapshot

            class GoodParams(BaseModel):
                threshold: float = 1.0

            class GoodRule(SignalRule[GoodParams]):
                @property
                def name(self) -> str:
                    return "good_rule"

                def evaluate(
                    self,
                    report: DeviationReport,
                    snapshot: PortfolioSnapshot,
                    params: GoodParams,
                ) -> list[Signal]:
                    return []
            """
            )
        )
        sys.path.insert(0, str(tmp_path))
        try:
            rules = discover_rules("fake_rules")
            assert "good_rule" in rules
        finally:
            sys.path.remove(str(tmp_path))
            for key in list(sys.modules):
                if key.startswith("fake_rules"):
                    del sys.modules[key]

    def test_ignores_underscore_prefixed_files(self, tmp_path: Path) -> None:
        pkg_dir = tmp_path / "underscore_pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")
        (pkg_dir / "_private.py").write_text(
            textwrap.dedent(
                """\
            from pydantic import BaseModel
            from pac.rules.base import SignalRule
            from pac.models.signals import Signal
            from pac.analysis.deviation import DeviationReport
            from pac.models.portfolio import PortfolioSnapshot

            class PrivateParams(BaseModel):
                pass

            class PrivateRule(SignalRule[PrivateParams]):
                @property
                def name(self) -> str:
                    return "private_rule"

                def evaluate(
                    self,
                    report: DeviationReport,
                    snapshot: PortfolioSnapshot,
                    params: PrivateParams,
                ) -> list[Signal]:
                    return []
            """
            )
        )
        sys.path.insert(0, str(tmp_path))
        try:
            rules = discover_rules("underscore_pkg")
            assert "private_rule" not in rules
        finally:
            sys.path.remove(str(tmp_path))
            for key in list(sys.modules):
                if key.startswith("underscore_pkg"):
                    del sys.modules[key]

    def test_ignores_non_rule_modules(self, tmp_path: Path) -> None:
        pkg_dir = tmp_path / "norule_pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")
        (pkg_dir / "helper.py").write_text("X = 42\n")
        sys.path.insert(0, str(tmp_path))
        try:
            rules = discover_rules("norule_pkg")
            assert len(rules) == 0
        finally:
            sys.path.remove(str(tmp_path))
            for key in list(sys.modules):
                if key.startswith("norule_pkg"):
                    del sys.modules[key]

    def test_ignores_abstract_classes(self, tmp_path: Path) -> None:
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
        try:
            rules = discover_rules("abstract_pkg")
            assert "abstract_middle" not in rules
        finally:
            sys.path.remove(str(tmp_path))
            for key in list(sys.modules):
                if key.startswith("abstract_pkg"):
                    del sys.modules[key]
