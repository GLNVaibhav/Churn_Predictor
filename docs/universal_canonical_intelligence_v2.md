# Universal Canonical Intelligence Layer (V2)

V2 is additive. It does not call prediction code, mutate a dataframe used by
V1, select a route, or translate a canonical feature into a legacy model
column.

```text
Raw enterprise dataset
        |
        v
V1 Business Meaning + Canonical Mapping + Knowledge Graph + Coverage
        |
        |  (read-only intelligence evidence)
        v
V2 Canonical Feature Builder
        |
        +--> CanonicalFeatureSet
        |      - value (or missing, never default-filled)
        |      - confidence
        |      - provenance
        |      - supporting business concepts
        |      - derivation method
        |
        +--> Compatibility Intelligence
        |      - Legacy schema suitability (only when supplied)
        |      - Future universal-model readiness
        |
        +--> Training Readiness Report
               - coverage, confidence, provenance, unsupported concepts

Future only: canonical feature sets from multiple enterprises
        --> sector-specific universal training matrix --> new universal model

Existing V1 inference, models, routing, CLI, reports, ABIL, UDIF: unchanged
```

Canonical specifications are sector contracts in
`knowledge/<sector>/canonical_features.yaml`.  Evidence names are business
concepts, not organisation, carrier, or dataset column names.  A specification
can declare multiple alternative required evidence concepts.  The builder only
uses recognised evidence and leaves an unsupported feature missing; it never
uses defaults and never creates a mapping such as recharge value to a legacy
monthly-charge field.

The intended future training process is to build a `CanonicalFeatureSet` for
each source dataset, retain confidence and provenance alongside every feature,
apply a training governance threshold using `CompatibilityAssessment`, and
train a new sector model only on the approved canonical feature contract.
