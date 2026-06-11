# First-Run Onboarding

First-run onboarding guides a non-coder through the safest local setup path. It does not connect real social accounts, publish posts, fetch analytics, or send replies.

## What Onboarding Covers

The onboarding screen walks through:

- Welcome and safety overview.
- Local data directory confirmation.
- First Brand Brain profile.
- Basic business details, services, service areas, voice, and common CTA.
- Default draft platforms.
- Approval-first safety settings.
- Optional first media import or skip.
- Optional demo draft request.
- Next steps for normal app use.

## Safety Defaults

Onboarding confirms these defaults:

- Require approval before publishing: `true`.
- Require approval before replying: `true`.
- Emergency pause: `false`.
- Automation level: `approval_queue`.
- Real publishing: disabled.
- Real auto-replies: disabled.

Completing onboarding does not publish anything and does not connect to platform APIs.

## Where State Is Stored

Onboarding state is stored locally in the `onboarding_state` SQLite table when the localhost bridge is running. The browser-only fallback stores the same state in localStorage for demo use.

The stored state tracks:

- Overall status: `not_started`, `in_progress`, `completed`, or `skipped`.
- Current step.
- Completed steps.
- Skipped steps.
- Checklist overrides.

## Setup Checklist

The Home screen / Control Center shows a reusable setup checklist until the
important setup work is done. It also shows the recommended next action, work
that needs attention, ready local tasks, this week's schedule signals, and
safety status. Checklist items include:

- Brand profile created.
- Local data directory ready.
- Safety settings confirmed.
- Media added.
- First draft generated.
- First draft approved.
- First post scheduled.
- Manual export tested.
- Analytics demo or manual metrics added.
- Social accounts mock connected or setup reviewed.

Statuses are `not_started`, `in_progress`, `completed`, `skipped`, or `needs_attention`.

## Completing Onboarding

When the user completes onboarding:

1. The app validates that the business name is present.
2. The Brand Brain is created or updated locally.
3. Safe app settings are confirmed.
4. Default platforms are stored in settings metadata.
5. Onboarding status becomes `completed`.
6. If requested, a demo draft is saved as `needs_review`.

The demo draft is local only and still requires normal review.

## Skipping And Restarting

The user may skip onboarding with confirmation. Skipping does not block the app.

The user can restart onboarding from Settings. Restarting changes onboarding status back to `in_progress`; it does not delete Brand Brain, media, drafts, schedules, analytics, engagement items, or other records.

## Limitations

- Changing the local data directory is a placeholder until desktop packaging support exists.
- Browser-only mode uses localStorage and is only a demo fallback.
- Media import depends on the local bridge for real local file copying.
- Social account setup remains mock/scaffolded in this build.
