Feature: Plan Organisation Execution within destination capacity
  As a user
  I want capacity checked before organisation
  So that execution does not intentionally fill the destination

  Scenario: Execute the full proposal when it fits
    Given a chronological Organisation Proposal that fits usable capacity
    When Capacity Preflight is performed
    Then the full Organisation Proposal is selected unchanged

  Scenario: Select complete chronological months when the full proposal does not fit
    Given January and February fit but March exceeds usable capacity
    When Capacity Preflight is performed
    Then January and February are selected in chronological order
    And March is excluded completely
    And every included placement keeps its original destination

  Scenario: Keep Name Conflicts in their complete month
    Given a month containing canonical and Name Conflict placements
    When that month is selected by Capacity Preflight
    Then both colliding placements remain in the selected month

  Scenario: Do not offer a partial proposal when its oldest month does not fit
    Given the oldest complete month exceeds usable capacity
    When Capacity Preflight is performed
    Then there is no executable Organisation Proposal

  Scenario: Decline a partial Organisation Proposal
    Given Capacity Preflight offers a partial Organisation Proposal
    When the user declines partial Organisation Execution
    Then no destination content is written

