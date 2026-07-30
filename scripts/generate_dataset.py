"""Deterministically generate the synthetic tickets and KB articles for the Knowledge Gap Agent.

Run: python scripts/generate_dataset.py
Writes: data/tickets.json, data/kb_articles.json

The dataset is designed so that, after embedding-based clustering, several
recurring documentation themes should be classified as:
  - "good"    coverage (a detailed, matching KB article exists)
  - "weak"    coverage (an article exists but is generic/outdated)
  - "missing" coverage (no relevant article exists)

A separate set of "bug" tickets is included to verify the agent correctly
excludes product defects from documentation-gap analysis, even when they
recur frequently.

The `topic` field on each ticket is metadata for dataset design and test
evaluation only. It is never passed to the embedding model; clustering must
work from ticket subject/body text alone.

Tickets also carry the fields the validation pipeline needs and that cannot be
derived from text: `customer_id` (unique-customer thresholds),
`product_version` (contradiction detection against a versioned article), and
self-service search outcome (`searched`, `search_top_article`) so a real
documentation gap can be told apart from content that exists but is never
retrieved.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

START_DATE = datetime(2026, 4, 1)
# IDs use a stable range so links remain deterministic across regenerated data.
ID_START = 30001


def _dates(n: int, spread_days: int = 120) -> list[str]:
    # Spread evidence over time to model a persistent documentation gap.
    step = max(spread_days // max(n, 1), 8)
    return [
        (START_DATE + timedelta(days=i * step, hours=(i * 7) % 24)).isoformat() + "Z"
        for i in range(n)
    ]


def _ticket_id(counter: int) -> str:
    return f"T-{ID_START + counter - 1:05d}"


# Synthetic account identifiers. Ticket volume alone cannot tell one noisy
# customer apart from a recurring problem across the base, so the validation
# pipeline counts unique accounts.
ACCOUNTS = [f"ACCT-{1000 + i}" for i in range(1, 25)]

DEFAULT_VERSION = "4.1"


def _accounts_for(topic_index: int, count: int = 4) -> list[str]:
    start = (topic_index * 3) % len(ACCOUNTS)
    return [ACCOUNTS[(start + i) % len(ACCOUNTS)] for i in range(count)]


# Each topic entry drives generation of N tickets that share a real customer
# problem, phrased in varied ways (not copy-pasted) so clustering must rely on
# semantic similarity rather than exact string matches.
DOC_TOPICS = [
    {
        "topic": "api_key_reset",
        "product_area": "platform",
        "intended_coverage": "good",
        # A complete article exists, but self-service search returns nothing for
        # how customers phrase it. This is a findability problem, not a gap.
        "search": {"searched": True, "top": None},
        "variants": [
            ("Can't find where to reset my API key", "I need to rotate our API key after an employee left but I can't find the setting anywhere in the dashboard."),
            ("How do I regenerate an API key?", "Our current API key may have been exposed. What are the steps to generate a new one without breaking our integration?"),
            ("API key reset instructions needed", "Please send me the exact steps to reset the API key for our production workspace."),
            ("Rotating API keys for security audit", "Our security team requires us to rotate all API keys quarterly. How do I do this from the account settings?"),
            ("Where is the API key management page?", "I used to be able to see our API key under settings but I can't locate it after the redesign."),
            ("Need a new API key, old one compromised", "We think our API key leaked in a public repo. How fast can we get a replacement key issued?"),
            ("Generate additional API key for staging", "We want a second API key scoped to our staging environment. How is that configured?"),
            ("API key expired, need to reissue", "Our integration stopped working and support said the API key expired. How do I reissue it?"),
            ("Steps to revoke and recreate API key", "Can you walk me through revoking our current API key and creating a replacement?"),
            ("API key rotation for CI pipeline", "We rotate secrets automatically. Is there a documented process for rotating the API key without downtime?"),
            ("Lost access to API key value", "I never copied the API key when it was created and now I can't view it again. What are my options?"),
            ("New team member needs API key access", "A new engineer joined and needs their own API key. How do we provision one?"),
            ("API key reset after account transfer", "We transferred ownership of the workspace. Do we need to reset the API key as part of that?"),
            ("How to reset the API key safely", "What is the recommended way to reset an API key so our production integration is not interrupted?"),
        ],
    },
    {
        "topic": "sso_setup",
        "product_area": "security",
        "intended_coverage": "good",
        "search": {"searched": True, "top": "KB-002"},
        "variants": [
            ("Configuring SSO with Okta", "We use Okta company-wide and want all logins to go through SSO. How do we set that up?"),
            ("Azure AD single sign-on setup", "Our IT team wants to enforce Azure AD SSO for this tool. What configuration is required on our side?"),
            ("Enforcing SSO for all users", "Can we require every user in our workspace to log in only through SSO once it's configured?"),
            ("SAML configuration for identity provider", "We need the SAML metadata and ACS URL to configure our identity provider for SSO."),
            ("SSO login redirect not working", "After setting up SSO, users are redirected to an error page. What are the correct setup steps?"),
            ("How to enable SSO for enterprise plan", "Is SSO available on our plan, and how do we turn it on for our organization?"),
            ("SSO setup with Google Workspace", "We'd like to use Google Workspace as our identity provider for single sign-on. Is that supported?"),
            ("Mapping SSO groups to roles", "Once SSO is configured, how do we map identity provider groups to roles in the app?"),
            ("SSO certificate renewal steps", "Our SAML certificate is expiring soon. What is the process to update it without breaking logins?"),
            ("Testing SSO before full rollout", "Is there a way to test SSO configuration with one test user before enabling it company-wide?"),
            ("SSO setup documentation request", "Does the vendor provide setup instructions for SSO configuration with a generic SAML provider?"),
            ("Multiple identity providers for SSO", "Can we configure SSO with two different identity providers for two subsidiaries?"),
        ],
    },
    {
        "topic": "timezone_settings",
        "product_area": "platform",
        "intended_coverage": "good",
        # Search keeps returning the scheduled-reports article instead of the
        # timezone article, so retrieval ranks the wrong content.
        "search": {"searched": True, "top": "KB-015"},
        "variants": [
            ("Change workspace default timezone", "All our reports show times in UTC, but our team is in EST. How do we change the default timezone?"),
            ("Timezone setting affecting scheduled reports", "Our scheduled reports arrive at the wrong local time. Where do we set the workspace timezone?"),
            ("How to set timezone for new workspace", "When creating a new workspace, what determines the default timezone and can we change it later?"),
            ("Timestamps look off by several hours", "The timestamps on tickets look off by five hours compared to our local time. How do we fix this?"),
            ("Per-user timezone vs workspace timezone", "Can individual users set their own timezone, or is it only a workspace-wide setting?"),
            ("Daylight saving time not applied correctly", "Our reports didn't shift for daylight saving time this year. Is the timezone setting supposed to handle that automatically?"),
            ("Update timezone after office relocation", "We moved offices to a new timezone. How do we update the workspace-level timezone setting?"),
            ("Timezone setting for multi-region team", "Our team is spread across three timezones. How does the workspace timezone setting handle that?"),
            ("Where is the timezone configuration option", "I looked through account settings but couldn't find where to change the timezone."),
        ],
    },
    {
        "topic": "csv_export",
        "product_area": "reporting",
        "intended_coverage": "weak",
        "search": {"searched": True, "top": "KB-004"},
        "variants": [
            ("How do I export data as CSV?", "I need to download our ticket data as a CSV file for a board presentation. Is that possible?"),
            ("CSV export missing some columns", "When I export to CSV, several columns from the dashboard view are missing. Is that expected?"),
            ("Export to CSV for finance team", "Finance needs a CSV export of billing data every month. What's the process?"),
            ("Bulk CSV export of all tickets", "Can we export our entire ticket history as one CSV file instead of paginated exports?"),
            ("CSV export button not visible", "I don't see a CSV export option on the reports page, only PDF. Am I missing something?"),
            ("Scheduled CSV export to email", "Is it possible to schedule a recurring CSV export that gets emailed automatically?"),
            ("CSV export character encoding issue", "Our exported CSV file shows broken characters for names with accents. How do we fix the encoding?"),
            ("Export filtered view as CSV", "I filtered the table by status and want to export just that filtered view to CSV."),
            ("Difference between CSV and Excel export", "Is there a difference in data completeness between the CSV and Excel export options?"),
            ("Automating CSV export via API", "Can we pull the same CSV export data through the API instead of the UI?"),
        ],
    },
    {
        "topic": "two_factor_auth",
        "product_area": "security",
        "intended_coverage": "weak",
        "search": {"searched": True, "top": "KB-005"},
        "variants": [
            ("How do I turn on two-factor authentication?", "We want to require 2FA for all admin accounts. Where do we enable that?"),
            ("2FA setup with authenticator app", "Can we use Google Authenticator for two-factor authentication, or only SMS codes?"),
            ("Lost my 2FA device, locked out", "I lost my phone with my authenticator app and can't log in. How do I recover access?"),
            ("Enforcing 2FA for entire organization", "Is there a setting to force two-factor authentication for every member of our workspace?"),
            ("2FA backup codes not working", "The backup codes I saved for two-factor authentication aren't being accepted. What should I do?"),
            ("Disabling 2FA for a single user", "One of our admins wants to temporarily disable two-factor authentication. Is that possible?"),
            ("Two-factor authentication and SSO together", "If we enable SSO, do we still need to configure two-factor authentication separately?"),
            ("2FA recovery process for admins", "What is the recovery process when an admin is locked out of two-factor authentication?"),
            ("Setting up 2FA via SMS", "How do we configure SMS-based two-factor authentication for users without a smartphone?"),
        ],
    },
    {
        "topic": "rate_limit_errors",
        "product_area": "platform",
        "intended_coverage": "weak",
        "search": {"searched": True, "top": "KB-006"},
        "variants": [
            ("Getting 429 errors from the API", "Our integration suddenly started returning 429 errors. What are the current rate limits?"),
            ("What is our API rate limit?", "We're scaling up our integration and need to know the exact request-per-minute rate limit."),
            ("Rate limit errors during bulk sync", "Our nightly bulk sync job hits rate limit errors. How should we handle backoff and retries?"),
            ("Increase API rate limit for our account", "Can we request a higher rate limit for our enterprise account?"),
            ("Rate limit headers not documented", "The API responses include rate limit headers, but I can't find what each one means."),
            ("Intermittent 429 responses under normal load", "We're not sending many requests, but we still get occasional 429 responses. Why?"),
            ("Rate limit reset time unclear", "How do we know when the rate limit window resets so we can retry safely?"),
            ("Different rate limits per endpoint", "Do different API endpoints have different rate limits, or is it a single global limit?"),
        ],
    },
    {
        "topic": "billing_plan_migration",
        "product_area": "billing",
        "intended_coverage": "missing",
        "search": {"searched": True, "top": None},
        "variants": [
            ("How do I move from legacy plan to new pricing?", "We're on an old legacy plan and want to switch to the new pricing tiers. What does that process look like?"),
            ("Will migrating plans affect our current data?", "If we migrate from the legacy plan to a new tier, will any of our existing data or settings be affected?"),
            ("New pricing tiers not showing for our account", "Our account still shows old pricing. How do we get moved onto the new plan structure?"),
            ("Cost comparison legacy vs new plan", "Can someone walk us through how our costs would change if we migrate to the new pricing tiers?"),
            ("Downgrading during plan migration", "We want to migrate to the new pricing but end up on a lower tier than before. Is that supported?"),
            ("Timeline for forced migration off legacy plan", "We heard legacy plans are being sunset. What is the timeline and process for migrating?"),
            ("Migrating multiple workspaces to new tiers", "We manage five workspaces on the legacy plan. Can they all be migrated to new tiers at once?"),
            ("Grandfathered features lost after migration", "Will we lose any grandfathered features if we migrate from our legacy plan to a new tier?"),
            ("Who approves plan migration for enterprise", "What is the internal approval process for migrating an enterprise account to new pricing tiers?"),
            ("Plan migration billing proration", "If we migrate mid-cycle, how is the billing prorated between the legacy and new plan?"),
            ("Rolling back after plan migration", "Is it possible to roll back to our legacy plan if the new pricing tier doesn't work out for us?"),
        ],
    },
    {
        "topic": "webhook_retry_config",
        "product_area": "platform",
        "intended_coverage": "weak",
        "search": {"searched": True, "top": "KB-012"},
        # These customers are on 4.2, where retries are no longer automatic.
        # KB-012 still documents the 4.1 behavior, so the evidence contradicts
        # the published article.
        "product_version": "4.2",
        "variants": [
            ("How does webhook retry behavior work?", "When our endpoint is briefly down, does the platform automatically retry sending the webhook?"),
            ("Configuring webhook retry attempts", "Can we configure how many times a failed webhook delivery is retried?"),
            ("Webhook retries causing duplicate events", "We're seeing duplicate events on our side. Is that from webhook retry behavior?"),
            ("Webhook retry backoff schedule", "What is the backoff schedule between webhook retry attempts after a failure?"),
            ("Disabling webhook retries for one endpoint", "Can we disable automatic retries for a specific webhook endpoint?"),
            ("Webhook delivery failed permanently, no retry", "Our endpoint was down for an hour and now webhook deliveries seem to have stopped retrying. Is there a retry limit?"),
            ("How to inspect failed webhook retry attempts", "Is there a log or dashboard showing failed webhook deliveries and retry history?"),
            ("Webhook retry after signature verification failure", "If our endpoint rejects a webhook due to signature mismatch, is it retried the same way as a timeout?"),
            ("Retries no longer automatic after 4.2 upgrade", "Since we upgraded to 4.2, automatic webhook retries stopped and we now have to re-enable retries manually for every endpoint."),
            ("Do we have to re-enable retries manually now?", "The documentation says retries are automatic, but on our version we must turn retries back on manually after each failure. Which is correct?"),
        ],
    },
    {
        "topic": "bulk_user_import",
        "product_area": "admin",
        "intended_coverage": "missing",
        "search": {"searched": True, "top": None},
        "variants": [
            ("How do I bulk import users via CSV?", "We have 200 employees to add. Is there a way to bulk import users instead of adding them one by one?"),
            ("Bulk user import failing silently", "We tried uploading a CSV of users and nothing happened, no error and no new users."),
            ("Required CSV format for user import", "What columns and format does the bulk user import CSV need to have?"),
            ("Assigning roles during bulk import", "Can we set each user's role as part of the bulk import file, or do we assign roles afterward?"),
            ("Bulk import users from another tool", "We're migrating from another platform. Can we bulk import users along with their existing roles?"),
            ("Partial failures during bulk user import", "Some rows failed during bulk import but we don't know which ones or why."),
            ("Bulk deactivating users via import", "Is there a bulk import option to deactivate a large list of users at once?"),
            ("Bulk import limit on number of users", "Is there a maximum number of users we can include in a single bulk import file?"),
            ("Re-running a bulk import after fixing errors", "After fixing a few rows, can we re-run the same bulk import file without duplicating existing users?"),
            ("Bulk import users with SSO enabled", "Does bulk user import work the same way once SSO is enabled for the workspace?"),
            ("Mapping departments during bulk import", "Can department or team assignment be included in the bulk user import file?"),
            ("Bulk import audit trail", "Is there an audit log showing who ran a bulk user import and what changed?"),
            ("CSV template for bulk user import", "Is there a downloadable template for the bulk user import CSV format?"),
        ],
    },
]

# Recurring product defects. These must never surface in the knowledge-gap
# ranking, even though they occur frequently, because they are bugs and not
# documentation questions.
BUG_TOPICS = [
    {
        "topic": "dashboard_charts_not_loading",
        "product_area": "reporting",
        "variants": [
            ("Dashboard charts stuck on loading spinner", "The revenue chart on our dashboard has been stuck loading for the past hour."),
            ("Charts show no data after refresh", "All charts on the main dashboard show blank after I refresh the page."),
            ("Dashboard widgets fail to render", "Several widgets on our dashboard fail to render and show a generic error icon."),
            ("Chart loading error on Safari", "Our team on Safari sees a permanent loading spinner on all dashboard charts; Chrome works fine."),
            ("Dashboard crashes when filtering by date range", "Selecting a custom date range on the dashboard causes the whole page to crash."),
            ("Charts intermittently blank on load", "About half the time, opening the dashboard shows blank charts until a manual refresh."),
            ("Dashboard performance degraded this week", "Dashboard charts are taking 30+ seconds to load since yesterday, previously instant."),
            ("Chart tooltips showing wrong values", "Hovering over the dashboard chart shows numbers that don't match the summary totals."),
            ("Dashboard error: failed to fetch chart data", "We get a 'failed to fetch chart data' error banner on the dashboard several times a day."),
            ("Charts not updating after new data arrives", "New tickets aren't reflected in the dashboard charts until much later than expected."),
            ("Dashboard chart legend overlapping labels", "The legend on the dashboard bar chart overlaps the axis labels, making it unreadable."),
            ("Dashboard blank for one specific workspace", "Every other workspace loads fine, but one of our workspaces shows a completely blank dashboard."),
        ],
    },
    {
        "topic": "mobile_app_crash_login",
        "product_area": "mobile",
        "variants": [
            ("Mobile app crashes immediately after login", "Every time I log in on the iOS app, it crashes within two seconds."),
            ("Android app force closes on startup", "The Android app force closes right after the splash screen since the latest update."),
            ("App crash after entering SSO credentials", "The mobile app crashes right after I complete the SSO login flow."),
            ("Mobile login loop, never reaches home screen", "The app keeps returning to the login screen in a loop and never loads the dashboard."),
            ("iOS app crash on biometric login", "Using Face ID to log in on iOS causes an immediate crash."),
            ("Mobile app white screen after login", "After logging in on Android, the screen goes completely white and the app becomes unresponsive."),
            ("App crashes only for users with 2FA enabled", "Users with two-factor authentication enabled report the mobile app crashing after entering the code."),
            ("Mobile crash report attached, login screen", "Attaching a crash log; it happens consistently right after tapping the login button."),
            ("App unusable since update, crashes on launch", "Since updating the app yesterday, it crashes on launch before we even reach the login screen."),
        ],
    },
]

# A handful of one-off, unrelated documentation questions. Each appears only
# once or twice, below the minimum cluster size, and should be excluded from
# the ranked results as insufficient evidence (not enough tickets to justify
# a content recommendation).
NOISE_DOC_TICKETS = [
    ("Can I change my account email address?", "I need to update the email address associated with my account.", "account"),
    ("How do I cancel my subscription?", "We'd like to cancel our subscription at the end of the current billing cycle.", "billing"),
    ("Is there a dark mode option?", "Would like to know if a dark mode theme is available or planned.", "platform"),
    ("Can I invite an external contractor as a guest?", "We have a contractor who needs limited guest access. Is that supported?", "admin"),
    ("Does the API support GraphQL?", "We prefer GraphQL over REST. Is there a GraphQL endpoint available?", "platform"),
]


def _build_doc_tickets() -> list[dict]:
    tickets = []
    counter = 1
    for topic_index, topic in enumerate(DOC_TOPICS):
        dates = _dates(len(topic["variants"]))
        accounts = _accounts_for(topic_index)
        search = topic["search"]
        for position, ((subject, body), created_at) in enumerate(
            zip(topic["variants"], dates, strict=True)
        ):
            tickets.append(
                {
                    "id": _ticket_id(counter),
                    "subject": subject,
                    "body": body,
                    "created_at": created_at,
                    "product_area": topic["product_area"],
                    "ticket_type": "question",
                    "topic": topic["topic"],
                    "customer_id": accounts[position % len(accounts)],
                    "product_version": topic.get("product_version", DEFAULT_VERSION),
                    "searched": search["searched"],
                    "search_top_article": search["top"],
                }
            )
            counter += 1
    return tickets, counter


def _build_bug_tickets(counter: int) -> tuple[list[dict], int]:
    tickets = []
    for topic_index, topic in enumerate(BUG_TOPICS):
        dates = _dates(len(topic["variants"]))
        accounts = _accounts_for(len(DOC_TOPICS) + topic_index)
        for position, ((subject, body), created_at) in enumerate(
            zip(topic["variants"], dates, strict=True)
        ):
            tickets.append(
                {
                    "id": _ticket_id(counter),
                    "subject": subject,
                    "body": body,
                    "created_at": created_at,
                    "product_area": topic["product_area"],
                    "ticket_type": "bug",
                    "topic": topic["topic"],
                    "customer_id": accounts[position % len(accounts)],
                    "product_version": DEFAULT_VERSION,
                    "searched": False,
                    "search_top_article": None,
                }
            )
            counter += 1
    return tickets, counter


def _build_noise_tickets(counter: int) -> tuple[list[dict], int]:
    tickets = []
    dates = _dates(len(NOISE_DOC_TICKETS))
    for position, ((subject, body, area), created_at) in enumerate(
        zip(NOISE_DOC_TICKETS, dates, strict=True)
    ):
        tickets.append(
            {
                "id": _ticket_id(counter),
                "subject": subject,
                "body": body,
                "created_at": created_at,
                "product_area": area,
                "ticket_type": "question",
                "topic": "noise",
                # One-off questions come from one account each, so they also fail
                # the unique-customer threshold, not only the volume threshold.
                "customer_id": ACCOUNTS[-(position + 1)],
                "product_version": DEFAULT_VERSION,
                "searched": False,
                "search_top_article": None,
            }
        )
        counter += 1
    return tickets, counter


KB_ARTICLES = [
    {
        "id": "KB-001",
        "title": "API Key Management Guide",
        "content": (
            "This guide covers how to view, rotate, and reset your API key from Settings > "
            "Developer > API Keys. To reset a key: open the API Keys page, click Reset next to "
            "the key you want to replace, confirm the action, and copy the new key immediately "
            "since it is only shown once."
        ),
    },
    {
        "id": "KB-002",
        "title": "Single Sign-On (SSO) Setup with Okta and Azure AD",
        "content": (
            "Step-by-step instructions for configuring SAML-based single sign-on with Okta or "
            "Azure AD, including the ACS URL, entity ID, certificate upload, group-to-role "
            "mapping, and how to test SSO with a single user before enforcing it organization-wide."
        ),
    },
    {
        "id": "KB-003",
        "title": "Changing Your Workspace Timezone",
        "content": (
            "Workspace administrators can change the default timezone from Settings > General > "
            "Timezone. This affects all timestamps, scheduled reports, and daylight saving time "
            "adjustments for every user in the workspace, unless a user overrides it individually."
        ),
    },
    {
        "id": "KB-004",
        "title": "Data Export Overview",
        "content": (
            "You can export data from most report views using the Export button in the top right "
            "corner. Exported files can be printed or saved as PDF for sharing with stakeholders."
        ),
    },
    {
        "id": "KB-005",
        "title": "Account Security Basics",
        "content": (
            "We recommend using a strong, unique password for your account. Additional security "
            "options are available under Settings > Security, including session management, "
            "login activity history, and an option to turn on two-factor authentication."
        ),
    },
    {
        "id": "KB-006",
        "title": "Understanding API Response Codes",
        "content": (
            "This article lists common HTTP response codes returned by the API, such as 200, 400, "
            "401, 404, and 500, along with general guidance for handling error responses in client code."
        ),
    },
    {
        "id": "KB-007",
        "title": "Getting Started with the Platform",
        "content": (
            "Welcome! This overview walks new users through creating a workspace, inviting "
            "teammates, and navigating the main dashboard for the first time."
        ),
    },
    {
        "id": "KB-008",
        "title": "Billing FAQ",
        "content": (
            "Answers to common billing questions, including how invoices are generated, accepted "
            "payment methods, and how to update your payment method on file."
        ),
    },
    {
        "id": "KB-009",
        "title": "Managing Team Members",
        "content": (
            "Admins can invite, remove, and edit permissions for individual team members from the "
            "People page. Each teammate is added one at a time by entering their email address."
        ),
    },
    {
        "id": "KB-010",
        "title": "Notifications and Alerts Settings",
        "content": (
            "Configure which events trigger email or in-app notifications, including new ticket "
            "assignments, mentions, and daily digest summaries."
        ),
    },
    {
        "id": "KB-011",
        "title": "Mobile App Overview",
        "content": (
            "The mobile app lets you review tickets, respond to customers, and receive push "
            "notifications on the go. Available for iOS and Android."
        ),
    },
    {
        "id": "KB-012",
        "title": "Integrations Overview",
        "content": (
            "The platform integrates with popular tools like Slack, Salesforce, and Jira. Webhooks "
            "notify external systems when events occur, such as a new ticket being created. "
            "Delivery is handled automatically and no configuration is required."
        ),
        # Written for 4.1. Customers on 4.2 report the opposite behavior, which is
        # what the contradiction validator has to catch.
        "applies_to_version": "4.1",
    },
    {
        "id": "KB-013",
        "title": "Password Reset Guide",
        "content": (
            "If you forgot your account password, click Forgot Password on the login screen and "
            "follow the emailed link to choose a new password. This does not affect your API key."
        ),
    },
    {
        "id": "KB-014",
        "title": "Two-Way Data Sync Overview",
        "content": (
            "Describes how two-way sync keeps records consistent between this platform and "
            "connected CRMs, including sync frequency and conflict resolution rules."
        ),
    },
    {
        "id": "KB-015",
        "title": "Scheduling Recurring Reports",
        "content": (
            "Reports can be scheduled to run daily, weekly, or monthly and delivered by email as a "
            "PDF attachment to a chosen list of recipients."
        ),
    },
]


def generate() -> None:
    doc_tickets, counter = _build_doc_tickets()
    bug_tickets, counter = _build_bug_tickets(counter)
    noise_tickets, counter = _build_noise_tickets(counter)
    tickets = doc_tickets + bug_tickets + noise_tickets
    articles = [
        {**article, "applies_to_version": article.get("applies_to_version", DEFAULT_VERSION)}
        for article in KB_ARTICLES
    ]

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "tickets.json").write_text(
        json.dumps(tickets, indent=2), encoding="utf-8"
    )
    (DATA_DIR / "kb_articles.json").write_text(
        json.dumps(articles, indent=2), encoding="utf-8"
    )
    print(f"Wrote {len(tickets)} tickets and {len(articles)} KB articles to {DATA_DIR}")


if __name__ == "__main__":
    generate()
