Feature: Backtest Results Persistence
  Backtest results are saved as frontend-agnostic JSON files in .pac/backtests/
  for later retrieval, comparison, and visualization by any frontend.

  Background:
    Given a completed backtest report with 3 Monte Carlo iterations
    And a result store using a temporary directory

  Scenario: Save and load a backtest result
    When the report is converted to a run result
    And the run result is saved
    Then loading the run ID returns the same result

  Scenario: Equity curve has P5/median/P95 bands
    When the report is converted to a run result
    Then the equity curve has one point per trading day
    And each point has P5, median, and P95 values
    And P5 is less than or equal to median
    And median is less than or equal to P95

  Scenario: Allocations include all assets plus cash
    When the report is converted to a run result
    Then each allocation point includes all asset IDs and cash
    And each asset has P5, median, and P95 percentage values

  Scenario: Trade list comes from the median iteration
    When the report is converted to a run result
    Then the trade list is non-empty
    And all trades have float amounts, not Decimal

  Scenario: Summary statistics are computed
    When the report is converted to a run result
    Then the summary has total_invested, final_value, total_fees, total_trades
    And total_invested equals initial cash plus monthly contributions

  Scenario: List runs shows saved results
    Given two backtest results are saved
    When listing all runs
    Then both run IDs are returned
    And they are ordered newest first

  Scenario: Delete removes a saved result
    When the report is converted to a run result
    And the run result is saved
    And the run result is deleted
    Then loading the run ID raises an error
