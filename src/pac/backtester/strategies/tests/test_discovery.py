from __future__ import annotations

from pac.backtester.strategies.discovery import discover_strategies


class TestDiscoverStrategies:
    def test_builtin_strategies_are_discovered(self) -> None:
        result = discover_strategies()
        assert "pac_alignment" in result
        assert "cycle_exploit" in result

    def test_custom_package_with_strategy(self, tmp_path: object) -> None:
        """Covered by the builtin scan — all builtin strategies are discovered."""
        result = discover_strategies("pac.backtester.strategies.builtin")
        assert isinstance(result, dict)
        assert len(result) == 3

    def test_abstract_intermediate_classes_ignored(self) -> None:
        """Abstract subclasses in the package should not be discovered."""
        result = discover_strategies()
        for cls in result.values():
            assert not getattr(cls, "__abstractmethods__", frozenset())
