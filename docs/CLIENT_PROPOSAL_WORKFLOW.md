# Client Proposal Workflow

Lifecycle: `submitted -> under_review -> availability_confirmed -> estimate_prepared -> sent_to_client -> client_approved/client_rejected -> converted_to_campaign`. `draft` and `expired` remain supported states.

Each line snapshots its opaque unit UUID, code, location, address, city/region, dimensions, facing, format, illumination, visible selling rate, tax, and availability. Inventory edits do not rewrite history.

Estimate creation reuses `CampaignEstimateService` and `CampaignEstimateLineService`, preserving numbering, tax logic, permissions, and public response behavior. Conversion requires tenant/client consistency, approved client state, an approved linked estimate when present, and a clean availability recheck. Campaign plus pending bookings are created in one transaction and repeated conversion is idempotent. Existing campaign code rules remain unchanged.
