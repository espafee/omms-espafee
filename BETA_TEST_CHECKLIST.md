# OMMS Beta Test Checklist

Use this checklist for a focused beta round against the current OMMS build.

## Before You Start

- Confirm backend is running and reachable.
- Confirm frontend is running and reachable.
- Confirm database migrations are applied.
- Confirm at least one admin user exists.
- Confirm test data exists for sites, media units, campaigns, and users where required.
- Confirm media uploads write to a real writable storage location.

## Test Accounts

- `Admin`: full access, including share-link management and client creation.
- `Operations`: inventory and POE write access.
- `Sales`: campaign and booking write access.
- `Client`: read-only scoped access plus public share-link access.

## 1. Login

- Open `/login`.
- Sign in with a valid user.
- Confirm redirect to `/dashboard`.
- Confirm invalid password shows a clear validation message.
- Confirm expired or invalid session redirects cleanly after logout or token expiry.

Expected result:
- Login succeeds for valid credentials.
- Invalid credentials do not crash the page and show a readable error.

## 2. Inventory Site Add/Delete

- Sign in as admin.
- Open `/inventory`.
- Create a new site with valid required fields.
- Confirm success state appears.
- Confirm new site appears in the list without a manual refresh if the UI supports it, or after a standard page refresh if not.
- Delete a site that has no active bookings.
- Confirm delete succeeds.
- Try deleting a site linked to active bookings.

Expected result:
- Admin can create and delete allowed sites.
- Protected delete shows a clear error and does not remove the site.

## 3. Site Image Upload

- On inventory, upload one or more site images.
- Confirm thumbnail appears.
- Mark one image as primary if that action is available.
- Delete an uploaded image after confirmation.

Expected result:
- Upload succeeds.
- Primary image updates correctly.
- Delete requires confirmation.
- Bad upload or permission failure shows a readable message.

## 4. Media Unit Create/Edit

- Create a media unit under an existing site.
- Fill `Facing Direction`.
- Fill `Site Type`.
- Save the unit.
- Edit the unit and update direction or type.

Expected result:
- Unit appears with direction and type shown safely.
- Empty optional fields do not break layout.

## 5. Campaign Create

- Sign in as sales or admin.
- Open `/campaigns`.
- Create a campaign with valid client and manager selections.
- Confirm success message.
- Confirm the new campaign appears in the roster.

Expected result:
- Campaign create works without page-level errors.

## 6. Client Create

- From the campaign page, use the Add Client form as admin.
- Create a new client with unique email and username.
- Confirm the client appears in the campaign client dropdown immediately.
- Try reusing the same email or username.

Expected result:
- New client is selectable right away.
- Duplicate data shows field-level validation errors.

## 7. Booking Create

- Sign in as sales or admin.
- Open `/bookings`.
- Create a booking with valid campaign, site, media unit, and dates.
- Confirm success state and refreshed booking list.

Expected result:
- Booking is created successfully.
- Selected site and media unit context is shown clearly.

## 8. Booking Conflict Handling

- Try creating a second booking for the same media unit over the same date range.

Expected result:
- Booking is rejected with a user-friendly conflict/availability message.
- Existing booking remains unchanged.

## 9. POE Create

- Sign in as operations or admin.
- Open `/poe` or the field capture flow.
- Create a POE record for a valid booking.
- Attach image evidence if the flow supports it.

Expected result:
- POE record is saved successfully.
- Uploaded evidence appears in the POE list or detail view.

## 10. POE Verify

- Trigger POE verification on a valid record.
- Test a normal case and, if available, a suspicious/misaligned GPS case.

Expected result:
- Verification status, score, and notes are shown clearly.
- Verification does not expose raw server errors.

## 11. Share Link Generate/Copy/Revoke

- Sign in as admin.
- Open `/campaigns`.
- Select a campaign with share-link controls.
- Generate a share link.
- Copy the link.
- Refresh the page.
- Confirm the same active link is still visible.
- Revoke the link after confirmation.

Expected result:
- Active link persists after refresh.
- Copy works repeatedly.
- Revoke changes the visible status and disables public access.

## 12. Public Client Campaign Page

- Open the public campaign link in a logged-out browser tab.
- Review campaign name, duration, status, booking summary, and POE gallery.
- Test an invalid, expired, or revoked link if available.

Expected result:
- Valid link loads a polished read-only page.
- Invalid or expired links show a clean state message, not a crash or raw server error.

## Regression Notes

Watch for these specific failure types during beta:

- Generic page-level red banners for optional API failures.
- Blank/white pages caused by stale Next.js build output.
- Missing image arrays or nested fields crashing inventory or public campaign pages.
- Admin-only actions becoming visible to sales, operations, or client users.
- Upload endpoints failing because media storage is not writable or not served correctly.

## Sign-Off

- `Pass`: all critical flows succeed and no blockers remain.
- `Conditional pass`: only non-critical UI polish issues remain.
- `Blocker`: any auth, booking conflict, upload, public share-link, or POE verification flow fails.
