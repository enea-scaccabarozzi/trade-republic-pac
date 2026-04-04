Feature: Config-driven wiring
  The orchestrator wires config to rules, channels, and templates at startup.

  Scenario: Valid config wires successfully
    Given a config with valid signals, rules, and channels
    When the orchestrator is created from settings
    Then all rules are registered
    And all channels are instantiated with typed config

  Scenario: Config references unknown rule
    Given a config with signal referencing rule "nonexistent"
    When the orchestrator is created from settings
    Then a validation error is raised mentioning "unknown rule"

  Scenario: Config references unknown channel type
    Given a config with channel type "discord" not discovered
    When the orchestrator is created from settings
    Then a validation error is raised mentioning "unknown type"

  Scenario: Config references unknown template
    Given a config with signal referencing template "nonexistent"
    When the orchestrator is created from settings
    Then a validation error is raised mentioning "unknown template"
