# Glossary

Real publishing is disabled in this build. These terms describe local workflow
objects and future integration concepts.

## Brand Brain

The saved business identity: services, service areas, voice, CTA, claims,
warnings, and preferences.

## Media Asset

A local photo or video record plus metadata such as tags, notes, service type,
and file path.

## Generated Draft

AI-created content saved for review. Generated drafts default to `needs_review`.

## Approval Queue

The service and workflow that controls whether drafts can be approved,
rejected, revised, archived, scheduled, or considered for future publishing.

## Scheduled Post

A local Calendar item created from an approved draft. It stores a caption and
media snapshot.

## Publish Queue

The local queue that tracks waiting, ready, blocked, manually exported, mock
published, failed, canceled, and skipped posting work.

## Preflight

The safety and requirements check before a queued item can be ready.

## Manual Export

A local package with caption, hashtags, metadata, media manifest, and posting
instructions for manual posting.

## Mock Publish

A local-only status used for testing. It does not publish to a real platform.

## Engagement Item

A local comment, mention, message, review, lead, or system note.

## Reply Suggestion

An AI-assisted draft reply that must be reviewed. Approval is local only and
does not send a reply.

## AI Memory

Evidence-backed local learning about what content, replies, platforms, or
strategies seem to work.

## Weekly Report

A local summary of recent performance, engagement, insights, and recommended
next actions.

## Emergency Pause

A safety control that blocks risky automation such as scheduling, queue
readiness, mock publishing, manual export package creation, and future real
actions.

## Connector

A platform integration module for services such as Facebook, Instagram, YouTube,
TikTok, LinkedIn, or X. Current connectors are scaffolds or mock-ready.

## OAuth

The sign-in flow platforms use to grant app access. Real OAuth is scaffolded but
not production-ready.

## Token

A sensitive credential from a platform or provider. Tokens must not be shown,
logged, committed, or included in normal backups.

## Local-first

The app stores and processes data on your machine by default.
