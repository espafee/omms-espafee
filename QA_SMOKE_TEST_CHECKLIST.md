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
