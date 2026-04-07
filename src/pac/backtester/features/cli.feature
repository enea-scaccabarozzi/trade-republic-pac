Feature: Backtester CLI
  As a PAC user
  I want to validate my signal configuration against historical data
  So that I can assess strategy performance before using it live

  Background:
    Given the backtest dependencies are installed
    And a valid pac.yaml config file exists

  Scenario: Run a backtest in batch mode
    When I run "python -m pac.backtester run --strategy pac_alignment --start 2020-01-01 --end 2021-12-31"
    Then the CLI exits with code 0
    And the output contains "Backtest Results"
    And a JSON result file is saved under ".pac/backtests/"

  Scenario: Run with unknown strategy
    When I run "python -m pac.backtester run --strategy nonexistent --start 2020-01-01 --end 2021-12-31"
    Then the CLI exits with code 1
    And the output contains "Unknown strategy"

  Scenario: List available strategies
    When I run "python -m pac.backtester strategies"
    Then the CLI exits with code 0
    And the output contains "pac_alignment"

  Scenario: List results when none exist
    Given no backtest runs are saved
    When I run "python -m pac.backtester results"
    Then the CLI exits with code 0
    And the output contains "No saved backtest runs"

  Scenario: Show a saved result
    Given a saved backtest run with ID "test_run_001"
    When I run "python -m pac.backtester show test_run_001"
    Then the CLI exits with code 0
    And the output contains "Backtest Results"

  Scenario: Show an unknown result
    When I run "python -m pac.backtester show nonexistent_run_id"
    Then the CLI exits with code 1
    And the output contains "No backtest result found"
