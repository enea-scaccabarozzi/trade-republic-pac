Feature: Dashboard Run Listing

  Background:
    Given the result store contains saved backtest runs

  Scenario: Run listing table shows saved results
    When the results page is loaded
    Then a table displays the saved runs
    And each row shows the strategy name
    And each row shows the date range
    And each row shows the final value

  Scenario: Empty result store shows placeholder
    Given the result store is empty
    When the results page is loaded
    Then a message indicates no results are available

  Scenario: Clicking a run navigates to detail page
    When the results page is loaded
    And the user clicks on a run row
    Then the detail URL contains the run ID

  Scenario: Corrupted run files are skipped gracefully
    Given the result store contains a corrupted JSON file
    When the results page is loaded
    Then the corrupted run is not shown in the table
    And remaining valid runs are still displayed
