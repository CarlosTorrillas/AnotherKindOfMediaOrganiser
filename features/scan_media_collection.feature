Feature: Scan a media collection safely
  As a user
  I want to scan a folder containing my media
  So that I can understand what it contains before making any changes

  Scenario: Scan a folder containing supported media
    Given a directory containing these supported media files:
      | filename     |
      | portrait.jpg |
      | holiday.heic |
      | camera.arw   |
      | clip.mp4     |
    When the user scans the directory
    Then the scan reports 4 total files
    And the scan reports 4 recognised media files
    And the media counts are 2 images, 1 RAW file, and 1 video

  Scenario: Scan nested directories
    Given a directory containing media files in two nested directories
    When the user scans the directory
    Then the nested media files are included in the result
    And the scan reports 3 directories scanned

  Scenario: Unsupported files are reported
    Given a directory containing 1 supported media file and 2 unsupported files
    When the user scans the directory
    Then the scan reports 2 unsupported files
    And the scan reports 1 recognised media file

  Scenario: Extension matching is case-insensitive
    Given a directory containing mixed-case media extensions
    When the user scans the directory
    Then the media counts are 1 image, 1 RAW file, and 1 video

  Scenario: Scan an empty directory
    Given an empty directory
    When the user scans the directory
    Then the scan reports 0 total files
    And the scan reports 0 recognised media files
    And the scan reports 0 unsupported files

  Scenario: Do not follow directory symbolic links
    Given a directory containing a symbolic link to an external directory
    When the user scans the directory
    Then the symbolic link is not recursively followed

