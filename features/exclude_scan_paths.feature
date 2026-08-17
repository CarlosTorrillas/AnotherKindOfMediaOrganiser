Feature: Exclude paths from a Media Collection scan
  As a user
  I want intentional exclusions distinguished from access failures
  So that operating-system metadata can be omitted without weakening scan safety

  Scenario: Exclude known macOS metadata by default
    Given a Media Collection containing a known macOS metadata directory
    When the Media Collection is scanned with default exclusions
    Then the metadata directory is reported as excluded
    And the scan remains complete

  Scenario: Do not exclude arbitrary hidden directories
    Given a hidden directory containing user media
    When the Media Collection is scanned with default exclusions
    Then the hidden media is included in the scan

  Scenario: Exclude a user-selected subtree
    Given a Media Collection containing an explicitly excluded subtree
    When the Media Collection is scanned with that exclusion
    Then media in the excluded subtree is absent
    And the excluded subtree is reported

  Scenario: Preserve unexpected access failures
    Given a non-excluded directory reports an access failure
    When the Media Collection is scanned with default exclusions
    Then the scan remains incomplete

  Scenario: Reject an exclusion outside the Media Collection
    Given an exclusion that escapes the Media Collection
    When the Media Collection scan is requested
    Then the exclusion is rejected before scanning

