Feature: CLI Results Display
  As a backtester user
  I want to see charts and detailed tables when viewing results
  So that I can quickly assess strategy performance

  Background:
    Given a saved backtest run with equity curve data
    And the run has trades and metrics

  Scenario: Show command displays equity curve chart
    When I view the backtest result
    Then the output contains "Equity Curve"

  Scenario: Show command displays drawdown chart
    When I view the backtest result
    Then the output contains "Drawdown"

  Scenario: Show command displays asset allocation chart
    When I view the backtest result
    Then the output contains "Asset Allocation"

  Scenario: Show command displays trade log table
    When I view the backtest result
    Then the output contains "Trade Log"
    And the output contains "BUY"
    And the output contains "SELL"

  Scenario: Show command displays metrics comparison
    Given the run includes benchmark metrics
    When I view the backtest result
    Then the output contains "Performance Metrics"

  Scenario: Show command without plotext falls back gracefully
    Given plotext is not installed
    When I view the backtest result
    Then the output contains a hint to install plotext
    And the output contains "Performance Metrics"

  Scenario: Show command truncates long trade logs
    Given the run has more than 50 trades
    When I view the backtest result
    Then the output contains "Showing last 50"
