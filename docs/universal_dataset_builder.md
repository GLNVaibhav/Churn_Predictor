# Universal Dataset Builder (UCIF V2)

## Before and after

```text
V1: company-specific raw columns -> legacy sector model -> prediction

V2: multiple enterprise datasets
        -> existing semantic intelligence (read-only)
        -> canonical feature builder
        -> dataset validation and compatibility assessment
        -> confidence-aware canonical merge
        -> Universal_<Sector>_Training.csv
        -> future universal sector model training (outside this phase)
```

## Pipeline

`build_universal_training_dataset()` accepts explicit `DatasetInput` objects.
Each input has a dataframe, governed dataset origin, and explicitly named
target column.  The builder invokes the existing intelligence pipeline and the
additive V2 canonical-feature layer, then evaluates readiness before merging.

Every accepted input is aligned to the exact feature order in its sector's
`knowledge/<sector>/canonical_features.yaml`.  No original feature column is
carried into the unified training frame.  Missing business evidence stays
missing; it is never converted into a legacy feature or filled with a default.

## Validation and readiness

Datasets receive `READY`, `PARTIAL`, `INSUFFICIENT`, or `REJECTED` based on
canonical coverage, mean confidence, derived-feature ratio, compatibility, and
an optional governed list of critical canonical concepts.  `INSUFFICIENT` and
`REJECTED` inputs are excluded from the merged rows but retained in the quality
report, which makes exclusions auditable.

## Confidence and provenance

The in-memory `CanonicalTrainingDataset` retains full feature provenance by
dataset origin.  The CSV contains canonical feature values, `Target`, dataset
origin, coverage/readiness/compatibility, confidence columns, derivation
methods, and semantic provenance (business and canonical concepts).  It does
not export raw enterprise column names.

## Future training

The merged export is a governed cross-enterprise training candidate, not a
model input today.  A future training workflow can accept only approved
datasets, set sector critical concepts centrally, inspect confidence metadata,
and fit a new model on stable business features shared by Airtel, Jio,
Vodafone, BSNL, HDFC, Axis, ICICI, Apollo, KIMS, Amazon, and Flipkart without
changing the feature contract for each company.
