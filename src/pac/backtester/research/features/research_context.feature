Feature: ResearchContext non-IO behaviors

  Background:
    Given a ResearchContext built from two assets with known bar dates

  Scenario: Date range is computed from the intersection of all asset bars
    Then the data start date is the latest first bar across all assets
    And the data end date is the earliest last bar across all assets

  Scenario: Built-in event calendars are accessible
    Then the "crises" calendar is available
    And the "bull_runs" calendar is available
    And the "corrections" calendar is available
    And the "rate_regimes" calendar is available

  Scenario: A fresh ResearchContext has an empty indicator registry
    Then no indicators are registered in the context

  Scenario: Registering the crisis pack makes crisis indicators available
    When the "crisis" pack is registered on the context
    Then the "drawdown" indicator is available in the context
