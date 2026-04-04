Feature: Configuration Loading
  The system loads its configuration from a YAML file,
  interpolates environment variables, and validates the schema.

  Background:
    Given a valid pac.yaml configuration file

  Scenario: Load valid configuration
    When the configuration is loaded
    Then the settings contain the expected values
    And the asset target percentages sum to 100

  Scenario: Environment variable interpolation
    Given the environment variable "TEST_SECRET" is set to "my-secret"
    And the config file contains "${TEST_SECRET}" as the job_secret
    When the configuration is loaded
    Then the job_secret is "my-secret"

  Scenario: Missing environment variable raises error
    Given the config file references "${MISSING_VAR}"
    And the environment variable "MISSING_VAR" is not set
    When the configuration is loaded
    Then a ValueError is raised mentioning "MISSING_VAR"

  Scenario: Config file not found
    Given no config file exists at the specified path
    When the configuration is loaded
    Then a FileNotFoundError is raised

  Scenario: Invalid YAML syntax
    Given a config file with invalid YAML syntax
    When the configuration is loaded
    Then a YAML parsing error is raised

  Scenario: Asset target percentages do not sum to 100
    Given a config file where asset target_pct values sum to 90
    When the configuration is loaded
    Then a validation error is raised mentioning "sum to 100"

  Scenario: Duplicate asset IDs rejected
    Given a config file with two assets having id "stocks"
    When the configuration is loaded
    Then a validation error is raised mentioning "unique"

  Scenario: Invalid asset ID format rejected
    Given a config file with an asset id "Invalid-ID"
    When the configuration is loaded
    Then a validation error is raised

  Scenario: Invalid ISIN format rejected
    Given a config file with an asset isin "INVALID"
    When the configuration is loaded
    Then a validation error is raised

  Scenario: Signal references unknown channel
    Given a config file where signal "test" references channel "slack"
    And no channel "slack" is defined
    When the configuration is loaded
    Then a validation error is raised mentioning "unknown channel"

  Scenario: Empty assets list rejected
    Given a config file with an empty assets list
    When the configuration is loaded
    Then a validation error is raised mentioning "sum to 100"

  Scenario: Non-dict YAML root rejected
    Given a config file containing only a scalar value
    When the configuration is loaded
    Then a ValueError is raised mentioning "YAML mapping"

  Scenario: Missing version field rejected
    Given a config file without a version field
    When the configuration is loaded
    Then a validation error is raised mentioning "version"

  Scenario: Custom config path via environment variable
    Given the environment variable "PAC_CONFIG_PATH" is set to a custom path
    And a valid config file exists at that path
    When the configuration is loaded without specifying a path
    Then the settings are loaded from the custom path

  Scenario Outline: Dynamic asset count
    Given a config with <count> assets summing to 100%
    When the configuration is loaded
    Then settings.assets has <count> entries

    Examples:
      | count |
      | 1     |
      | 3     |
      | 5     |
      | 10    |
