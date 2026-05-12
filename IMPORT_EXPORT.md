# OMMS Import / Export

## Import Flow

Inventory site import now follows a review-first workflow:

1. Upload CSV.
2. OMMS creates an `ImportExportJob`.
3. Preview validates rows and stores errors, warnings, duplicate candidates, and preview rows.
4. User reviews the preview.
5. User confirms the import.
6. OMMS creates records only for valid rows.

Invalid rows never create records.

## Inventory Site CSV Columns

Required:

- `code`
- `name`
- `site_type`
- `address`
- `city`
- `state`

Optional:

- `latitude`
- `longitude`

Coordinates can be left blank and captured later during first verified POE.

## Export Flow

CSV exports are supported through `ImportExportJob` for:

- inventory sites
- campaigns
- invoices
- POE reports
- client statements

Export jobs track creator, company, type, filters, status, output file, rows, and errors.
