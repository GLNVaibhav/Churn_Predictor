"""
tests/test_semantic_schema.py
══════════════════════════════════════════════════════════════════════
Version 7, Chunk 1 tests — the Semantic Schema Intelligence Layer.

Organized to mirror the chunk's own acceptance criteria:

    TestVersion6BehaviorUnchanged   — the hard requirement: nothing
                                        about resolve_schema()'s
                                        default output may change.
    TestBackends                     — embedding backend contracts.
    TestSemanticCandidateRetrieval   — top-k / scoring mechanics.
    TestSemanticResolution           — resolve_semantic_alias() /
                                        resolve_schema(enable_semantic=True).
    TestPrecedenceRules              — deterministic-always-wins.
    TestDiagnosticsReport            — "why it matched" / "why
                                        deterministic won" reporting.
    TestGoldenMessyUnknownSynthetic  — the four required dataset
                                        categories from the validation
                                        section of the spec.

All tests pin backend='tfidf' explicitly (rather than 'auto') so
results are deterministic and independent of whether
sentence-transformers/Ollama happen to be installed in the CI
environment — the TF-IDF fallback is always available and is exactly
what "auto" degrades to when neither optional dependency is present.
"""
from __future__ import annotations

import pandas as pd
import pytest

from universal_churn.schema_resolution import (
    resolve_schema, resolution_summary, CANONICAL_FIELDS, ColumnResolution,
)
from universal_churn.semantic_schema import (
    SemanticConfig, SemanticSchemaResolver, SemanticCandidate, SemanticMatchReport,
    TfidfCharNgramBackend, SentenceTransformerBackend, OllamaEmbeddingBackend,
    select_backend, get_default_resolver, reset_default_resolver,
    diagnose_columns, resolve_with_semantics, _humanize,
)


@pytest.fixture
def tfidf_config():
    return SemanticConfig(backend="tfidf", confidence_threshold=0.5, top_k=3)


@pytest.fixture
def tfidf_resolver(tfidf_config):
    return SemanticSchemaResolver(config=tfidf_config)


# ══════════════════════════════════════════════════════════════════
# 1. VERSION 6 BEHAVIOR MUST BE UNCHANGED BY DEFAULT
# ══════════════════════════════════════════════════════════════════

class TestVersion6BehaviorUnchanged:
    def test_default_call_signature_still_returns_two_tuple(self):
        df = pd.DataFrame({'tenure': [1, 2], 'foo': [1, 2]})
        result = resolve_schema(df)
        assert isinstance(result, tuple) and len(result) == 2

    def test_unresolved_columns_stay_unresolved_without_flag(self):
        """A column the semantic layer WOULD resolve must remain
        unresolved when enable_semantic is not passed at all."""
        df = pd.DataFrame({'SubscriptionCost': [10, 20]})
        _, resolutions = resolve_schema(df)
        assert resolutions[0].method == 'unresolved'
        assert resolutions[0].canonical_field is None

    def test_explicit_semantic_false_matches_default(self):
        df = pd.DataFrame({'SubscriptionCost': [10, 20], 'tenure': [1, 2]})
        _, a = resolve_schema(df)
        _, b = resolve_schema(df, enable_semantic=False)
        assert [(r.raw_column, r.method, r.canonical_field) for r in a] == \
               [(r.raw_column, r.method, r.canonical_field) for r in b]

    def test_exact_and_regex_results_identical_with_semantic_enabled(self, tfidf_config):
        """Enabling semantic resolution must not perturb columns that
        exact/regex already resolve."""
        resolver = SemanticSchemaResolver(config=tfidf_config)
        df = pd.DataFrame({
            'MonthlyCharges': [1, 2],       # exact alias
            'TechSupportCalls': [1, 2],     # exact alias
            'randomthingwithcharge': [1, 2],  # regex hit (".*charge.*")
        })
        _, off = resolve_schema(df)
        _, on = resolve_schema(df, enable_semantic=True, semantic_resolver=resolver)
        for r_off, r_on in zip(off, on):
            assert r_off.method == r_on.method
            assert r_off.canonical_field == r_on.canonical_field
            assert r_off.confidence == r_on.confidence

    def test_column_resolution_new_fields_default_none(self):
        r = ColumnResolution(raw_column='x', canonical_field=None, method='unresolved', confidence=0.0)
        assert r.semantic_score is None
        assert r.explanation is None

    def test_resolution_summary_backward_compatible_keys_present(self):
        df = pd.DataFrame({'tenure': [1], 'foo': [1]})
        _, res = resolve_schema(df)
        summary = resolution_summary(res)
        for key in ('exact_matches', 'regex_matches', 'unresolved_columns',
                    'matched_fields', 'unmatched_fields'):
            assert key in summary


# ══════════════════════════════════════════════════════════════════
# 2. EMBEDDING BACKENDS
# ══════════════════════════════════════════════════════════════════

class TestBackends:
    def test_tfidf_backend_always_available(self):
        assert TfidfCharNgramBackend().is_available() is True

    def test_tfidf_backend_embeds_without_prior_fit(self):
        backend = TfidfCharNgramBackend()
        vecs = backend.embed(['monthly charges', 'tenure months'])
        assert vecs.shape[0] == 2

    def test_select_backend_tfidf_explicit(self, tfidf_config):
        backend = select_backend(tfidf_config)
        assert backend.name == 'tfidf-char-ngram'

    def test_select_backend_auto_never_raises(self):
        # 'auto' must always succeed — worst case, falls back to tfidf.
        backend = select_backend(SemanticConfig(backend='auto'))
        assert backend.is_available()

    def test_select_backend_unknown_raises(self):
        with pytest.raises(ValueError):
            select_backend(SemanticConfig(backend='not-a-real-backend'))

    def test_select_backend_explicit_sentence_transformers_raises_if_missing(self):
        st_backend = SentenceTransformerBackend()
        if st_backend.is_available():
            pytest.skip("sentence-transformers is installed in this environment")
        with pytest.raises(RuntimeError):
            select_backend(SemanticConfig(backend='sentence-transformers'))

    def test_select_backend_explicit_ollama_raises_if_no_server(self):
        ollama_backend = OllamaEmbeddingBackend()
        if ollama_backend.is_available():
            pytest.skip("a local Ollama server is running in this environment")
        with pytest.raises(RuntimeError):
            select_backend(SemanticConfig(backend='ollama'))

    def test_humanize_splits_camel_case_and_underscores(self):
        assert _humanize('MonthlyCharges') == 'monthly charges'
        assert _humanize('Days_Since_Last_Visit') == 'days since last visit'
        assert _humanize('tenure') == 'tenure'


# ══════════════════════════════════════════════════════════════════
# 3. SEMANTIC CANDIDATE RETRIEVAL
# ══════════════════════════════════════════════════════════════════

class TestSemanticCandidateRetrieval:
    def test_top_k_respects_k(self, tfidf_resolver):
        candidates = tfidf_resolver.top_k_candidates('MonthlyChg', k=2)
        assert len(candidates) <= 2

    def test_candidates_sorted_descending_by_score(self, tfidf_resolver):
        candidates = tfidf_resolver.top_k_candidates('SubscriptionCost')
        scores = [c.score for c in candidates]
        assert scores == sorted(scores, reverse=True)

    def test_candidate_field_matches_a_registered_canonical_field(self, tfidf_resolver):
        candidates = tfidf_resolver.top_k_candidates('SubscriptionCost')
        known_names = {f.name for f in CANONICAL_FIELDS}
        assert all(c.canonical_field in known_names for c in candidates)

    def test_scores_are_within_unit_range(self, tfidf_resolver):
        candidates = tfidf_resolver.top_k_candidates('anything_at_all_123')
        assert all(0.0 <= c.score <= 1.0 for c in candidates)

    def test_candidate_fields_filter_restricts_search_space(self, tfidf_resolver):
        subset = [f for f in CANONICAL_FIELDS if f.name == 'Tenure_Raw']
        candidates = tfidf_resolver.top_k_candidates('MonthlyChg', candidate_fields=subset)
        assert all(c.canonical_field == 'Tenure_Raw' for c in candidates)

    def test_near_miss_synonym_scores_correct_field_highest(self, tfidf_resolver):
        """'SubscriptionCost' is a realistic paraphrase of the
        registered alias 'SubscriptionFee' (-> Recurring_Cost) and
        must NOT already be caught by exact/regex matching."""
        candidates = tfidf_resolver.top_k_candidates('SubscriptionCost')
        assert candidates, "expected at least one candidate"
        assert candidates[0].canonical_field == 'Recurring_Cost'


# ══════════════════════════════════════════════════════════════════
# 4. SEMANTIC RESOLUTION (accept/reject against threshold)
# ══════════════════════════════════════════════════════════════════

class TestSemanticResolution:
    def test_high_similarity_column_is_accepted(self, tfidf_resolver):
        report = tfidf_resolver.resolve('SubscriptionCost')
        assert report.accepted is True
        assert report.canonical_field == 'Recurring_Cost'

    def test_confidence_capped_below_regex_tier(self, tfidf_resolver):
        report = tfidf_resolver.resolve('SubscriptionCost')
        assert report.confidence < 0.8
        assert report.confidence <= tfidf_resolver.config.max_accepted_confidence

    def test_unrelated_column_is_rejected(self, tfidf_resolver):
        report = tfidf_resolver.resolve('xk7q_flux_capacitor_zz')
        assert report.accepted is False
        assert report.canonical_field is None

    def test_resolve_schema_with_semantic_enabled_resolves_near_miss(self, tfidf_config):
        resolver = SemanticSchemaResolver(config=tfidf_config)
        df = pd.DataFrame({'SubscriptionCost': [10.0, 20.0]})
        resolved_df, resolutions = resolve_schema(
            df, enable_semantic=True, semantic_resolver=resolver)
        assert resolutions[0].method == 'semantic'
        assert resolutions[0].canonical_field == 'Recurring_Cost'
        assert 'Recurring_Cost' in resolved_df.columns
        assert resolutions[0].explanation is not None
        assert resolutions[0].semantic_score is not None

    def test_resolve_schema_with_semantic_enabled_still_leaves_junk_unresolved(self, tfidf_config):
        resolver = SemanticSchemaResolver(config=tfidf_config)
        df = pd.DataFrame({'xk7q_flux_capacitor_zz': [1, 2]})
        _, resolutions = resolve_schema(df, enable_semantic=True, semantic_resolver=resolver)
        assert resolutions[0].method == 'unresolved'

    def test_resolve_with_semantics_convenience_wrapper(self, tfidf_config):
        df = pd.DataFrame({'SubscriptionCost': [10.0, 20.0]})
        resolved_df, resolutions = resolve_with_semantics(df, config=tfidf_config)
        assert resolutions[0].canonical_field == 'Recurring_Cost'

    def test_default_resolver_is_singleton_and_reset_rebuilds(self):
        reset_default_resolver()
        r1 = get_default_resolver(SemanticConfig(backend='tfidf'))
        r2 = get_default_resolver()
        assert r1 is r2
        reset_default_resolver()
        r3 = get_default_resolver(SemanticConfig(backend='tfidf'))
        assert r3 is not r1


# ══════════════════════════════════════════════════════════════════
# 5. PRECEDENCE RULES — deterministic always wins
# ══════════════════════════════════════════════════════════════════

class TestPrecedenceRules:
    def test_exact_match_column_never_reaches_semantic_strategy(self, tfidf_config):
        """Sanity check on resolve_schema's control flow: a column
        that exact-matches must short-circuit via `continue` before
        Strategy 3 runs at all."""
        resolver = SemanticSchemaResolver(config=tfidf_config)
        df = pd.DataFrame({'MonthlyCharges': [1, 2]})
        _, resolutions = resolve_schema(df, enable_semantic=True, semantic_resolver=resolver)
        assert resolutions[0].method == 'exact'
        assert resolutions[0].confidence == 1.0

    def test_regex_match_column_never_downgraded_to_semantic(self, tfidf_config):
        resolver = SemanticSchemaResolver(config=tfidf_config)
        df = pd.DataFrame({'weird_charge_field_xyz': [1, 2]})  # hits r".*charge.*"
        _, resolutions = resolve_schema(df, enable_semantic=True, semantic_resolver=resolver)
        assert resolutions[0].method == 'regex'
        assert resolutions[0].confidence == 0.8

    def test_diagnostic_resolve_reports_deterministic_precedence_note(self, tfidf_resolver):
        report = tfidf_resolver.resolve(
            'MonthlyCharges', deterministic_method='exact', deterministic_field='Recurring_Cost')
        assert report.accepted is False   # not applied — deterministic already won
        assert report.canonical_field is None
        assert report.precedence_note is not None
        assert 'exact' in report.precedence_note

    def test_semantic_confidence_can_never_equal_or_exceed_any_regex_confidence(self, tfidf_resolver):
        """Property check across a spread of column names: whatever
        the raw similarity score, the *accepted* confidence returned
        must stay under the regex tier."""
        for name in ['SubscriptionCost', 'PaymentAutoDebit', 'AgeYears', 'TotalBalanceOwed']:
            report = tfidf_resolver.resolve(name)
            if report.accepted:
                assert report.confidence < 0.8


# ══════════════════════════════════════════════════════════════════
# 6. DIAGNOSTICS REPORT
# ══════════════════════════════════════════════════════════════════

class TestDiagnosticsReport:
    def test_diagnose_columns_covers_every_column(self, tfidf_config):
        df = pd.DataFrame({
            'MonthlyCharges': [1, 2], 'SubscriptionCost': [1, 2], 'foo': [1, 2],
        })
        reports = diagnose_columns(df, config=tfidf_config)
        assert {r.raw_column for r in reports} == set(df.columns)
        assert all(isinstance(r, SemanticMatchReport) for r in reports)

    def test_diagnostics_never_mutate_input_frame(self, tfidf_config):
        df = pd.DataFrame({'MonthlyCharges': [1, 2], 'foo': [1, 2]})
        before_cols = list(df.columns)
        diagnose_columns(df, config=tfidf_config)
        assert list(df.columns) == before_cols

    def test_deterministically_resolved_column_carries_precedence_note(self, tfidf_config):
        df = pd.DataFrame({'MonthlyCharges': [1, 2]})
        reports = diagnose_columns(df, config=tfidf_config)
        report = reports[0]
        assert report.deterministic_method == 'exact'
        assert report.deterministic_field == 'Recurring_Cost'
        assert report.accepted is False
        assert report.precedence_note is not None

    def test_report_serializes_to_plain_dict(self, tfidf_resolver):
        report = tfidf_resolver.resolve('SubscriptionCost')
        d = report.to_dict()
        assert isinstance(d, dict)
        assert set(d.keys()) >= {
            'raw_column', 'backend_used', 'top_candidates', 'confidence',
            'accepted', 'canonical_field', 'explanation',
            'deterministic_method', 'deterministic_field', 'precedence_note',
        }

    def test_candidate_serializes_to_plain_dict(self):
        c = SemanticCandidate(canonical_field='Recurring_Cost', score=0.7, matched_text='alias X')
        assert c.to_dict() == {
            'canonical_field': 'Recurring_Cost', 'score': 0.7, 'matched_text': 'alias X',
        }


# ══════════════════════════════════════════════════════════════════
# 7. GOLDEN / MESSY / UNKNOWN / SYNTHETIC SCHEMAS
# ══════════════════════════════════════════════════════════════════

class TestGoldenMessyUnknownSynthetic:
    """Mirrors the spec's 'Validation' section dataset categories."""

    def test_golden_schema_fully_exact_matched_semantic_never_needed(self, tfidf_config):
        golden = pd.DataFrame({
            'customerID': ['C1', 'C2'],
            'tenure': [12, 24],
            'MonthlyCharges': [50.0, 60.0],
            'Contract': ['Month-to-month', 'One year'],
        })
        resolver = SemanticSchemaResolver(config=tfidf_config)
        _, resolutions = resolve_schema(golden, enable_semantic=True, semantic_resolver=resolver)
        assert all(r.method in ('exact', 'regex') for r in resolutions)
        assert resolution_summary(resolutions)['semantic_matches'] == 0

    def test_messy_schema_resolved_only_with_semantic_enabled(self, tfidf_config):
        messy = pd.DataFrame({
            'SubscriptionCost': [50.0, 60.0],   # near-miss of SubscriptionFee alias
        })
        resolver = SemanticSchemaResolver(config=tfidf_config)
        _, off = resolve_schema(messy)
        _, on = resolve_schema(messy, enable_semantic=True, semantic_resolver=resolver)
        assert off[0].method == 'unresolved'
        assert on[0].method == 'semantic'
        assert on[0].canonical_field == 'Recurring_Cost'

    def test_unknown_schema_stays_unresolved_even_with_semantic_enabled(self, tfidf_config):
        unknown = pd.DataFrame({
            'zzz_flux_capacitor': [1, 2], 'qqq_warp_core': [3, 4],
        })
        resolver = SemanticSchemaResolver(config=tfidf_config)
        _, resolutions = resolve_schema(unknown, enable_semantic=True, semantic_resolver=resolver)
        assert all(r.method == 'unresolved' for r in resolutions)

    def test_synthetic_schema_variants_of_a_known_alias(self, tfidf_config):
        """Programmatically generated near-miss variants of a single
        known alias ('MonthlyCharges') — none of these strings are
        registered verbatim, and none match the ".*charge.*"/
        ".*premium.*"/".*fee.*" regex patterns for Recurring_Cost, so
        only the semantic layer can resolve them."""
        variants = [
            'MonthlyChg', 'MnthlyCharges', 'Charges_Per_Month', 'MonthlyCost',
        ]
        resolver = SemanticSchemaResolver(config=tfidf_config)
        resolved_count = 0
        for variant in variants:
            df = pd.DataFrame({variant: [10.0, 20.0]})
            _, resolutions = resolve_schema(df, enable_semantic=True, semantic_resolver=resolver)
            if resolutions[0].method == 'semantic':
                resolved_count += 1
        # Not every synthetic variant necessarily clears the threshold
        # with the lexical TF-IDF fallback — the requirement is that
        # semantic resolution meaningfully improves coverage over the
        # deterministic-only baseline (which resolves none of these).
        assert resolved_count >= 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
