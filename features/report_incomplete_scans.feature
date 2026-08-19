Feature: Report incomplete scans
  As a user
  I want inaccessible paths reported explicitly
  So that I never mistake a partial result for a complete collection

  Background:
    Given a Scan Result containing an inaccessible path

  Scenario: Report incomplete scan status
    When the user requests the scan summary
    Then the CLI reports that the scan is incomplete
    And the CLI reports the inaccessible path

  Scenario: Warn before presenting a partial Organisation Proposal
    When the user proposes organisation from the incomplete scan
    Then the CLI warns that the proposal includes accessible media only

  Scenario: Warn before verifying accessible collisions
    When the user verifies collisions from the incomplete scan
    Then the CLI warns that verification covers accessible media only

  Scenario: Decline incomplete Organisation Execution
    When the user declines Organisation Execution from the incomplete scan
    Then the incomplete-operation warning and inaccessible scope are reported
    And the source and Destination Collection remain unchanged

  Scenario: Continue with accessible media
    When the user accepts Organisation Execution from the incomplete scan
    Then the accessible media is organised
    And the skipped inaccessible scope is reported after completion
