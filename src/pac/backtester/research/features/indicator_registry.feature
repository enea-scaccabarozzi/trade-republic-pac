Feature: Indicator Registry

  Background:
    Given an indicator registry with minimal price data

  Scenario: A new registry has no indicators registered
    Then no indicators are registered

  Scenario: Registering the crisis pack makes crisis indicators available
    When the "crisis" indicator pack is registered
    Then the registry contains the "drawdown" indicator
    And the registry contains the "death_cross" indicator

  Scenario: Registering an unknown pack raises a descriptive error
    When the "nonexistent_pack" indicator pack is registered
    Then a ValueError is raised

  Scenario: A custom indicator function can be registered
    When a custom indicator named "my_sma" is registered
    Then the registry contains the "my_sma" indicator
