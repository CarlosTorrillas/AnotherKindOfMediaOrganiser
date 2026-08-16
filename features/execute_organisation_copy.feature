Feature: Execute an Organisation Proposal by copying
  As a user
  I want to copy media into a separate Destination Collection
  So that the source Media Collection remains untouched

  Scenario: Copy recognised media into an empty Destination Collection
    Given a source Media Collection and an empty Destination Collection
    When the user accepts Organisation Execution
    Then recognised media is copied to its proposed destination
    And the source Media Collection remains unchanged by execution

  Scenario: Copy Name Conflict placements exactly as proposed
    Given a lightweight Organisation Proposal containing Name Conflicts
    When the user accepts Organisation Execution
    Then canonical and nameConflicts placements are copied exactly as proposed

  Scenario: Decline Organisation Execution
    Given a valid Organisation Proposal for copying
    When the user declines Organisation Execution
    Then no Destination Collection is created

  Scenario: Reject an existing destination file during preflight
    Given a proposed destination file already exists
    When Organisation Execution is requested
    Then execution fails before confirmation
    And no source media is copied
    And the existing destination file remains untouched

  Scenario Outline: Reject unsafe source and destination relationships
    Given the Destination Collection is <relationship> the source Media Collection
    When Organisation Execution is requested
    Then execution is rejected before writing

    Examples:
      | relationship |
      | the same as  |
      | inside       |
      | containing   |

  Scenario: Stop safely after a runtime copy failure
    Given Organisation Execution has completed one copy
    When the next copy operation fails
    Then the completed destination copy remains
    And the failed destination is not presented as completed
    And the source Media Collection remains unchanged by execution

  Scenario: Cancel copying safely
    Given Organisation Execution is copying media
    When copying is cancelled
    Then completed destination copies remain
    And the incomplete destination is not presented as completed
    And the source Media Collection remains unchanged by execution
