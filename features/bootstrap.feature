Feature: Behave test infrastructure
  The project needs executable acceptance-test infrastructure before business
  features are introduced.

  Scenario: Behave can execute project step definitions
    Given the Behave test infrastructure is configured
    Then the infrastructure scenario passes

