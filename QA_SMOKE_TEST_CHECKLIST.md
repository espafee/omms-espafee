# OMMS End-to-End Smoke Test Checklist

Use this checklist after every production deployment or major workflow change.

## 1. Login
- Open the hosted web app.
- Sign in with an admin or finance user.
- Expected: user lands on Dashboard and sidebar navigation is visible.

## 2. Setup
- Open Setup.
- Confirm company name, GSTIN, bank details, invoice prefix, and branding.
- Expected: saved setup data appears consistently in invoice PDF header, supplier card, bank details, and signature.

## 3. Inventory Site Creation
- Open Inventory.
- Create a site with name, code, type, address, city, and state only.
- Leave latitude and longitude blank.
- Expected: site is created with location status `unverified`.
- Expected: UI explains coordinates will be captured during first verified POE.

## 4. Campaign Creation
- Open Campaigns.
- Create a campaign for a client with start/end dates and budget.
- Expected: campaign appears in campaign list and dashboard counts update.

## 5. Booking
- Open Bookings.
- Book one or more media units for the campaign.
- Confirm the booking.
- Expected: booked unit appears as confirmed and becomes invoice-eligible after campaign start date.

## 6. Estimate Approval
- Open Billing.
- Create a Campaign Estimate for the client and campaign.
- Add one or more proposed media lines with dates, rate, quantity, and tax.
- Click Save & Share Estimate.
- Copy/open the public estimate link in a logged-out browser.
- Approve or reject the estimate.
- Expected: public page works without login and exposes only client-safe estimate data.
- Expected: internal estimate status changes to approved or rejected.

## 7. Invoice Generation
- Open Billing.
- Select a running or completed campaign with confirmed bookings.
- Preview invoice, then generate invoice.
- Expected: invoice appears in the invoice roster as draft.
- Click Issue & Download PDF or issue then download.
- Expected: invoice issues successfully and PDF downloads.

## 8. Payment Recording
- In Billing invoice roster, click Record Payment.
- Enter a partial amount less than balance due with payment date, mode, reference, and notes.
- Expected: invoice status becomes partially paid and payment history shows the record.
- Record remaining balance.
- Expected: invoice status becomes paid and balance due becomes zero.
- Try overpayment.
- Expected: overpayment is blocked with a clear error.

## 9. PDF Download
- Download the same invoice PDF.
- Expected: PDF uses configured company profile data, correct GST, bank details, grand total, and footer.
- Expected: normal 1-2 line invoice fits cleanly on one A4 page.

## 10. POE Upload
- Open mobile app as assigned field staff.
- Select assigned work and capture POE photo.
- Expected: GPS and timestamp attach automatically.
- If site has no verified coordinates, first POE stores provisional coordinates.
- After verification, expected: site coordinates lock as first verified POE location.

## 11. POE Review
- Open web POE page as admin/operations.
- Filter by campaign, site, status, suspicious only, and date range.
- Review GPS confidence and distance from site.
- Use quick approve/reject when operationally safe.
- Expected: status changes and suspicious POE notification event is logged.

## 12. Issue Reporting
- Open a public issue link in a logged-out browser.
- Submit an issue with description and optional image.
- Expected: issue is created without requiring login and limited public data is exposed.
- Expected: client-reported issue receives priority/SLA metadata.

## 13. Public Links
- Test campaign public link, estimate public link, and issue report link in an incognito/logged-out state.
- Expected: stale local JWT or no JWT does not break public flows.

## 14. Finance Dashboard
- Open Dashboard.
- Expected: finance widgets show total outstanding, due soon invoices, overdue invoices, payments this month, and draft invoice count.
- Click overdue, due soon, outstanding/unpaid, payments this month, and draft invoice widgets.
- Expected: Billing opens with the matching invoice/payment drill-down filter.

## 15. Invoice Detail And Audit
- Open Billing.
- Click `View Details` on an invoice.
- Expected: invoice detail page shows metadata, line items, payment history, credit/refund history, and audit trail.
- Use audit event type and search filters.
- Expected: audit history filters without losing the invoice context.

## 16. Paid Invoice Void / Credit Note
- Record a partial payment against an issued invoice.
- Open invoice detail and attempt to void it.
- Enter void reason plus credit/refund amount, date, method, reference, and notes.
- Expected: invoice status becomes cancelled/void.
- Expected: original payment remains visible.
- Expected: credit/refund record and audit event appear.

## 17. Client Statement Export
- Open Billing client statement section.
- Select a client and load statement.
- Click `Export CSV` and `Export PDF`.
- Expected: CSV downloads with invoice/payment/balance rows.
- Expected: PDF downloads with a clean client statement summary.

## 18. POE Review SLA
- Open POE as admin/operations.
- Review pending POE rows.
- Expected: review SLA badge shows on track, overdue, or reviewed.
- Quick approve/reject with reviewer comment.
- Expected: reviewer comment and reviewed status are visible after refresh.

## 19. Issue Escalation
- Create a high-priority or client/public issue.
- Expected: high-priority issue is escalated and notification event is logged.
- Manually escalate an issue as admin/operations with a reason.
- Expected: issue escalation fields and issue audit event are updated.

## 20. Playwright Smoke
- From `frontend`, run `npx playwright test`.
- Expected: smoke tests pass for public route responses, protected route shell responses, and invoice detail deep-link response.
- Optional: set `PLAYWRIGHT_BASE_URL=https://omms.vercel.app` to run against hosted frontend instead of local dev server.
- Playwright specs must remain under `frontend/e2e/smoke`; do not create repo-root `tests/` folders for frontend tests.
- Backend discovery is documented in `TESTING.md` and defaults to the backend `apps` package.
