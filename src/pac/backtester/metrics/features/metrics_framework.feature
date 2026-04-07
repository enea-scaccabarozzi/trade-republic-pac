Feature: Backtest Metrics Framework
  The metrics framework computes performance metrics from simulation results,
  aggregates across Monte Carlo iterations, and compares strategy performance
  against a passive buy-and-hold benchmark.

  Background:
    Given a portfolio with 3 assets: stocks (70%), gold (15%), bonds (15%)
    And initial cash of €10,000
    And a monthly contribution of €500
    And configured metrics: sharpe, max_drawdown, cagr

  Scenario: Metrics computed from simulation results
    Given a completed strategy simulation with 3 iterations
    When metrics are computed
    Then the report contains metrics for "sharpe", "max_drawdown", "cagr"
    And each metric has median, P5, and P95 values

  Scenario: Benchmark comparison included by default
    Given a completed strategy simulation
    And benchmark comparison is enabled
    When a backtest report is computed
    Then the report includes both strategy and benchmark metric sets
    And both sets contain the same metric names

  Scenario: Benchmark comparison can be disabled
    Given a completed strategy simulation
    And benchmark comparison is disabled
    When a backtest report is computed
    Then the report has no benchmark metrics

  Scenario: Max drawdown is always non-positive
    Given a completed simulation with varying market conditions
    When metrics are computed
    Then max_drawdown median is less than or equal to 0
    And max_drawdown P95 is less than or equal to 0

  Scenario: Single iteration produces equal confidence bounds
    Given a completed strategy simulation with 1 iterations
    When metrics are computed
    Then for each metric, median equals P5 and P95
