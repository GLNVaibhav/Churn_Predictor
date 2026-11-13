# UCIF Novelty Preservation Matrix — Checkpoint M3

**Audit baseline:** branch `dev`, starting HEAD `821bfdd3c7a29183f8c0d77cdc7d44cb5a263d25` (13 November 2026). The original terminology was checked against `UCIF_Report.docx`, supplied at `C:\Users\DELL\OneDrive\Documents\SRM\Churn_Research\UCIF_Report.docx`.

The report describes UCIF as an implementation-supported **semantic software architecture for cross-sector churn intelligence and decision support**, rather than a new churn algorithm. Its runtime sequence is orchestration, typed semantic/profile/context/graph/canonical mapping/coverage/routing, prediction, Decision Intelligence, optional ABIL and reports. It also marks the separately named `semantic_intelligence/` and `prediction_intelligence/` packages as future or partially integrated—not as the active runtime sequence.

## Before / after preservation matrix

| Research contribution (report terminology) | Before this work | Changes in this checkpoint | After / evidence and limits |
|---|---|---|---|
| Semantic Intelligence and Context Validation | Active typed pipeline. Business meaning could lose the raw source-column identifier in knowledge-pack and inferred paths. | `universal_churn/business_meaning.py` now places `source_column` in each produced meaning. | Still active; tested on eight external schemas. Sector classification succeeded 8/8, but context validation marked all eight schemas ambiguous / Critical. Sector recognition is not semantic correctness. |
| Semantic Graph and Canonical Mapping | Active; serialized mapping names could fall back to generated `col_<n>_<concept>` labels. | `universal_churn/canonical_mapping.py` now uses preserved raw source names and resolves conflict entity evidence from the preceding meaning. | Mapping lineage is inspectable. Low-confidence mappings remain and are explicitly reported; no unsupported feature values were added. |
| Coverage Intelligence | Active typed coverage with concept, entity, semantic, confidence, and supplemental stability diagnostics. | No coverage formula or readiness thresholds changed. | Scores and penalties remain separate in execution output. The eight external inputs show nontrivial coverage, but coverage is not a measure of predictive performance or semantic truth. |
| Adaptive Routing | Active deterministic routing. Its code documented a 0.4 prior + 0.6 factor budget, while factor weights summed to 1.0; `confidence` could be mistaken for probability. | `universal_churn/routing.py` adjusts factor weights to sum to 0.60 and documents the score as deterministic, not calibrated. A regression test checks the budget and a worked score. | Routing is still deterministic and has no empirically justified minimum confidence threshold. All eight external runs selected `GenericPipeline`; the actual inference model was Universal XGBoost. Scores around 0.71–0.77 are not probabilities of correct routing. |
| Adaptive Business Intelligence Layer (ABIL) | Context was persisted and evaluated, but recommendations commonly repeated the source’s generic mitigation text. | `backend/services/business_context_service.py` creates sector/category-specific bounded follow-ups, carries source recommendation, department, priority, evidence ID, rationale and limitations. Executor/report and workspace views expose these as rule-based context, separate from model output. | 8/8 paired external runs produced 25 context signals and 25 recommendations, with exactly invariant prediction labels/probabilities. Recommendations are deterministic rules, not ML or causal conclusions; broad categories still use a generic validation action. |
| Decision Intelligence, diagnostics and enterprise reporting | Active execution outputs, diagnostics, decision assessments and report references. SHAP values are not part of the returned diagnostics contract. | No prediction or active model change. UI clarifies rule-based follow-up and limitations. | Browser workspace, diagnostics and report views rendered a real local execution. Diagnostics explicitly disclose that local per-record SHAP values are not returned. Existing decision/report sections remain active; evidence quality is bounded by source context. |

## External-schema semantic and routing evidence

The same eight supplied CSV/ABIL pairs were read from the previously recorded external paths and their 16 SHA-256 hashes still match `outputs/evaluation/old_vs_new/input_manifest.json`. They were not used for training or tuning. Each table row below is the automatic, dataset-only execution; the paired ABIL run gave the same prediction outputs.

| Input | Rows | Detected sector | Coverage | Concept confidence | Missing critical concepts | Context domain / confidence | Context health / ambiguity | Canonical map: ambiguous / conflicting / duplicate / high-confidence | Selected pipeline; route score | Inference model / artifact |
|---|---:|---|---:|---:|---|---|---|---|---|---|
| Airtel Telecom | 400 | Telecom | .793 | .585 | Customer, Lifecycle | Customer / .480 | Critical / yes | 10 / 6 / 5 / 8 | GenericPipeline; .758 | Universal XGBoost / `outputs/universal/universal_xgb_model.pkl` |
| Jio Telecom | 600 | Telecom | .793 | .585 | Customer, Lifecycle | Customer / .480 | Critical / yes | 10 / 6 / 5 / 8 | GenericPipeline; .758 | Universal XGBoost / same artifact |
| Axis Banking | 450 | Banking | .727 | .437 | Customer | Customer / .440 | Critical / yes | 18 / 10 / 5 / 3 | GenericPipeline; .722 | Universal XGBoost / same artifact |
| HDFC Banking | 550 | Banking | .727 | .437 | Customer | Customer / .440 | Critical / yes | 18 / 10 / 5 / 3 | GenericPipeline; .722 | Universal XGBoost / same artifact |
| Amazon E-commerce | 700 | E-commerce | .733 | .540 | Customer | Customer / .640 | Critical / yes | 10 / 6 / 4 / 3 | GenericPipeline; .766 | Universal XGBoost / same artifact |
| Flipkart E-commerce | 300 | E-commerce | .735 | .462 | Customer | Customer / .520 | Critical / yes | 12 / 2 / 3 / 2 | GenericPipeline; .737 | Universal XGBoost / same artifact |
| Apollo Healthcare | 500 | Healthcare | .727 | .468 | Customer | Customer / .480 | Critical / yes | 16 / 1 / 6 / 3 | GenericPipeline; .730 | Universal XGBoost / same artifact |
| KIMS Healthcare | 500 | Healthcare | .673 | .432 | Customer | Customer / .440 | Critical / yes | 14 / 1 / 6 / 3 | GenericPipeline; .714 | Universal XGBoost / same artifact |

**Lineage correction evidence:** the 32-case execution outputs now retain each original CSV column in `business_meanings[*].supporting_features.source_column` and `canonical_mapping.mappings[*].column_name`. Examples of unresolved low-confidence mapping include Airtel `AutoPay → Cost (.21)`, Axis `Loans → Complaint (.20)`, Amazon `Reviews_Posted → Complaint (.20)`, and Apollo `Department → Marketing (.20)`. These are not asserted as valid; semantic uncertainty remains a research limitation. `Patient_ID`/`UHID` and similar identifiers also need domain-specific canonical entity concepts before claiming complete healthcare mapping.

`GenericPipeline` is the routing label, not the estimator artifact. Runtime code at `universal_churn/universal_pipeline.py:252-259,295-301` loads `UNIVERSAL_MODEL_PATH`, aligns to scaler feature order, and labels predictions `Universal XGBoost`; `universal_churn/config.py:16` points to the saved XGBoost artifact. `backend/adapters/framework_adapter.py` currently serializes `model_artifact=selected_pipeline`, so that field alone is misleading and should not be used as proof of the estimator file/version. The active predictor remained unchanged. Expected universal features absent from a transformed input are filled with zero at the universal-pipeline alignment step; this remains a compatibility risk requiring semantic feature-level review.

## External-label diagnostic (not validated predictive evidence)

Metrics were recomputed from the current run’s output and target columns at the default 0.5 classification threshold. Supplied files are company-inspired evaluation fixtures; target provenance, label semantics and independence from training data are unverified. Treat this strictly as an external-schema diagnostic, not production or research validity. PR-AUC is average precision. Confusion matrices are `[TN, FP, FN, TP]`.

| Dataset | Accuracy | Precision | Recall | F1 | ROC-AUC | Average precision | Balanced accuracy | MCC | Brier | Confusion matrix |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Airtel | .4925 | .1511 | .7391 | .2509 | .7294 | .3893 | .5998 | .1283 | .3082 | [163,191,12,34] |
| Jio | .5417 | .2043 | .8272 | .3276 | .7747 | .4525 | .6621 | .2226 | .2913 | [258,261,14,67] |
| Axis | .2467 | .0733 | .5208 | .1285 | .3249 | .0755 | .3674 | -.1911 | .5092 | [86,316,23,25] |
| HDFC | .2782 | .0896 | .5373 | .1535 | .3485 | .0892 | .3898 | -.1626 | .4922 | [117,366,31,36] |
| Amazon | .4300 | .0278 | .0968 | .0432 | .3758 | .1050 | .2889 | -.2874 | .3027 | [292,315,84,9] |
| Flipkart | .5000 | .1233 | .4500 | .1935 | .4902 | .1748 | .4788 | -.0288 | .3156 | [132,128,22,18] |
| Apollo | .4020 | .3996 | .9850 | .5685 | .3013 | .3020 | .4992 | -.0069 | .4791 | [4,296,3,197] |
| KIMS | .4060 | .3937 | .9692 | .5600 | .6025 | .4807 | .5076 | .0377 | .3196 | [14,291,6,189] |

The results are weak/inconsistent for Banking and E-commerce and show high churn-positive prediction rates in several domains. Brier values are not calibration certification. No active-versus-candidate comparison or retraining was performed: current candidate artifacts do not have established feature/label compatibility with these external schemas, so candidate benchmarking and model-promotion recommendations remain blocked.

## Reproducibility, tests and checkpoint status

- 32/32 current FastAPI TestClient runs succeeded in a temporary HEAD snapshot overlaid with the reviewed source changes: automatic/manual sector × dataset-only/ABIL for each dataset. Prediction counts matched rows. The original inputs remain unchanged.
- ABIL: paired exact equality of `(Predicted_Churn, Churn_Probability)` for all 8 datasets; 25 events and 25 recommendations per context. Example (Telecom Network Quality): prior source text “Review and execute mitigation plan.”; generated action “Review the reported network or service-reliability evidence for the stated period; validate any supplied affected areas before considering a retention response.” Department, priority and evidence identity are carried independently.
- Actual paired examples from the supplied contexts (the generated text is rule-based guidance and is explicitly non-causal):

| Sector and signal | Supplied recommendation before | UCIF follow-up after | Trace |
|---|---|---|---|
| Telecom — Network Quality | Review and execute mitigation plan. | Review the reported network or service-reliability evidence for the stated period; validate any supplied affected areas before considering a retention response. | Airtel `ABIL-bb709c6c929547aeb20a7f2fed9da23e-4` |
| Banking — Credit Risk | Review and execute mitigation plan. | Route the supplied risk or compliance signal for authorized case review; validate the evidence and do not use churn risk as a substitute for a regulated risk decision. | Axis `ABIL-0461c08192de418db3c29069a5dc20e7-5` |
| E-commerce — Logistics | Review and implement strategic initiative. | Review the supplied fulfillment, return, or inventory evidence for the reported period; validate any affected buyer or seller cohort before taking action. | Amazon `ABIL-1821610de621472fad9a4884a8fc8c66-4` |
| Healthcare — Clinical Quality | Review and implement strategic initiative. | Route the supplied clinical or safety signal to the authorized quality or clinical-governance owner; verify it through approved records and keep it separate from churn-risk decisions. | Apollo `ABIL-16f72ccdd804440793bbffcbff6693cc-3` |
- Actual Next.js → same-origin proxy → FastAPI local flow: upload Airtel (201), analyze (202), terminal SUCCEEDED, 400 predictions, 13/13 pipeline stages, decision, diagnostics and three report references. Browser UI opened this execution and rendered workspace overview, Diagnostic Intelligence and Reports. Browser console logs and mobile viewport were not available to this browser interface.
- Backend suite: `pytest -q backend/tests` → 123 passed, 3 warnings. Frontend TypeScript passed after the dependency tree was restored. ESLint on `src` → 0 errors, 7 existing chart warnings. `pnpm run build` succeeded; no frontend test/spec files or test script were found. `git diff --check` passed with Git line-ending notices.
- Original 34 active model artifact hashes and all 16 external input hashes still match their manifests. No training, model rewrite or promotion occurred.

| Checkpoint | Status | Reason |
|---|---|---|
| 1 Novelty preservation baseline | IMPLEMENTED AND VERIFIED | Original report terms documented; before/after matrix here. |
| 2 Semantic mapping and coverage | IMPLEMENTED BUT NOT FULLY VERIFIED | Source lineage fixed and eight outputs inspected; ambiguity/low-confidence mappings remain. |
| 3 Model compatibility and routing | IMPLEMENTED BUT NOT FULLY VERIFIED | Eight routes/model outputs observed; artifact field ambiguity and universal feature-fill risk remain. |
| 4 Active vs candidate evaluation | BLOCKED | No candidate with demonstrated compatible features/labels; supplied labels lack validated provenance. |
| 5 Bounded model experiments | NOT COMPLETED | No training/tuning on external inputs; no compatible candidate comparison. |
| 6 ABIL recommendation specificity | IMPLEMENTED BUT NOT FULLY VERIFIED | Deterministic bounded rules and 4-sector tests; business efficacy not validated. |
| 7 Browser-to-backend integration | IMPLEMENTED BUT NOT FULLY VERIFIED | One real proxy workflow and three rendered views; not all 14 interactions were browser-tested. |
| 8 UI intelligence presentation | IMPLEMENTED BUT NOT FULLY VERIFIED | Workspace exposes returned diagnostics/reports; mobile and all routes not covered. |
| 9 MLOps monitoring | NOT COMPLETED | No new live operational metrics/routing distribution monitoring added. |
| 10 Novelty-preserving regression tests | IMPLEMENTED BUT NOT FULLY VERIFIED | Lineage, routing budget, ABIL behavior/report traces covered; all six innovation categories lack dedicated regression coverage. |
| 11 Final validation and local commits | IMPLEMENTED BUT NOT FULLY VERIFIED | Backend/frontend validation passed; standalone npm unavailable. Verified source commits `1d1c2e9` and `e49b899` were created; unrelated pre-existing changes remain uncommitted. |
| 12 Post-change novelty matrix | IMPLEMENTED AND VERIFIED | Matrix records preservation and remaining limits. |

No model has been promoted. No external evaluation input, model artifact, golden file, or unrelated existing worktree change is included in this report’s source changes.
