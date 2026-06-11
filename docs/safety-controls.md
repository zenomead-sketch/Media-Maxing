# Safety Controls

The Safety Center is the app's central place to pause automation, review safety status, and run local kill-switch actions.

The MVP remains local-first. The Safety Center does not publish posts, send replies, call social APIs, or revoke provider tokens remotely.

## Approval required

Approval required is the default safety rule. Generated drafts start as
`needs_review`. The user must review and approve a draft before it can be
scheduled. Reply suggestions also require human review. Local approval never
sends a reply to a real platform.

## Emergency Pause

Emergency pause blocks risky actions:

- Scheduling new posts.
- Moving due scheduled posts to ready queue state.
- Mock publishing.
- Manual export package creation in the MVP.
- Future real publishing eligibility.
- Future real reply sending.
- AI auto-action placeholders.
- Automation levels above `approval_queue`.

Emergency pause does not block safe local work:

- Viewing existing data.
- Editing drafts.
- Editing Brand Brain.
- Importing or organizing media.
- Creating backups or diagnostic reports.
- Reading analytics and weekly reports.
- Adding manual notes or local status changes.

When pause is enabled, the app forces automation back to `approval_queue` if needed and records a `safety_audit_logs` entry.

## Automation Levels

The Safety Center displays all planned automation levels:

- `manual_assist`
- `approval_queue`
- `semi_auto_scheduling`
- `safe_auto_posting`
- `autonomous_content_engine`

In the MVP, only `manual_assist` and `approval_queue` can be selected. Higher levels are shown so the user understands the roadmap, but they remain locked and do not enable real publishing or real replies.

## Safety flags

Safety flags warn the user about risky content. Critical safety flags block
scheduling and future publishing eligibility until the content is fixed. Common
critical problems include invented testimonials, unsupported guarantees,
private customer information risk, missing proof for brand claims, or attempts
to bypass approval.

## Reply approval

AI reply suggestions are local drafts. The user can edit, approve locally,
reject, mark manually sent, archive, escalate, or mark spam. Critical reply
safety flags block local approval until the suggestion is edited and reviewed.

## Real publishing disabled

Real publishing disabled is the current policy. The app can prepare content,
schedule locally, run preflight, mock publish locally, and create manual export
packages, but it must not publish to real social platforms.

## Manual export fallback

Manual export fallback is the safe posting path. The app writes a local package
with caption, hashtags, metadata, media manifest, and posting instructions. The
user posts manually outside the app.

## The AI should never

The AI should never invent testimonials, customer names, pricing, scheduling
availability, certifications, insurance, awards, guarantees, or fake social
proof. It should not claim a post or reply was sent when it was only drafted.
It should not hide safety flags or argue with complaints.

## Kill switch actions

Dangerous actions require a typed confirmation phrase.

Current actions:

- Pause all automation.
- Cancel future scheduled posts.
- Disable queue processing.
- Disconnect connected or mock accounts locally.
- Mark stored token metadata revoked locally.
- Disable AI generation temporarily.
- Export a redacted safety report.
- Full local reset placeholder.

These actions prefer reversible local state changes. The full local reset is intentionally a placeholder and does not delete data.

## Audit Log

Safety actions are written to `safety_audit_logs`.

Tracked actions include:

- `emergency_pause_enabled`
- `emergency_pause_disabled`
- `automation_level_changed`
- `kill_switch_action_started`
- `kill_switch_action_completed`
- `queue_processing_disabled`
- `accounts_disconnected`
- `tokens_marked_revoked`
- `scheduled_posts_canceled`
- `ai_generation_disabled`
- `safety_report_exported`

The audit log stores safe JSON details and timestamps. It must not include tokens, client secrets, authorization codes, or raw provider responses.

## Service Enforcement

Emergency pause and safety flags are checked outside the UI:

- Scheduling uses the approval queue safety gate.
- Publish Queue mock publishing and manual completion check app settings.
- Manual export checks emergency pause before writing a package.
- The local job runner uses preflight and will not mark items ready while paused.
- The queue-processing kill switch makes the local job runner exit without changing queue readiness.

The UI is not the source of truth. Services must continue to enforce safety rules when called directly from scripts or tests.
