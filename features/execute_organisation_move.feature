Feature: Execute an Organisation Proposal by moving
  As a user
  I want to move media into a separate Destination Collection
  So that originals are removed only after their copies are verified

  Scenario: Move recognised media safely
    Given a valid Organisation Proposal for moving
    When the user accepts MOVE Organisation Execution
    Then each destination contains the original source content
    And each source is deleted only after its destination is verified

  Scenario: Preserve the source when copying fails
    Given a valid Organisation Proposal for moving
    When MOVE copying fails
    Then the source media remains

  Scenario: Preserve the source when verification fails
    Given a valid Organisation Proposal for moving
    When MOVE verification fails
    Then the source media remains

  Scenario: Report a deletion failure without removing either copy
    Given a valid Organisation Proposal for moving
    When MOVE source deletion fails
    Then the verified destination remains
    And the source media remains

  Scenario: Cancel before the current source is verified
    Given a valid Organisation Proposal for moving
    When MOVE is cancelled during verification
    Then the current source media remains

  Scenario: Move Name Conflict placements exactly as proposed
    Given a MOVE proposal containing Name Conflicts
    When the user accepts MOVE Organisation Execution
    Then canonical and nameConflicts placements exist at their proposed destinations

