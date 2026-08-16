Feature: Verify destination collisions
  As a user
  I want to explicitly verify files competing for the same destination
  So that I can distinguish identical content from files requiring review

  Scenario: Explicitly verify identical colliding files
    Given two colliding Media Entries with identical content
    When the user verifies destination collisions
    Then collision verification reports one Exact Duplicate

  Scenario: Explicitly verify different colliding files
    Given two colliding Media Entries with different content
    When the user verifies destination collisions
    Then collision verification reports one Potential Conflict

  Scenario: Report no collisions requiring verification
    Given a Media Collection without Destination Collisions
    When the user verifies destination collisions without hashing
    Then no collisions require verification

  Scenario: Reuse completed collision verification
    Given a Destination Collision has already been content-verified
    When the user verifies the same collision again
    Then collision verification reports cached hashes were reused

  Scenario: Collision verification is read-only
    Given a readable Media Collection containing a Destination Collision
    When the user verifies destination collisions
    Then collision verification leaves the Media Collection unchanged
