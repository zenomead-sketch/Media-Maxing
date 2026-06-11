# TODO

## Critical before real users

- Complete a manual browser pass using `docs/launch-candidate-checklist.md`.
- Add a simple app version display in the UI.
- Decide whether launch artifacts under `data/launch-check/` should be auto-cleaned by default.
- Improve empty fresh-database flows where seeded demo data is currently easiest.
- Confirm Backup and Diagnostics paths are obvious to non-coder testers.

## Important before real publishing

- Implement one real OAuth path end to end with secure token storage.
- Add account selection for platforms with multiple pages/accounts/channels.
- Verify platform API requirements from official docs at implementation time.
- Keep real publishing disabled until approval, preflight, audit, emergency pause, and rollback gates are proven.
- Add post-publish audit logs before any real platform call.

## Nice to have

- Add richer dashboard charts without adding heavy dependencies too early.
- Add a visual setup progress indicator across Home, Settings, and Onboarding.
- Add more guided copy for first-time users on empty screens.
- Add import/export buttons that open local folders in a desktop wrapper.

## Research needed

- Tauri versus Electron final packaging tradeoffs.
- Best OS keychain/encrypted local token storage for Windows-first testing.
- Local background runner options for desktop mode.
- Better local AI/media analysis options for job photos and videos.

## Platform API verification

- Meta Pages, Instagram Business/Creator, and Threads OAuth scopes.
- YouTube Shorts upload and channel profile requirements.
- TikTok content posting and app review requirements.
- LinkedIn organization/page posting requirements.
- X API access, pricing, rate limits, and posting requirements.

## Security hardening

- Add OS keychain or encrypted local token storage before real OAuth is used with real accounts.
- Keep redaction tests for logs, diagnostics, errors, backups, and frontend-safe DTOs.
- Add a pre-commit or CI security scan later.
- Review all export formats for private customer information before broader testing.

## UX improvements

- Improve keyboard handling for modal-like panels.
- Add clearer success/failure notifications to every long-running local action.
- Add richer table collapse behavior for narrow screens.
- Add final non-coder guided walkthrough copy for the first test release.

## Desktop packaging

- Choose and implement Tauri or Electron.
- Add packaging scripts only after the package manager and desktop structure are settled.
- Add signed installer notes and release artifact process.
- Limit desktop filesystem permissions to app data and user-selected files.
