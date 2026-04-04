Feature: Channel Auto-Discovery
  The framework automatically discovers delivery channels
  by scanning the channels package for DeliveryChannel subclasses.

  Scenario: All builtin channels are discovered
    When the builtin channels package is scanned
    Then the discovered channels include "telegram"

  Scenario: Discovered channels have valid config models
    When the builtin channels package is scanned
    Then each discovered channel has a config_model attribute
    And each config_model is a Pydantic BaseModel subclass

  Scenario: Subdirectories without channel.py are ignored
    Given a channels package containing a subdirectory with no channel.py
    When that channels package is scanned
    Then no channels are discovered from that subdirectory

  Scenario: Abstract intermediate classes are ignored
    Given a channels package with an abstract DeliveryChannel subclass
    When that channels package is scanned
    Then the abstract class is not included in discovered channels
