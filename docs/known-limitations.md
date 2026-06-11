# Known Limitations

This document is deliberately blunt. The app is a local-first test release, not production SaaS.

## Real publishing disabled

Real publishing disabled is the current policy. The app can prepare content, schedule locally, run preflight, and create Manual Export packages, but it must not post to real platforms.

## Real analytics are not fetched by default

Analytics can be entered manually or generated as mock/demo data. Real analytics are not fetched by default, and platform API analytics need future OAuth, permissions, and API verification.

## Real comments are not fetched by default

The Engagement Inbox uses mock/manual data in this release. Real comments, mentions, DMs, and reviews are not fetched by default.

## Real replies are not sent

AI can suggest replies and the user can approve them locally. Real replies are not sent. Marking a reply manually sent only records that the user handled it outside the app.

## Platform limits require verification

Caption lengths, media requirements, title requirements, scopes, and account requirements are practical placeholders until each platform is verified against official docs during real integration work.

## OAuth requires real developer app setup later

OAuth scaffolding and mock mode exist. Real OAuth requires developer apps, redirect URIs, scopes, app review awareness, and explicit safety flags.

## Token storage needs hardening

Token storage defaults to placeholder/not-stored behavior. Before real OAuth is used seriously, token storage should use OS keychain or encrypted local storage. Token storage must never expose raw tokens to frontend code.

## Desktop packaging is not finished

Desktop packaging is prepared and documented, but there is no signed production installer. Desktop packaging may need signing, installer configuration, filesystem permission review, and native folder/file picker hardening.

## AI output quality depends on provider and prompts

Mock AI is deterministic and useful for tests. Real output quality will depend on provider configuration, Brand Brain quality, prompt versions, media metadata, and evaluation coverage.

## Local scheduling only works while app/backend is running

Local scheduling only works while app/backend is running unless a desktop/background service is implemented. The local job runner can process due items when invoked, but it is not an OS-level scheduler.

## Local-first means local responsibility

Backups, media, exports, diagnostics, and local databases live on the user machine. Users should back up their data before destructive changes.

## Launch status is partial

Automated launch checks pass for local workflows and safety, but the release status is partial because there is no package-manager build command or production desktop installer yet.
