"""Write and publish plausible Help Center articles for demo themes.

Usage (from knowledge-gap-agent/):
  python scripts/publish_demo_articles.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import knowledge_gap as kg  # noqa: E402
import review_store as rs  # noqa: E402

ARTICLES = {
    "bulk_user_import": """# Bulk import users via CSV

Use bulk import when you need to add many users at once instead of inviting them one by one.

## Before you start

- You need **Admin** permission in the workspace.
- Prepare a CSV file with UTF-8 encoding.
- If SSO is already enabled, imported users still need a matching identity in your identity provider before they can sign in.

## CSV format

| Column | Required | Description |
| --- | --- | --- |
| email | Yes | Work email address for the user |
| name | Yes | Display name |
| role | No | `admin`, `member`, or `viewer` (defaults to `member`) |
| team | No | Existing team name; left blank if unknown |

Download the template from **Settings → People → Bulk import → Download CSV template**.

## Import users

1. Go to **Settings → People → Bulk import**.
2. Upload your CSV file.
3. Review the preview of rows that will be created or skipped.
4. Click **Start import**.
5. When the job finishes, download the result report to see successes and failures.

## Troubleshoot common issues

### Import finishes with no new users

- Confirm the file uses commas, not semicolons.
- Check that the header row matches the template exactly (`email`, `name`, `role`, `team`).
- Open the result report: rows with invalid emails are skipped.

### Some rows fail

- Fix only the failed rows and upload again.
- Existing users matched by email are updated, not duplicated.
- Role values must match one of the allowed roles listed above.

### Large files run slowly

There is no hard row limit for a single file, but imports above a few thousand rows can take several minutes. Split very large files if the job times out.

## Re-run after fixing errors

You can upload a corrected CSV again. Users that already exist are matched by email, so a re-run does not create duplicates.

## FAQ

**Can I deactivate users with bulk import?**  
Not in this release. Deactivate users from **Settings → People**, or contact support for a bulk deactivation request.

**Is there an audit trail for who ran an import?**  
Workspace admins can review import jobs under **Settings → People → Bulk import → History**, including who started the job and when.

**Does bulk import work with SSO?**  
Yes. The import creates the user records; users then authenticate through your identity provider.
""",
    "billing_plan_migration": """# Migrate from a legacy billing plan

Legacy plans are being replaced by the current pricing tiers. This article explains what changes, what stays the same, and how to migrate.

## What changes

- Your workspace moves to one of the current tiers (Starter, Growth, or Enterprise).
- Invoice line items and plan name on the Billing page update to the new tier.
- Some grandfathered limits may be replaced by the limits of the new tier.

## What stays the same

- Existing tickets, users, integrations, and workspace settings are kept.
- Historical invoices remain available under **Settings → Billing → Invoices**.

## Before you migrate

1. Confirm you are a billing admin for the account.
2. Review the current tier comparison under **Settings → Billing → Plans**.
3. Note any grandfathered features you rely on and mark them for [VERIFY] with your account manager if needed.

## Migrate a single workspace

1. Open **Settings → Billing → Plans**.
2. Choose the target tier.
3. Review the proration summary for the remainder of the billing cycle.
4. Confirm the migration.
5. Watch for the confirmation email once the change completes.

## Migrate multiple workspaces

Each workspace is migrated separately. Start with a non-production workspace if you want to validate the new limits first.

## Mid-cycle proration

If you migrate mid-cycle, unused time on the legacy plan is credited toward the new tier for the rest of the period. The next full invoice uses the new tier price.

## Downgrade or roll back

- You can move to a lower current-tier plan after migration.
- Rolling back to a legacy plan is not available after the legacy plan is closed for your account. Contact your account manager if you need an exception.

## FAQ

**Will our data be affected?**  
No. Migration changes billing and plan limits only.

**Why do we still see old pricing?**  
Accounts on a legacy plan keep that pricing until migration is confirmed. After migration, refresh the Billing page or sign out and back in.

**Who must approve enterprise migrations?**  
Enterprise moves usually require a billing admin plus confirmation from your account team.
""",
    "two_factor_auth": """# Set up and manage two-factor authentication

Two-factor authentication (2FA) adds a second step at sign-in so a password alone is not enough to access an account.

## Turn on 2FA for your account

1. Go to **Settings → Security → Two-factor authentication**.
2. Choose **Authenticator app** (recommended) or **SMS**.
3. Scan the QR code with Google Authenticator, 1Password, or a similar app.
4. Enter the 6-digit code to confirm.
5. Save the backup codes in a secure place.

## Require 2FA for the workspace

Workspace admins can require 2FA for everyone:

1. Open **Settings → Security → Policies**.
2. Enable **Require two-factor authentication**.
3. Choose whether the rule applies to admins only or to all members.
4. Save. Users without 2FA are prompted at next sign-in.

## Recover access if you lose your device

1. Use a backup code on the sign-in screen.
2. If backup codes are unavailable, ask another workspace admin to temporarily disable 2FA for your user under **Settings → People → [user] → Security**.
3. Sign in, then set up 2FA again on a new device.

## 2FA and SSO

If your workspace uses SSO, authentication is handled by your identity provider. Workspace-level 2FA applies to password-based logins; SSO users follow your IdP MFA policy.

## FAQ

**Can I use SMS instead of an authenticator app?**  
Yes, if SMS 2FA is enabled for your workspace. Authenticator apps are preferred because they work offline.

**Why are my backup codes rejected?**  
Each backup code can be used once. Generate a new set from **Settings → Security → Two-factor authentication** after you regain access.

**Can one admin temporarily disable 2FA for another user?**  
Yes, if they have admin permission. Re-enable 2FA as soon as the user recovers access.
""",
    "rate_limit_errors": """# Understand and handle API rate limits

The API returns **HTTP 429** when a client sends more requests than allowed in the current window.

## Default limits

| Scope | Limit | Window |
| --- | --- | --- |
| Standard workspace | 60 requests | per minute |
| Enterprise workspace | 300 requests | per minute |

Exact limits for your account appear in **Settings → Developer → API usage**. Some endpoints may have lower ceilings; check the response headers below.

## Response headers

| Header | Meaning |
| --- | --- |
| `X-RateLimit-Limit` | Maximum requests in the current window |
| `X-RateLimit-Remaining` | Requests left in the window |
| `X-RateLimit-Reset` | Unix timestamp when the window resets |

## Recommended client behavior

1. Read `X-RateLimit-Remaining` after each response.
2. When you receive a 429, wait until `X-RateLimit-Reset` (or use exponential backoff starting at 1–2 seconds).
3. Retry the request at most a few times.
4. For bulk sync jobs, add pacing so average traffic stays under the limit.

## Bulk sync and nightly jobs

Spread large syncs across the window instead of sending bursts. If you consistently need higher throughput, request a limit increase from your account team and include typical peak requests per minute.

## FAQ

**Why do we see occasional 429s under normal load?**  
Shared clients, retries, and concurrent jobs can consume the window faster than expected. Inspect `X-RateLimit-Remaining` in logs around the failures.

**Do different endpoints share one limit?**  
Most endpoints share the workspace limit. A few high-cost endpoints publish a separate limit in their API reference.

**How do we request a higher limit?**  
Contact support or your account manager with your workspace ID and expected peak traffic.
""",
    "webhook_retry_config": """# Configure and troubleshoot webhook retries

When your endpoint does not return a successful response, the platform retries delivery automatically.

## Default retry behavior

- Retries happen after temporary failures such as timeouts and `5xx` responses.
- The backoff schedule is approximately 1 minute, 5 minutes, 30 minutes, then a few longer attempts.
- After the final attempt, the delivery is marked **failed** and retries stop.

## What is retried

| Outcome | Retried? |
| --- | --- |
| Timeout / connection error | Yes |
| HTTP 5xx | Yes |
| HTTP 429 from your endpoint | Yes |
| HTTP 2xx | No (success) |
| HTTP 4xx (except 429) | No (treated as a permanent rejection) |

Signature verification failures on your side usually look like a `4xx` response, so they are not retried the same way as timeouts.

## Reduce duplicate processing

Retries can deliver the same event more than once. Make handlers idempotent:

- Use the event ID in the payload to ignore duplicates.
- Avoid creating a new record for every delivery of the same event.

## Inspect failed deliveries

1. Open **Settings → Integrations → Webhooks**.
2. Select the endpoint.
3. Open **Delivery history** to see attempts, response codes, and timestamps.
4. Use **Redeliver** for a single event after you fix the endpoint.

## Disable retries for one endpoint

Automatic retries cannot be turned off per endpoint in the UI today. If you need a fire-and-forget endpoint, acknowledge with `2xx` quickly and process asynchronously, or contact support about webhook configuration options.

## FAQ

**Why did retries stop after our outage?**  
The retry budget was exhausted. Fix the endpoint, then redeliver failed events from Delivery history.

**Can we change the number of retry attempts?**  
Not from the standard UI. Enterprise accounts can ask about custom retry policies.
""",
}


def main() -> None:
    themes = {theme["theme_id"]: theme for theme in kg.analyze()}
    for theme_id, content in ARTICLES.items():
        theme = themes[theme_id]
        rs.save_article_draft(
            theme_id,
            theme,
            {"content": content.strip() + "\n", "model": "curated-demo"},
        )
        rs.publish_article(theme_id, theme, content.strip() + "\n")
        print(f"published {theme_id}: {theme['label']}")


if __name__ == "__main__":
    main()
