# Freight Invoice Validation & Audit — Comprehensive Data Dictionary

This document specifies the schema, constraints, data types, uniqueness, allowed values, units, and validation rules for all 11 core entities in the freight invoice audit and settlement domain.

---

## 1. Carrier (`carrier.csv`)
Represents the freight transportation service provider contracted to move shipments.

| Field Name | Type | Req/Opt | Allowed Values / Format | Units | Uniqueness | Validation Rule |
|---|---|---|---|---|---|---|
| `carrier_id` | String | Required | `CAR-000001` to `CAR-999999` | - | Primary Key | Must match pattern `^CAR-\d{6}$`. Unique across all carriers. |
| `carrier_name` | String | Required | Text (e.g. "Apex Freight Logistics") | - | Non-unique | Non-empty string, length 3–100 chars. |
| `scac_code` | String | Required | 2–4 uppercase letters (e.g. `APEX`, `BLUD`) | - | Unique | Standard Carrier Alpha Code (SCAC). Must be uppercase alphanumeric. |
| `contact_email` | String | Required | RFC 5322 email (e.g. `billing@apex.com`) | - | Non-unique | Valid email syntax. |
| `phone` | String | Required | `+1-XXX-XXX-XXXX` or international format | - | Non-unique | Valid telephone format. |
| `payment_terms` | Enum | Required | `NET15`, `NET30`, `NET45`, `NET60` | - | Non-unique | Must be in allowed enum values. |
| `status` | Enum | Required | `ACTIVE`, `INACTIVE`, `SUSPENDED` | - | Non-unique | Inactive or suspended carriers cannot be assigned to new shipments. |
| `created_at` | String | Required | ISO 8601 Date (`YYYY-MM-DD`) | - | Non-unique | Must be valid date <= today. |

---

## 2. Lane (`lane.csv`)
Defines a commercial transportation corridor between origin and destination hubs.

| Field Name | Type | Req/Opt | Allowed Values / Format | Units | Uniqueness | Validation Rule |
|---|---|---|---|---|---|---|
| `lane_id` | String | Required | `LANE-0001` to `LANE-9999` | - | Primary Key | Pattern `^LANE-\d{4}$`. Unique across all lanes. |
| `origin_code` | String | Required | 3-letter IATA/Hub code (e.g. `BLR`, `BOM`, `DEL`) | - | Non-unique | Uppercase 3 letters. |
| `origin_city` | String | Required | Text (e.g. "Bengaluru", "Mumbai") | - | Non-unique | Non-empty string. |
| `origin_state` | String | Required | Text / 2-letter code | - | Non-unique | Non-empty string. |
| `destination_code` | String | Required | 3-letter IATA/Hub code (e.g. `MAA`, `DEL`, `HYD`) | - | Non-unique | `destination_code != origin_code`. |
| `destination_city`| String | Required | Text (e.g. "Chennai", "Delhi") | - | Non-unique | Non-empty string. |
| `destination_state`| String | Required | Text / 2-letter code | - | Non-unique | Non-empty string. |
| `distance_km` | Decimal | Required | Positive real number (e.g. 350.00) | km | Non-unique | `distance_km > 0`. |
| `transit_days_std` | Integer | Required | Integer >= 1 | days | Non-unique | Standard service transit duration. |
| `transit_days_exp` | Integer | Required | Integer >= 1 | days | Non-unique | `transit_days_exp <= transit_days_std`. |

---

## 3. RateCard (`rate_card.csv`)
Specifies the contracted freight tariff agreed between shipper and carrier by lane, service level, and weight tier.

| Field Name | Type | Req/Opt | Allowed Values / Format | Units | Uniqueness | Validation Rule |
|---|---|---|---|---|---|---|
| `rate_id` | String | Required | `RATE-CAR-000001-2026-01-L0001-STD-T1` | - | Primary Key | Unique rate card tariff identifier. Starts with `RATE-<carrier-id>-2026-01`. |
| `carrier_id` | String | Required | `CAR-000001` to `CAR-999999` | - | Foreign Key | References `carrier.carrier_id`. Carrier must exist. |
| `lane_id` | String | Required | `LANE-0001` to `LANE-9999` | - | Foreign Key | References `lane.lane_id`. Lane must exist. |
| `service` | Enum | Required | `STANDARD`, `EXPRESS` | - | Non-unique | Must be valid service type. |
| `weight_min_kg` | Decimal | Required | Real number >= 0.00 | kg | Non-unique | Lower bound of tier (inclusive). |
| `weight_max_kg` | Decimal | Required | Real number > weight_min_kg | kg | Non-unique | Upper bound of tier (exclusive). `weight_max_kg > weight_min_kg`. |
| `base_rate` | Decimal | Required | Real number > 0.00 | USD | Non-unique | Contracted flat base rate for the tier, rounded to 2 decimals. |
| `fuel_pct` | Decimal | Required | Real number between 0.00 and 1.00 (e.g. 0.12) | ratio | Non-unique | Contracted fuel surcharge percentage. |
| `currency` | String | Required | `USD` (or ISO 4217 code) | - | Non-unique | ISO 4217 3-letter currency code. |
| `effective_from` | String | Required | ISO 8601 Date (`YYYY-MM-DD`) | - | Non-unique | Start date of contracted validity. |
| `effective_to` | String | Required | ISO 8601 Date (`YYYY-MM-DD`) | - | Non-unique | `effective_to >= effective_from`. Rate expires after this date. |
| `status` | Enum | Required | `ACTIVE`, `EXPIRED`, `SUPERSEDED` | - | Non-unique | Operational lifecycle status. |

---

## 4. Shipment (`shipment.csv`)
Operational shipment booking containing physical attributes, service tier, routing, and delivery status.

| Field Name | Type | Req/Opt | Allowed Values / Format | Units | Uniqueness | Validation Rule |
|---|---|---|---|---|---|---|
| `shipment_id` | String | Required | `SHP-2026-000001` to `SHP-2026-999999` | - | Primary Key | Pattern `^SHP-2026-\d{6}$`. Unique across all shipments. |
| `carrier_id` | String | Required | `CAR-000001` to `CAR-999999` | - | Foreign Key | References `carrier.carrier_id`. |
| `lane_id` | String | Required | `LANE-0001` to `LANE-9999` | - | Foreign Key | References `lane.lane_id`. |
| `service` | Enum | Required | `STANDARD`, `EXPRESS` | - | Non-unique | Service requested by shipper. |
| `ship_date` | String | Required | ISO 8601 Date (`YYYY-MM-DD`) | - | Non-unique | Date cargo was tendered. |
| `delivery_date` | String | Required | ISO 8601 Date (`YYYY-MM-DD`) | - | Non-unique | `delivery_date >= ship_date`. |
| `actual_weight_kg` | Decimal | Required | Real number > 0.00 | kg | Non-unique | Gross scale weight. |
| `length_cm` | Decimal | Required | Real number > 0.00 | cm | Non-unique | Outer packaging length. |
| `width_cm` | Decimal | Required | Real number > 0.00 | cm | Non-unique | Outer packaging width. |
| `height_cm` | Decimal | Required | Real number > 0.00 | cm | Non-unique | Outer packaging height. |
| `dimensional_weight_kg` | Decimal | Required | Real number > 0.00 | kg | Non-unique | Calculated as `round((length * width * height) / 5000, 2)`. |
| `chargeable_weight_kg` | Decimal | Required | Real number > 0.00 | kg | Non-unique | Calculated as `max(actual_weight_kg, dimensional_weight_kg)`. |
| `delivery_status` | Enum | Required | `DELIVERED`, `IN_TRANSIT`, `EXCEPTION` | - | Non-unique | Must be valid delivery status. |
| `rate_id` | String | Required | `RATE-CAR-...` | - | Foreign Key | References `rate_card.rate_id`. Must match carrier, lane, service, and chargeable weight tier. |
| `pod_signatory` | String | Optional | Person name (e.g. "J. Doe") | - | Non-unique | Required if `delivery_status == 'DELIVERED'`. |

---

## 5. ShipmentLeg (`shipment_leg.csv`)
Individual transportation segment comprising a multi-stop or single-stop shipment journey.

| Field Name | Type | Req/Opt | Allowed Values / Format | Units | Uniqueness | Validation Rule |
|---|---|---|---|---|---|---|
| `leg_id` | String | Required | `LEG-2026-000001-01` | - | Primary Key | Pattern `^LEG-2026-\d{6}-\d{2}$`. Unique. |
| `shipment_id` | String | Required | `SHP-2026-000001` | - | Foreign Key | References `shipment.shipment_id`. |
| `sequence_no` | Integer | Required | Integer >= 1 | - | Non-unique | Order of the leg within the shipment. |
| `origin` | String | Required | 3-letter IATA/Hub code | - | Non-unique | Hub code. |
| `destination` | String | Required | 3-letter IATA/Hub code | - | Non-unique | `destination != origin`. |
| `depart_date` | String | Required | ISO 8601 Date (`YYYY-MM-DD`) | - | Non-unique | `depart_date >= shipment.ship_date`. |
| `arrive_date` | String | Required | ISO 8601 Date (`YYYY-MM-DD`) | - | Non-unique | `arrive_date >= depart_date`. |
| `status` | Enum | Required | `COMPLETED`, `IN_TRANSIT`, `CANCELLED` | - | Non-unique | Segment status. |

---

## 6. WeightMeasurement (`weight_measurement.csv`)
Certified scale weight audit records captured at warehouse or cross-dock origin.

| Field Name | Type | Req/Opt | Allowed Values / Format | Units | Uniqueness | Validation Rule |
|---|---|---|---|---|---|---|
| `measurement_id` | String | Required | `WM-2026-000001` | - | Primary Key | Pattern `^WM-2026-\d{6}$`. Unique. |
| `shipment_id` | String | Required | `SHP-2026-000001` | - | Foreign Key | References `shipment.shipment_id`. |
| `measured_weight_kg` | Decimal | Required | Real number > 0.00 | kg | Non-unique | Certified scale weight reading. |
| `unit` | Enum | Required | `kg` | - | Non-unique | Unit of mass. Standardized to `kg`. |
| `scale_id` | String | Required | `SCALE-BLR-01`, etc. | - | Non-unique | Calibration terminal identifier. |
| `certified` | Enum | Required | `true`, `false` | - | Non-unique | Whether calibration certificate is active. |
| `measured_at` | String | Required | ISO 8601 DateTime / Date | - | Non-unique | `measured_at <= shipment.delivery_date`. |

---

## 7. Accessorial (`accessorial.csv`)
Shipment-level auxiliary services and surcharges approved or requested for freight handling.

| Field Name | Type | Req/Opt | Allowed Values / Format | Units | Uniqueness | Validation Rule |
|---|---|---|---|---|---|---|
| `accessorial_id` | String | Required | `ACC-2026-000001` | - | Primary Key | Pattern `^ACC-2026-\d{6}$`. Unique. |
| `shipment_id` | String | Required | `SHP-2026-000001` | - | Foreign Key | References `shipment.shipment_id`. |
| `code` | Enum | Required | `LIFTGATE`, `RESIDENTIAL`, `DETENTION`, `HAZMAT`, `APPOINTMENT_DELIVERY`, `INSIDE_PICKUP` | - | Non-unique | Standard industry accessorial charge codes. |
| `amount` | Decimal | Required | Real number >= 0.00 | USD | Non-unique | Tariff amount for the accessorial. |
| `eligible` | Enum | Required | `true`, `false` | - | Non-unique | Whether shipment attributes justify the accessorial. |
| `approved` | Enum | Required | `true`, `false` | - | Non-unique | Whether warehouse / logistics planner pre-authorized charge. |
| `approval_ref` | String | Optional | Text (e.g. "AUTH-WH-0012") | - | Non-unique | Authorization voucher code if approved. |

---

## 8. FreightInvoice (`freight_invoice.csv`)
Carrier billing document submitted for settlement against one or more shipments.

| Field Name | Type | Req/Opt | Allowed Values / Format | Units | Uniqueness | Validation Rule |
|---|---|---|---|---|---|---|
| `invoice_id` | String | Required | `FINV-2026-000001` to `FINV-2026-999999` | - | Primary Key | Pattern `^FINV-2026-\d{6}$`. Unique invoice identifier. |
| `carrier_id` | String | Required | `CAR-000001` to `CAR-999999` | - | Foreign Key | References `carrier.carrier_id`. |
| `shipment_id` | String | Required | `SHP-2026-000001` | - | Foreign Key* | References `shipment.shipment_id`. *May be invalid ONLY in labelled `UNKNOWN_SHIPMENT` test anomaly. |
| `invoice_number`| String | Required | Text (e.g. `INV-APEX-90421`) | - | Non-unique | Carrier's proprietary invoice number. |
| `invoice_date` | String | Required | ISO 8601 Date (`YYYY-MM-DD`) | - | Non-unique | `invoice_date >= shipment.delivery_date`. |
| `currency` | String | Required | `USD` | - | Non-unique | Currency code. |
| `billed_total` | Decimal | Required | Real number > 0.00 | USD | Non-unique | Must equal arithmetic sum of linked `invoice_line.amount` values. |
| `source_rate_id`| String | Required | `RATE-CAR-...` | - | Foreign Key | Rate card referenced by the carrier on the invoice. |
| `status` | Enum | Required | `RECEIVED`, `AUDITED`, `APPROVED`, `DISPUTED`, `REJECTED` | - | Non-unique | Settlement state machine lifecycle. |

---

## 9. InvoiceLine (`invoice_line.csv`)
Individual line item charges detailing the base freight, fuel surcharges, and accessorial fees.

| Field Name | Type | Req/Opt | Allowed Values / Format | Units | Uniqueness | Validation Rule |
|---|---|---|---|---|---|---|
| `line_id` | String | Required | `FLINE-FINV-2026-000001-01` | - | Primary Key | Pattern `^FLINE-<invoice-id>-\d{2}$`. Unique across all lines. |
| `invoice_id` | String | Required | `FINV-2026-000001` | - | Foreign Key | References `freight_invoice.invoice_id`. |
| `line_no` | Integer | Required | Integer >= 1 | - | Non-unique | Sequential line index within invoice. |
| `line_type` | Enum | Required | `BASE`, `FUEL`, `LIFTGATE`, `RESIDENTIAL`, `DETENTION`, `HAZMAT`, `APPOINTMENT_DELIVERY`, `INSIDE_PICKUP` | - | Non-unique | Charge classification code. |
| `amount` | Decimal | Required | Real number >= 0.00 | USD | Non-unique | Amount billed for this line item. |
| `description` | String | Required | Text | - | Non-unique | Descriptive explanation of charge item. |

---

## 10. AuditException (`audit_exception.csv` / `outputs/exceptions.csv`)
Formally logged discrepancy detected during automated 3-way matching between contract, shipment, and invoice.

| Field Name | Type | Req/Opt | Allowed Values / Format | Units | Uniqueness | Validation Rule |
|---|---|---|---|---|---|---|
| `exception_id` | String | Required | `FEX-2026-000001` to `FEX-2026-999999` | - | Primary Key | Pattern `^FEX-2026-\d{6}$`. Unique exception identifier. |
| `invoice_id` | String | Required | `FINV-2026-000001` | - | Foreign Key | References `freight_invoice.invoice_id`. |
| `shipment_id` | String | Required | `SHP-2026-000001` or anomaly ID | - | Non-unique | Linked shipment identifier. |
| `carrier_id` | String | Required | `CAR-000001` | - | Foreign Key | References `carrier.carrier_id`. |
| `issue_type` | Enum | Required | `UNKNOWN_SHIPMENT`, `EXPIRED_RATE_CARD`, `WEIGHT_TIER_MISMATCH`, `DUPLICATE_SURCHARGE`, `INVALID_ACCESSORIAL`, `DUPLICATE_INVOICE`, `AMOUNT_MISMATCH`, `EXCESS_CREDIT` | - | Non-unique | Standardized freight audit violation taxonomy. |
| `severity` | Enum | Required | `INFO`, `REVIEW`, `REJECT` | - | Non-unique | `REJECT` for contractual breaches / missing records; `REVIEW` for price differences. |
| `expected_amount`| Decimal | Optional | Real number >= 0.00 or null | USD | Non-unique | Rate-calculated expected charge. Empty if shipment unknown. |
| `billed_amount` | Decimal | Required | Real number >= 0.00 | USD | Non-unique | Amount billed by carrier. |
| `variance` | Decimal | Optional | Real number or null | USD | Non-unique | `billed_amount - expected_amount`. Positive indicates carrier overbilling. |
| `explanation` | String | Required | Text | - | Non-unique | Clear, human-readable rationale for audit discrepancy. |
| `status` | Enum | Required | `OPEN`, `UNDER_REVIEW`, `DISPUTED`, `RESOLVED`, `WAIVED` | - | Non-unique | Exception resolution workflow state. |

---

## 11. CreditNote (`credit_note.csv` / `credit_note_validation.csv`)
Carrier-issued credit memorandum acknowledging dispute, overbilling refund, or tariff correction.

| Field Name | Type | Req/Opt | Allowed Values / Format | Units | Uniqueness | Validation Rule |
|---|---|---|---|---|---|---|
| `credit_note_id`| String | Required | `CN-2026-000001` to `CN-2026-999999` | - | Primary Key | Pattern `^CN-2026-\d{6}$`. Unique credit note identifier. |
| `exception_id` | String | Required | `FEX-2026-000001` | - | Foreign Key | References `audit_exception.exception_id`. |
| `invoice_id` | String | Required | `FINV-2026-000001` | - | Foreign Key | References `freight_invoice.invoice_id`. |
| `carrier_id` | String | Required | `CAR-000001` | - | Foreign Key | References `carrier.carrier_id`. |
| `credit_note_no`| String | Required | Text (e.g. `CR-APEX-1002`) | - | Non-unique | Carrier credit voucher reference number. |
| `credit_date` | String | Required | ISO 8601 Date (`YYYY-MM-DD`) | - | Non-unique | Date credit note was issued. Must be `>= invoice_date`. |
| `amount` | Decimal | Required | Real number > 0.00 | USD | Non-unique | Credit amount issued. |
| `approved_dispute_amount` | Decimal | Required | Real number >= 0.00 | USD | Non-unique | Maximum allowable dispute amount approved for exception. |
| `validation_status` | Enum | Required | `VALID`, `EXCESS_CREDIT` | - | Non-unique | `VALID` if `amount <= approved_dispute_amount + 0.01`, else `EXCESS_CREDIT`. |
| `status` | Enum | Required | `RECEIVED`, `APPLIED`, `REJECTED` | - | Non-unique | Settlement reconciliation status. |

---

## 12. GroundTruth (`ground_truth.csv`) [Evaluation-Only Artifact]
Out-of-band evaluation dataset cataloging deliberately injected synthetic anomalies. **Must NEVER be consumed by the audit engine.**

| Field Name | Type | Req/Opt | Allowed Values / Format | Units | Uniqueness | Validation Rule |
|---|---|---|---|---|---|---|
| `case_id` | String | Required | `GT-000001` to `GT-999999` | - | Primary Key | Unique evaluation benchmark case ID. |
| `invoice_id` | String | Required | `FINV-2026-000001` | - | Non-unique | Linked invoice under test. |
| `issue_type` | Enum | Required | `UNKNOWN_SHIPMENT`, `EXPIRED_RATE_CARD`, `WEIGHT_TIER_MISMATCH`, `DUPLICATE_SURCHARGE`, `INVALID_ACCESSORIAL`, `DUPLICATE_INVOICE`, `EXCESS_CREDIT` | - | Non-unique | Targeted anomaly category. |
| `expected_decision`| Enum | Required | `PASS`, `REVIEW`, `REJECT` | - | Non-unique | Expected operational decision by audit engine. |
| `expected_variance`| Decimal | Optional | Real number | USD | Non-unique | Expected financial variance injected. |
| `details` | String | Required | Text | - | Non-unique | Engineering explanation of injected condition. |
