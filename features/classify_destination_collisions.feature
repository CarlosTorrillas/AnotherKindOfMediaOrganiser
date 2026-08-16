Feature: Classify Destination Collisions
  As a user
  I want collisions classified by verified file content
  So that identical files and files requiring review remain distinct

  Scenario: Classify identical colliding files as Exact Duplicates
    Given two colliding Media Entries with identical content
    When the Organisation Proposal classifies the Destination Collision
    Then one receives the normal proposed destination
    And the other receives an exactDuplicates review destination

  Scenario: Classify different colliding files as Potential Conflicts
    Given two colliding Media Entries with different content
    When the Organisation Proposal classifies the Destination Collision
    Then one receives the normal proposed destination
    And the other receives a potentialConflicts review destination

  Scenario: Same filename does not imply duplicate
    Given two colliding Media Entries with the same filename but different content
    When the Organisation Proposal classifies the Destination Collision
    Then neither is classified as an Exact Duplicate

  Scenario: Classify multiple Exact Duplicates
    Given four colliding Media Entries with identical content
    When the Organisation Proposal classifies the Destination Collision
    Then one receives the normal proposed destination
    And every additional copy receives a unique deterministic exactDuplicates destination

  Scenario: Classify mixed duplicate and conflicting content
    Given a Destination Collision where A equals B equals C and D differs
    When the Organisation Proposal classifies the Destination Collision
    Then A receives the normal proposed destination
    And B and C are represented as Exact Duplicates
    And D is represented as a Potential Conflict
    And every source Media Entry remains represented exactly once

  Scenario: Classification is deterministic
    Given a Media Collection containing a Destination Collision
    When the Organisation Proposal is generated repeatedly
    Then canonical selection and review destinations are identical

  Scenario: Unreadable content becomes an Unverified Conflict
    Given a Destination Collision with an unreadable non-canonical file
    When the Organisation Proposal classifies the Destination Collision
    Then the unreadable file is represented as an Unverified Conflict
    And it is not an Exact Duplicate or Potential Conflict

  Scenario: Classification remains read-only
    Given a readable Media Collection containing a Destination Collision
    When the Organisation Proposal classifies the Destination Collision
    Then collision classification leaves the Media Collection unchanged

