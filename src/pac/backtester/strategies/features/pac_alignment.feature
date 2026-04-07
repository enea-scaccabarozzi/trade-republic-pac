Feature: PAC Alignment Strategy
  As a PAC investor
  I want my monthly PAC contributions automatically redirected toward underweight assets
  So that my portfolio gravity pulls back toward the target allocation without hard rebalances

  Background:
    Given a three-asset portfolio with targets 70% stocks / 15% gold / 15% bonds
    And a PacAlignmentStrategy with default params

  Scenario: No PAC adjustment when portfolio is at target
    Given the portfolio is at exactly the target allocation
    When on_pac_date is called
    Then no PAC adjustment is returned

  Scenario: PAC is fully redirected at blend_factor 1.0
    Given stocks is overweight at 80% (target 70%)
    And gold is underweight at 10% (target 15%)
    And bonds is underweight at 10% (target 15%)
    When on_pac_date is called with blend_factor 1.0
    Then the PAC allocation for stocks is the minimum (€1)
    And gold and bonds receive the majority of the PAC budget

  Scenario: PAC is target-proportional at blend_factor 0.0
    Given stocks is overweight at 80% (target 70%)
    And gold is underweight at 10% (target 15%)
    And bonds is underweight at 10% (target 15%)
    When on_pac_date is called with blend_factor 0.0
    Then a PacAdjustment is returned with volumes proportional to target weights
    And the stocks allocation is 70% of the total PAC budget

  Scenario: On-signals always returns no actions
    Given any set of signals including cycle_inversion
    When on_signals is called
    Then an empty list is returned

  Scenario: Strategy is auto-discovered
    When the builtin strategies package is scanned
    Then "pac_alignment" is in the discovered strategies
