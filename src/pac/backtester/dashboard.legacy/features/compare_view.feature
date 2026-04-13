Feature: Compare View

  Background:
    Given multiple saved backtest runs

  Scenario: Overlaid equity curves from two runs
    When the user selects two runs for comparison
    Then the overlay chart contains a median trace for each run
    And each trace uses a distinct color

  Scenario: Confidence bands can be toggled
    Given two runs are loaded for comparison
    When confidence bands are enabled
    Then the overlay chart includes P5/P95 shaded bands for each run

  Scenario: Metrics comparison table highlights best performer
    When the user selects two runs for comparison
    Then the metrics table shows one column per run
    And the best value per metric is highlighted

  Scenario: Summary cards show KPIs side by side
    When the user selects two runs for comparison
    Then a KPI summary card is shown for each run

  Scenario: Allocation charts shown per run in tabs
    When the user selects two runs for comparison
    Then allocation charts are available in separate tabs

  Scenario: URL contains selected run IDs
    When the user selects two runs for comparison
    Then the URL query string contains the run IDs

  Scenario: No runs selected shows empty state
    When no runs are selected
    Then a prompt message asks the user to select runs

  Scenario: Single run selected shows data with info banner
    When only one run is selected
    Then the charts display data for that run
    And an info banner suggests adding more runs
