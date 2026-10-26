# Business Rules & Decision Policies

This document formalizes the freight calculation formulas, 3-way matching rules, exception severity classification, and settlement policies implemented by the audit engine.

---

## 1. Physical Characteristics & Weight Calculations

### 1.1 Dimensional Weight Formula
Domestic and international freight tariffs compute volumetric density to account for low-density, bulky shipments:

$$\text{Dimensional Weight (kg)} = \text{round}\left(\frac{\text{Length (cm)} \times \text{Width (cm)} \times \text{Height (cm)}}{5000}, 2\right)$$

- **Standard Divisor:** $5000\text{ cm}^3/\text{kg}$ (standard IATA and domestic express freight factor).
- **Rounding:** Rounded arithmetically to 2 decimal places.

### 1.2 Chargeable Weight Formula
Carriers charge based on the greater of certified scale weight and volumetric weight:

$$\text{Chargeable Weight (kg)} = \max(\text{Actual Scale Weight (kg)}, \text{Dimensional Weight (kg)})$$

---

## 2. Contracted Tariff Lookup & Rating

### 2.1 Weight Tier Rating
Contracted rate cards define 4 mutually exclusive weight brackets per carrier, lane, and service tier:

| Tier Index | Weight Range (kg) | Bracket Definition |
|---|---|---|
| Tier 1 | $0.0 \le W < 5.0$ | Document / Small Parcel |
| Tier 2 | $5.0 \le W < 15.0$ | Medium Parcel / Carton |
| Tier 3 | $15.0 \le W < 30.0$ | Heavy Carton / Multi-piece |
| Tier 4 | $30.0 \le W < \infty$ | Pallet / Bulk Freight |

A shipment must be rated using the tier matching its **Chargeable Weight**:
$$\text{Weight Min} \le \text{Chargeable Weight} < \text{Weight Max}$$

### 2.2 Contract Effective Dates
A rate card is valid if and only if the **Invoice Date** falls within its contractual validity window:
$$\text{Rate Effective From} \le \text{Invoice Date} \le \text{Rate Effective To}$$

If an invoice references an expired tariff or a date outside this window, the invoice is flagged with `EXPIRED_RATE_CARD`.

---

## 3. Expected Freight Charge Calculation

The expected freight invoice amount is determined by 3 additive components:

$$\text{Expected Total} = \text{Base Freight} + \text{Fuel Surcharge} + \sum \text{Approved Accessorials}$$

1. **Contracted Base Freight:** Exact flat rate defined for the matched lane, service, and weight tier.
2. **Contracted Fuel Surcharge:**
   $$\text{Fuel Surcharge} = \text{round}(\text{Contracted Base Freight} \times \text{Contracted Fuel \%}, 2)$$
   - Standard fuel percentage: $12\%$ ($0.12$).
3. **Approved Accessorial Charges:**
   Auxiliary fees are payable if and only if:
   - `eligible == 'true'` (shipment attributes justify the service), and
   - `approved == 'true'` (warehouse or planner pre-authorized the charge code).

---

## 4. Discrepancy Taxonomy & Severity Classification

| Issue Type | Severity | Trigger Condition | Decision Impact |
|---|---|---|---|
| `UNKNOWN_SHIPMENT` | `REJECT` | Referenced `shipment_id` does not exist in TMS / shipment records. | Automatic hard rejection. |
| `DUPLICATE_INVOICE` | `REJECT` | The same shipment is billed across multiple invoices. | Automatic hard rejection. |
| `EXPIRED_RATE_CARD` | `REJECT` | Referenced rate card expired prior to invoice date. | Automatic hard rejection. |
| `DUPLICATE_SURCHARGE`| `REJECT` | Invoice contains more than one `FUEL` surcharge line. | Automatic hard rejection. |
| `INVALID_ACCESSORIAL`| `REJECT` | Invoice charges for an accessorial that is not pre-approved or eligible. | Automatic rejection of accessorial. |
| `WEIGHT_TIER_MISMATCH`| `REVIEW` | Carrier rated shipment at a higher weight tier than warranted by chargeable weight. | Analyst review & dispute. |
| `AMOUNT_MISMATCH` | `REVIEW` | Billed amount differs from rate card calculation by $> \$0.01$. | Analyst review & dispute. |
| `EXCESS_CREDIT` | `REJECT` | Credit note amount exceeds the approved dispute settlement limit. | Rejection of excessive credit. |

---

## 5. Overall Decision Policy

Every audited invoice receives an immutable decision:

1. **`PASS`**:
   - Zero violations detected.
   - Billed total reconciles to calculated expected total within $\$0.01$ tolerance.
   - Ready for automated batch payment processing.
2. **`REVIEW`**:
   - Contains price differences, weight tier disputes, or minor miscalculations.
   - Requires Logistics Analyst review and formal carrier dispute workflow.
3. **`REJECT`**:
   - Contains a contractual violation or invalid business entity (unknown shipment, duplicate invoice, expired rate card, duplicate fuel surcharge, unapproved accessorial).
   - Invoiced payment is suspended pending carrier correction.

---

## 6. Credit Note Settlement & Reconciliation Policy

When an analyst disputes an overcharge, the carrier issues a formal credit memorandum (`CreditNote`):

$$\text{Approved Dispute Limit} = \max_{\text{exceptions}} |\text{Variance}|$$

- **Valid Credit Note (`VALID`):**
  $$\text{Credit Amount} \le \text{Approved Dispute Limit} + 0.01$$
  Credit note is applied to offset accounts payable.
- **Excessive Credit Note (`EXCESS_CREDIT`):**
  $$\text{Credit Amount} > \text{Approved Dispute Limit} + 0.01$$
  Credit note is flagged with severity `REJECT` to prevent incorrect accounting adjustments or fraudulent reversals.
