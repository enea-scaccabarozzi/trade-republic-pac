Feature: Rule Auto-Discovery
  The framework automatically discovers signal rules
  by scanning the builtin rules package.

  Scenario: All builtin rules are discovered
    When the builtin rules package is scanned
    Then the discovered rules include "threshold_deviation"
    And the discovered rules include "cycle_inversion"
    And the discovered rules include "pac_plan"

  Scenario: Discovered rules have valid params models
    When the builtin rules package is scanned
    Then each discovered rule has a params_model attribute
    And each params_model is a Pydantic BaseModel subclass

  Scenario: Non-rule modules are ignored
    Given a package containing a module with no SignalRule subclass
    When that package is scanned
    Then no rules are discovered from that module

  Scenario: Abstract intermediate classes are ignored
    Given a package with an abstract SignalRule subclass
    When that package is scanned
    Then the abstract class is not included in discovered rules
