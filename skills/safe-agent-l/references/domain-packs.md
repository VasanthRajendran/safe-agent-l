# Domain packs

Each pack is a starting point, not a policy. It gives you the vocabulary
(what to call the fields in your action dict), the constraints worth
having on day one, the safety layers that domain usually needs, and the
trigger keywords to append to the skill description so it fires on your
team's actual words.

Copy the closest pack, rename fields to match your action dict, set the
bounds from your real policy, and delete what does not apply. Bounds in
these packs are illustrative — none of them is your policy.

## How to use a pack

1. **Field vocabulary** → shape `propose_fn`'s return dict to these keys.
2. **Constraints** → paste into a `ConstraintEngine`, replace the bounds.
3. **Safety layers** → add to the `SafetyStack`; these are the checks that
   should not depend on the constraint config being right.
4. **Trigger keywords** → append to the `description:` line in `SKILL.md`
   so the skill loads when someone types your domain's terms.

---

## Pricing and merchandising

**Trigger keywords:** price, repricing, MAP, minimum advertised price,
markdown, discount, margin, promo, list price, SKU, competitor price

**Field vocabulary:** `sku`, `price`, `discount_pct`, `margin_pct`,
`channel`, `currency`

```python
ConstraintEngine([
    Constraint(field="price", op="gte", bound=19.99,
               reason="contractual MAP floor", required=True),
    Constraint(field="discount_pct", op="lte", bound=0.30,
               reason="max autonomous discount", mode=EnforcementMode.CLIP),
    Constraint(field="margin_pct", op="gte", bound=0.05,
               reason="never price below margin floor"),
    Constraint(field="currency", op="eq", bound="USD",
               reason="single-currency deployment", required=True),
])
```

**Safety layers:** `AnomalyDetector().as_layer("price")` to catch a
repricer that has lost its mind; a check that the new price is within some
ratio of the previous price (guards against a decimal-shift bug that no
absolute floor catches).

---

## Customer support, refunds, and credits

**Trigger keywords:** refund, credit, chargeback, goodwill, ticket,
escalation, case, RMA, return authorization, support agent, tool allowlist

**Field vocabulary:** `tool`, `order_id`, `refund_amount`, `credit_amount`,
`customer_tier`, `reason_code`

```python
ConstraintEngine([
    Constraint(field="tool", op="in",
               bound=["lookup_order", "create_ticket", "issue_refund", "send_email"],
               reason="tool allowlist", required=True),
    Constraint(field="refund_amount", op="lte", bound=100.0,
               reason="autonomous refund cap; above this goes to a human"),
    Constraint(field="refund_amount", op="gt", bound=0.0,
               reason="no zero or negative refunds"),
    Constraint(field="reason_code", op="in", bound=VALID_REASON_CODES,
               reason="reason code must be one the finance system accepts"),
])
```

Note the deliberate `REJECT` on the refund cap rather than `CLIP`: an
agent asking for $10,000 should be escalated, not quietly handed $100.

**Safety layers:** a per-customer daily refund total against a running
ledger; `AnomalyDetector().as_layer("refund_amount")`; a layer rejecting
refunds on orders already refunded.

---

## Lending and financial services

**Trigger keywords:** credit line, APR, loan, underwriting, adverse action,
KYC, AML, disbursement, limit increase, collections, payment plan

**Field vocabulary:** `action`, `applicant_id`, `credit_limit`, `apr`,
`term_months`, `disbursement_amount`, `decision_code`

```python
ConstraintEngine([
    Constraint(field="action", op="in",
               bound=["approve", "decline", "refer_to_underwriter"],
               reason="agent may not invent decision types", required=True),
    Constraint(field="apr", op="lte", bound=0.2999,
               reason="state usury ceiling"),
    Constraint(field="credit_limit", op="lte", bound=5000.0,
               reason="autonomous limit-increase ceiling"),
    Constraint(field="decision_code", op="not_in", bound=PROHIBITED_BASES,
               reason="prohibited basis under fair-lending policy", required=True),
])
```

**Safety layers:** a layer asserting an adverse-action reason is present
whenever `action == "decline"`; a layer refusing any action when the
applicant record is missing a required KYC flag. This domain is where the
audit trail earns its keep — always configure a `sink_path`.

**Read the limits section of `SKILL.md` out loud here.** The library
enforces what you configure and evidences it. Whether the configuration is
legally correct is a question for compliance counsel, not for this skill.

---

## Clinical and health operations

**Trigger keywords:** dose, dosage, formulary, prior authorization,
scheduling, triage, PHI, care plan, referral, order entry

**Field vocabulary:** `order_type`, `patient_id`, `medication`, `dose_mg`,
`route`, `requires_clinician_review`

```python
ConstraintEngine([
    Constraint(field="order_type", op="in",
               bound=["schedule_followup", "send_reminder", "route_to_clinician"],
               reason="agent may not place clinical orders autonomously",
               required=True),
    Constraint(field="requires_clinician_review", op="eq", bound=True,
               reason="all patient-facing output is clinician-reviewed",
               required=True),
])
```

The pattern here is inverted from the others: the allowlist is short and
everything consequential routes to a human. Constraining a dose range is
usually the wrong design — keep the agent out of dosing entirely and
constrain it to scheduling and routing.

**Safety layers:** a layer rejecting any action whose payload contains
identifiers not in the minimum necessary set for the task.

---

## Infrastructure and DevOps automation

**Trigger keywords:** deploy, rollback, terraform, kubectl, scale, restart,
migration, production, blast radius, runbook, incident remediation

**Field vocabulary:** `operation`, `environment`, `target`, `replica_count`,
`is_destructive`

```python
ConstraintEngine([
    Constraint(field="operation", op="in",
               bound=["scale", "restart", "rollback", "describe"],
               reason="operation allowlist", required=True),
    Constraint(field="environment", op="not_in", bound=["prod"],
               reason="no autonomous production changes", required=True),
    Constraint(field="replica_count", op="lte", bound=20,
               reason="scale ceiling", mode=EnforcementMode.CLIP),
    Constraint(field="is_destructive", op="eq", bound=False,
               reason="destructive operations require a human", required=True),
])
```

**Safety layers:** a layer matching `target` against an owned-resource
allowlist (an operation name allowlist does not stop the right operation
on the wrong cluster); a business-hours check for anything beyond
`describe`.

---

## Data access and egress

**Trigger keywords:** PII, export, query, egress, redaction, row limit,
data retention, bulk download, customer data

**Field vocabulary:** `query_type`, `dataset`, `row_limit`, `columns`,
`destination`

```python
ConstraintEngine([
    Constraint(field="dataset", op="in", bound=APPROVED_DATASETS,
               reason="dataset allowlist", required=True),
    Constraint(field="row_limit", op="lte", bound=1000,
               reason="bulk-egress ceiling", mode=EnforcementMode.CLIP),
    Constraint(field="destination", op="in", bound=["internal_dashboard"],
               reason="no external destinations", required=True),
])
```

**Safety layers:** a layer rejecting any request whose `columns` intersect
a restricted-column set — column-level rules do not fit the one-field
constraint shape and belong in a layer.

---

## Writing a new pack

Keep the same four sections. Two questions decide most of the design:

**What is the smallest set of fields that fully describes a
consequential action here?** If a rule needs two fields to evaluate — "an
export over 1000 rows is fine unless the destination is external" — it is
a safety layer, not a constraint. Constraints are per-field by design.

**For each rule: is a violation a mistake to correct, or an attempt to
escalate?** Correct with `CLIP`. Escalate with `REJECT`, and route the
denial somewhere a human sees it.

Add the pack to this file so the next person in your organization
inherits it instead of rediscovering it.
