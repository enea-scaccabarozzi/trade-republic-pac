Feature: Backtest Wizard

  Background:
    Given the available strategies include "pac_alignment"

  Scenario: Strategy selection shows info panel
    When the user selects strategy "pac_alignment"
    Then the info panel shows the strategy description
    And the info panel shows the params schema

  Scenario: Form validates required fields
    When the user submits the form with an empty start date
    Then a validation error is shown for the start date field

  Scenario: Form validates date range
    When the user submits with start date after end date
    Then a validation error indicates start must be before end

  Scenario: Form validates PAC days range
    When the user submits with PAC day "32"
    Then a validation error indicates PAC days must be 1-28

  Scenario: Form validates strategy params JSON
    When the user submits with strategy params "not json"
    Then a validation error indicates invalid JSON

  Scenario: Successful backtest run
    Given a valid backtest configuration
    When the user submits the form
    Then execution progress is reported
    And concurrent submissions are prevented

  Scenario: Pipeline error is displayed
    Given the pipeline will fail with a config error
    When the user submits the form
    Then an error notification is shown
    And new submissions are accepted

  Scenario: Re-run pre-fills form from previous run
    Given a saved backtest run with strategy "pac_alignment"
    When the wizard loads with query parameter from_run set to the run ID
    Then the strategy field shows "pac_alignment"
    And the date fields match the previous run's dates
    And the initial cash matches the previous run's value
