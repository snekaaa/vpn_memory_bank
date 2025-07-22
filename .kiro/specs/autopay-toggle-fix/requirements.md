# Requirements Document

## Introduction

This document outlines the requirements for fixing a bug in the VPN service Telegram bot where the autopay toggle state is not being saved when a user without an active subscription visits the subscription section. Currently, when a user without a subscription toggles the autopay setting, the UI updates correctly but the setting is not persisted, causing inconsistent behavior.

## Requirements

### Requirement 1

**User Story:** As a user without an active subscription, I want my autopay preference to be saved when I toggle it in the subscription section, so that my choice is remembered when I make a purchase.

#### Acceptance Criteria

1. WHEN a user without an active subscription toggles the autopay setting to "off" THEN the system SHALL persist this preference in the database.
2. WHEN a user without an active subscription toggles the autopay setting to "on" THEN the system SHALL persist this preference in the database.
3. WHEN a user without an active subscription returns to the subscription section THEN the system SHALL display the previously selected autopay preference.
4. WHEN a user without an active subscription makes a purchase THEN the system SHALL respect their previously selected autopay preference.

### Requirement 2

**User Story:** As a developer, I want to ensure consistent autopay preference handling between users with and without active subscriptions, so that the user experience is seamless.

#### Acceptance Criteria

1. WHEN a new user accesses the subscription section for the first time THEN the system SHALL set a default autopay preference (currently "on").
2. WHEN the system processes a payment THEN it SHALL check the user's stored autopay preference rather than relying on UI state.
3. WHEN a user's subscription expires THEN the system SHALL maintain their autopay preference setting.
4. WHEN the system displays subscription options THEN it SHALL always show the correct current autopay preference state.

### Requirement 3

**User Story:** As a system administrator, I want to ensure that autopay preferences are properly stored and retrieved, so that the system behaves consistently and predictably.

#### Acceptance Criteria

1. WHEN the backend API receives a request to update autopay preferences THEN it SHALL update the database regardless of the user's subscription status.
2. WHEN the backend API receives a request for autopay preference information THEN it SHALL return the stored preference regardless of the user's subscription status.
3. WHEN a database error occurs during autopay preference update THEN the system SHALL log the error and inform the user that their preference could not be saved.
4. WHEN the system cannot retrieve a user's autopay preference THEN it SHALL fall back to the default value and log the issue.