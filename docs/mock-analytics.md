# Mock Analytics

Mock analytics are fake demo metrics for development, walkthroughs, and local
UI testing. They are useful before you have manually entered results. They are
not real business performance.

Every generated mock snapshot is stored with:

```text
source = mock
rawMetrics.demo = true
rawMetrics.realPlatformAnalytics = false
```

## Generate Mock Analytics

In the local app:

1. Open **Analytics**.
2. Select **Generate mock analytics**.
3. Review the success message.
4. Use the Source filter to compare or hide mock/demo data.

From the command line:

```text
python -m scripts.services.analytics --database data/app.sqlite --generate-mock
```

Mock generation is deterministic and avoids duplicate snapshots for the same
post and date.

## When To Use It

Use mock analytics when:

- demonstrating the dashboard;
- testing filters, breakdowns, weekly reports, or AI memory locally;
- verifying the app without platform API credentials.

Do not use mock analytics to make business decisions. Replace the demo signal
with manually verified entries over time.

## Hide Or Remove Mock Data

To ignore mock data in the app, choose **Manual entry** in the Analytics Source
filter. Weekly reports can also be generated with a manual source filter.

Mock rows stay local. There is no delete button in the current MVP because
local audit history is preserved by default. To start a completely clean demo,
initialize and seed a separate SQLite database file.

## Safety

- No real analytics API is called.
- No social account is required.
- No API key is required.
- Mock data is visibly labeled fake/demo.
- Mock analytics do not publish posts or send replies.
