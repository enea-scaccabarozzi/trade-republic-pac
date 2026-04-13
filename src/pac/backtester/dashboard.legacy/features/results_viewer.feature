Feature: Results Viewer

  Background:
    Given a saved backtest run with equity curve and trade data

  Scenario: Results page displays config summary
    When the results viewer loads the run
    Then the config summary shows the strategy name
    And the config summary shows the date range
    And the config summary shows the number of iterations

  Scenario: Results page displays KPI values
    When the results viewer loads the run
    Then the KPIs include total invested amount
    And the KPIs include final portfolio value with confidence interval
    And the KPIs include total return percentage
    And the KPIs include total fees
    And the KPIs include total trades

  Scenario: Equity curve chart is built from run data
    When the equity curve chart is built
    Then the chart contains a median line trace
    And the chart contains a P5/P95 confidence band
    And the chart has a range slider for zoom

  Scenario: Allocation chart is built from run data
    When the allocation chart is built
    Then the chart contains a stacked area trace for each asset

  Scenario: Drawdown chart is built from equity curve
    When the drawdown chart is built
    Then the chart contains a filled area trace
    And drawdown values are non-positive

  Scenario: Metrics table shows strategy vs benchmark comparison
    Given the run includes benchmark metrics
    When the results viewer loads the run
    Then the metrics table shows strategy values with confidence intervals
    And the metrics table shows benchmark values
    And outperforming metrics are highlighted as positive

  Scenario: Trade log displays all trades
    When the results viewer loads the run
    Then the trade log contains all trade records
    And each trade shows date, type, asset, direction, amount, and fee

  Scenario: Filtering by date range narrows chart data
    When the user filters to a sub-period
    Then the equity curve chart shows only data within that period
    And the trade log shows only trades within that period

  Scenario: Filtering by asset narrows allocation and trades
    When the user filters to a specific asset
    Then the allocation chart shows only the selected asset
    And the trade log shows only trades for the selected asset

  Scenario: Run not found shows error state
    When the results viewer loads a nonexistent run
    Then an error message indicates the run was not found
    And a back button navigates to the results list
