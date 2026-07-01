"""
universal_churn.semantic_schema
================================
Semantic Schema Intelligence Layer — Version 7, Chunk 1.

Extends (does NOT replace) the deterministic resolver in
schema_resolution.py with a fifth-priority, opt-in strategy:

    1. Exact alias match        (schema_resolution.py, confidence 1.0)
    2. Normalized string match  (folded into (1) via _normalize())
    3. Regex match               (schema_resolution.py, confidence 0.8)
    4. Semantic similarity       (THIS MODULE, confidence < 0.8, opt-in)
    5. Unknown field              (schema_resolution.py, confidence 0.0)

Design invariants (non-negotiable, enforced in code below, not just
by convention):

    - Deterministic behavior always wins. This module is only ever
      consulted by schema_resolution.resolve_semantic_alias() for a
      column that exact + regex matching have already given up on
      (see resolve_schema()'s Strategy 3 block). It has no way to
      override, or even see, a column that was already resolved.
    - A semantic match's confidence is always capped strictly below
      the regex tier (0.8) — SemanticConfig.max_accepted_confidence —
      so even a caller that reads raw ColumnResolution.confidence
      values, ignoring `method` entirely, can never have a semantic
      match outrank a deterministic one.
    - Local models only. No OpenAI (or any other hosted-API) calls.
      Three embedding backends are supported, tried in this order
      under `backend="auto"`:
          1. sentence-transformers  (if installed)
          2. Ollama                  (if a local Ollama server is running)
          3. TF-IDF character n-grams (scikit-learn, always available —
             this project already depends on scikit-learn, so the
             semantic layer works out of the box with ZERO new
             mandatory dependencies and no model download).
      The TF-IDF fallback is not a "true" meaning-level embedding —
      it is provided so the semantic layer degrades gracefully to a
      lexical/sub-word similarity signal (still useful for typos,
      re-orderings, and concatenation variants) rather than silently
      doing nothing when no embedding model is available.
    - Enabling this layer never changes Version 6 behavior by itself.
      Nothing in this module is imported anywhere until
      schema_resolution.resolve_schema(..., enable_semantic=True) is
      used, and schema_resolution.py imports it lazily, inside a
      function body, specifically so that importing schema_resolution
      (or any module that imports it) never pulls this module — or
      its optional dependencies — in.

Routing (informational — mirrors the Chunk 1 spec)
---------------------------------------------------
    Schema Resolution
        -> Alias Resolver        (schema_resolution: exact + regex)
        -> Semantic Resolver     (this module, opt-in)
        -> Canonical Registry    (schema_resolution.CANONICAL_FIELDS)
        -> Feature Pipeline      (feature_engineering.py, unchanged)

Nothing downstream of schema_resolution.resolve_schema() needs to
change: concepts.py, coverage.py, concept_confidence.py, and
routing.py already read ColumnResolution.confidence generically,
regardless of which strategy produced it.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np

from .schema_resolution import CanonicalField, CANONICAL_FIELDS


# ══════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class SemanticConfig:
    """
    All tunables for the semantic layer live here — nothing else in
    this module reads an unconfigurable constant for behavior that a
    caller might reasonably want to change.
    """
    confidence_threshold: float = 0.55       # minimum similarity to accept a match
    top_k: int = 3                           # candidates retained per column
    max_accepted_confidence: float = 0.79    # hard ceiling, below the regex tier (0.8)
    backend: str = "auto"                    # 'auto' | 'sentence-transformers' | 'ollama' | 'tfidf'
    sentence_transformer_model: str = "all-MiniLM-L6-v2"
    ollama_model: str = "nomic-embed-text"
    ollama_host: str = "http://localhost:11434"


# ══════════════════════════════════════════════════════════════════
# EMBEDDING BACKENDS — local sentence embedding support
# ══════════════════════════════════════════════════════════════════
# Every backend implements the same tiny interface: is_available(),
# an optional fit() (only meaningful for the corpus-fitted TF-IDF
# fallback), and embed(). SemanticSchemaResolver is backend-agnostic
# beyond that.

class EmbeddingBackend(ABC):
    name: str = "backend"

    @abstractmethod
    def is_available(self) -> bool:
        """Whether this backend can be used right now, in this
        environment, without raising."""

    def fit(self, corpus_texts: list[str]) -> None:
        """Optional: some backends (TF-IDF) need to see the corpus
        once before embed() can be called. No-op for embedding models
        with a fixed, pre-trained vector space."""
        return None

    @abstractmethod
    def embed(self, texts: list[str]) -> np.ndarray:
        """Return an (n_texts, dim) array. Rows do not need to be
        globally comparable across different backend instances — only
        within a single SemanticSchemaResolver's corpus + queries,
        which always share one backend instance."""


class SentenceTransformerBackend(EmbeddingBackend):
    """
    Local sentence-transformers backend. Nothing here calls out to a
    hosted API — SentenceTransformer downloads (once, on first use,
    cached locally by the library) and then runs entirely on-device.
    """
    name = "sentence-transformers"

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or "all-MiniLM-L6-v2"
        self._model = None

    def is_available(self) -> bool:
        try:
            import sentence_transformers  # noqa: F401
            return True
        except ImportError:
            return False

    def embed(self, texts: list[str]) -> np.ndarray:
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        vectors = self._model.encode(list(texts), normalize_embeddings=True)
        return np.asarray(vectors, dtype=float)


class OllamaEmbeddingBackend(EmbeddingBackend):
    """
    Local Ollama embedding backend. Talks only to a local Ollama
    server (default http://localhost:11434) — this is a local-model
    runtime, not a hosted API, and is treated as such: is_available()
    fails closed (returns False) if no local server responds.
    """
    name = "ollama"

    def __init__(self, model_name: str | None = None, host: str | None = None):
        self.model_name = model_name or "nomic-embed-text"
        self.host = (host or "http://localhost:11434").rstrip("/")

    def is_available(self) -> bool:
        try:
            import requests
            resp = requests.get(f"{self.host}/api/tags", timeout=0.5)
            return resp.status_code == 200
        except Exception:
            return False

    def embed(self, texts: list[str]) -> np.ndarray:
        import requests
        vectors = []
        for text in texts:
            resp = requests.post(
                f"{self.host}/api/embeddings",
                json={"model": self.model_name, "prompt": text},
                timeout=10,
            )
            resp.raise_for_status()
            vectors.append(resp.json()["embedding"])
        return np.asarray(vectors, dtype=float)


class TfidfCharNgramBackend(EmbeddingBackend):
    """
    Zero-dependency, always-available fallback.

    Uses scikit-learn's TfidfVectorizer over character n-grams
    (2-4 chars, word-boundary-aware) instead of a real embedding
    model. This is deliberately NOT a semantic/meaning-level
    representation — it is a sub-word lexical similarity signal.
    It is included so that:
      - the semantic layer is fully local and works with the
        project's EXISTING dependencies (scikit-learn is already
        required elsewhere in this codebase) — no new installs,
        no model download, no network access required;
      - typo'd, re-ordered, concatenated, or abbreviated column
        names (e.g. "SubscriptonCost", "cost_recurring",
        "RecurCost") still get partial credit even when neither a
        real embedding model nor Ollama is available;
      - resolve_semantic_alias() never has to return None purely
        because no optional dependency happened to be installed.

    When sentence-transformers or Ollama ARE available, `backend=
    "auto"` prefers them, since they capture actual meaning (e.g.
    "MonthlyPremium" ~ "recurring cost") rather than just character
    overlap.
    """
    name = "tfidf-char-ngram"

    def __init__(self):
        self._vectorizer = None

    def is_available(self) -> bool:
        return True

    def fit(self, corpus_texts: list[str]) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer
        self._vectorizer = TfidfVectorizer(
            analyzer="char_wb", ngram_range=(2, 4), min_df=1, lowercase=True,
        )
        self._vectorizer.fit(corpus_texts)

    def embed(self, texts: list[str]) -> np.ndarray:
        if self._vectorizer is None:
            # Nothing fit yet (e.g. called standalone) — fit on this
            # call's own texts so embed() never hard-fails.
            self.fit(list(texts))
        return np.asarray(self._vectorizer.transform(list(texts)).todense())


def select_backend(config: SemanticConfig) -> EmbeddingBackend:
    """
    Resolve `config.backend` to a concrete, available EmbeddingBackend.
    Raises RuntimeError only if a SPECIFIC backend was requested and
    is not available — "auto" always succeeds, because the TF-IDF
    fallback has no external dependency and is_available() is always
    True.
    """
    if config.backend == "sentence-transformers":
        candidate = SentenceTransformerBackend(config.sentence_transformer_model)
        if not candidate.is_available():
            raise RuntimeError(
                "backend='sentence-transformers' was requested but the "
                "'sentence-transformers' package is not installed. Install "
                "it, or use backend='auto' / 'tfidf' instead."
            )
        return candidate

    if config.backend == "ollama":
        candidate = OllamaEmbeddingBackend(config.ollama_model, config.ollama_host)
        if not candidate.is_available():
            raise RuntimeError(
                f"backend='ollama' was requested but no Ollama server "
                f"responded at {config.ollama_host}. Start Ollama, or use "
                f"backend='auto' / 'tfidf' instead."
            )
        return candidate

    if config.backend == "tfidf":
        return TfidfCharNgramBackend()

    if config.backend != "auto":
        raise ValueError(
            f"Unknown backend '{config.backend}'. Expected one of: "
            f"'auto', 'sentence-transformers', 'ollama', 'tfidf'."
        )

    # ── auto: prefer a real local embedding model, fall back to TF-IDF ──
    for candidate in (
        SentenceTransformerBackend(config.sentence_transformer_model),
        OllamaEmbeddingBackend(config.ollama_model, config.ollama_host),
    ):
        if candidate.is_available():
            return candidate
    return TfidfCharNgramBackend()


# ══════════════════════════════════════════════════════════════════
# TEXT NORMALIZATION FOR EMBEDDING
# ══════════════════════════════════════════════════════════════════

def _humanize(identifier: str) -> str:
    """
    Turn a raw/alias column identifier into natural-language-ish text
    so embedding backends (especially real sentence embedding models)
    see something closer to a phrase than a code token.

        'MonthlyCharges'          -> 'monthly charges'
        'Days_Since_Last_Visit'   -> 'days since last visit'
        'NumOfProducts'           -> 'num of products'
    """
    s = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', identifier)   # camelCase split
    s = re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])', ' ', s)          # ABCDef -> ABC Def
    s = s.replace('_', ' ').replace('-', ' ')
    s = re.sub(r'\s+', ' ', s).strip().lower()
    return s or identifier.lower()


# ══════════════════════════════════════════════════════════════════
# CANDIDATE / REPORT DATA MODEL
# ══════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class SemanticCandidate:
    """One scored candidate canonical field for a raw column."""
    canonical_field: str
    score: float
    matched_text: str          # which alias/description/name produced this score
    field_description: str = ""

    def to_dict(self) -> dict:
        return {
            "canonical_field": self.canonical_field,
            "score": round(self.score, 4),
            "matched_text": self.matched_text,
        }


@dataclass
class SemanticMatchReport:
    """
    Full diagnostic record for one column — this IS the "semantic
    match report" deliverable: confidence, top candidate, why it
    matched, and (when relevant) why a deterministic alias won.
    """
    raw_column: str
    backend_used: str
    top_candidates: list[SemanticCandidate] = field(default_factory=list)
    confidence: float = 0.0             # capped, "would-be-applied" confidence
    accepted: bool = False              # True iff this report's match would be applied
    canonical_field: str | None = None  # set only if accepted
    explanation: str = ""               # "why it matched"
    deterministic_method: str | None = None   # what schema_resolution already chose, if anything
    deterministic_field: str | None = None
    precedence_note: str | None = None  # "why deterministic alias won", when applicable

    def to_dict(self) -> dict:
        return {
            "raw_column": self.raw_column,
            "backend_used": self.backend_used,
            "top_candidates": [c.to_dict() for c in self.top_candidates],
            "confidence": round(self.confidence, 4),
            "accepted": self.accepted,
            "canonical_field": self.canonical_field,
            "explanation": self.explanation,
            "deterministic_method": self.deterministic_method,
            "deterministic_field": self.deterministic_field,
            "precedence_note": self.precedence_note,
        }


# ══════════════════════════════════════════════════════════════════
# THE RESOLVER
# ══════════════════════════════════════════════════════════════════

class SemanticSchemaResolver:
    """
    Embeds every canonical field's name, aliases, and description once
    (the "corpus"), then scores an arbitrary raw column name against
    that corpus by cosine similarity. Top-k candidates and a
    human-readable explanation are always available via `resolve()`,
    regardless of whether the top candidate clears the acceptance
    threshold.
    """

    def __init__(
        self,
        canonical_fields: list[CanonicalField] | None = None,
        config: SemanticConfig | None = None,
        backend: EmbeddingBackend | None = None,
    ):
        self.canonical_fields = list(canonical_fields or CANONICAL_FIELDS)
        self.config = config or SemanticConfig()
        self.backend = backend or select_backend(self.config)

        self._corpus_texts: list[str] = []
        self._corpus_fields: list[str] = []
        self._corpus_sources: list[str] = []
        self._build_corpus()

        self.backend.fit(self._corpus_texts)
        self._corpus_vectors = (
            self.backend.embed(self._corpus_texts) if self._corpus_texts else None
        )
        self._by_name: dict[str, CanonicalField] = {
            f.name: f for f in self.canonical_fields
        }

    # ── corpus construction ─────────────────────────────────────

    def _build_corpus(self) -> None:
        for cf in self.canonical_fields:
            self._corpus_texts.append(_humanize(cf.name))
            self._corpus_fields.append(cf.name)
            self._corpus_sources.append(f"canonical field name '{cf.name}'")

            for alias in cf.exact_aliases:
                self._corpus_texts.append(_humanize(alias))
                self._corpus_fields.append(cf.name)
                self._corpus_sources.append(f"known alias '{alias}'")

            if cf.description:
                self._corpus_texts.append(cf.description)
                self._corpus_fields.append(cf.name)
                self._corpus_sources.append("field description")

    # ── candidate retrieval ─────────────────────────────────────

    def top_k_candidates(
        self,
        raw_column: str,
        k: int | None = None,
        candidate_fields: list[CanonicalField] | None = None,
    ) -> list[SemanticCandidate]:
        """
        Score `raw_column` against every canonical field in the
        corpus (or, if `candidate_fields` is given, only those),
        returning the top-k by best-matching-alias cosine similarity.
        """
        if not self._corpus_texts or self._corpus_vectors is None:
            return []

        k = k or self.config.top_k
        allowed_names = (
            {f.name for f in candidate_fields} if candidate_fields is not None else None
        )

        query_text = _humanize(raw_column)
        query_vec = self.backend.embed([query_text])

        from sklearn.metrics.pairwise import cosine_similarity
        sims = cosine_similarity(query_vec, self._corpus_vectors)[0]

        best: dict[str, tuple[float, str]] = {}
        for score, field_name, source in zip(sims, self._corpus_fields, self._corpus_sources):
            if allowed_names is not None and field_name not in allowed_names:
                continue
            score = max(0.0, float(score))   # clip any backend's negative cosine noise
            if field_name not in best or score > best[field_name][0]:
                best[field_name] = (score, source)

        ranked = sorted(best.items(), key=lambda kv: kv[1][0], reverse=True)
        return [
            SemanticCandidate(
                canonical_field=field_name,
                score=score,
                matched_text=source,
                field_description=self._by_name[field_name].description,
            )
            for field_name, (score, source) in ranked[:k]
        ]

    # ── full resolution + report ────────────────────────────────

    def resolve(
        self,
        raw_column: str,
        deterministic_method: str | None = None,
        deterministic_field: str | None = None,
        candidate_fields: list[CanonicalField] | None = None,
    ) -> SemanticMatchReport:
        """
        Produce a full SemanticMatchReport for `raw_column`.

        `deterministic_method` / `deterministic_field`: pass these
        in (from schema_resolution's exact/regex pass) when you want
        the report to explain WHY a deterministic match takes
        precedence, even though this call still computes and returns
        the semantic candidates for diagnostic visibility. When both
        are None (the default — used by resolve_semantic_alias(),
        which is only ever called for already-unresolved columns),
        the semantic match, if it clears the threshold, is `accepted`.
        """
        candidates = self.top_k_candidates(raw_column, candidate_fields=candidate_fields)
        top = candidates[0] if candidates else None
        raw_score = top.score if top else 0.0

        deterministic_present = deterministic_method not in (None, 'unresolved')
        clears_threshold = bool(top) and raw_score >= self.config.confidence_threshold
        accepted = clears_threshold and not deterministic_present
        capped_score = min(raw_score, self.config.max_accepted_confidence)

        explanation = self._explain(raw_column, candidates)

        precedence_note = None
        if deterministic_present:
            precedence_note = (
                f"'{raw_column}' was already resolved by the deterministic "
                f"'{deterministic_method}' strategy to '{deterministic_field}'. "
                f"Exact and regex matches always outrank semantic similarity "
                f"by design, so this semantic result is reported for "
                f"diagnostics only and was not applied."
            )
        elif not clears_threshold and top:
            precedence_note = (
                f"Best semantic candidate '{top.canonical_field}' scored "
                f"{raw_score:.3f}, below the acceptance threshold "
                f"({self.config.confidence_threshold:.2f}); column left "
                f"unresolved rather than risk a low-quality rename."
            )
        elif not top:
            precedence_note = "No canonical field corpus was available to compare against."

        return SemanticMatchReport(
            raw_column=raw_column,
            backend_used=self.backend.name,
            top_candidates=candidates,
            confidence=capped_score if accepted else raw_score,
            accepted=accepted,
            canonical_field=top.canonical_field if accepted else None,
            explanation=explanation,
            deterministic_method=deterministic_method,
            deterministic_field=deterministic_field,
            precedence_note=precedence_note,
        )

    def _explain(self, raw_column: str, candidates: list[SemanticCandidate]) -> str:
        if not candidates:
            return f"No semantic candidates were available for '{raw_column}'."
        top = candidates[0]
        msg = (
            f"'{raw_column}' matched {top.matched_text} of canonical field "
            f"'{top.canonical_field}' most closely (backend={self.backend.name}, "
            f"similarity={top.score:.3f})."
        )
        others = [c for c in candidates[1:] if c.score > 0.0]
        if others:
            other_str = ", ".join(f"{c.canonical_field} ({c.score:.2f})" for c in others)
            msg += f" Other candidates considered: {other_str}."
        return msg


# ══════════════════════════════════════════════════════════════════
# PROCESS-WIDE DEFAULT RESOLVER
# ══════════════════════════════════════════════════════════════════
# Building a SemanticSchemaResolver re-embeds the entire canonical
# corpus, which is wasted work if it happens on every single column of
# every single resolve_schema() call. schema_resolution.
# resolve_semantic_alias() reuses this lazily-constructed singleton
# unless a caller supplies their own resolver (e.g. a benchmark
# comparing backends, or a caller who wants a non-default
# SemanticConfig).

_default_resolver: SemanticSchemaResolver | None = None


def get_default_resolver(config: SemanticConfig | None = None) -> SemanticSchemaResolver:
    """Return the process-wide default resolver, building it (or
    rebuilding it, if a non-default config is supplied) on first use."""
    global _default_resolver
    if _default_resolver is None or config is not None:
        _default_resolver = SemanticSchemaResolver(config=config)
    return _default_resolver


def reset_default_resolver() -> None:
    """Test/benchmark helper — forces the next get_default_resolver()
    call to rebuild from scratch (e.g. after swapping backends)."""
    global _default_resolver
    _default_resolver = None


# ══════════════════════════════════════════════════════════════════
# DIAGNOSTICS — full "semantic match report" across every column
# ══════════════════════════════════════════════════════════════════

def diagnose_columns(
    df,
    config: SemanticConfig | None = None,
    resolver: SemanticSchemaResolver | None = None,
) -> list[SemanticMatchReport]:
    """
    Purely observational: for EVERY column in `df`, report what the
    deterministic resolver (exact/regex) already decided AND what the
    semantic resolver would say, regardless of whether semantic
    resolution is actually enabled anywhere else. This is the audit
    trail the Chunk 1 spec asks for — confidence, top candidate, why
    it matched, and why a deterministic alias won when applicable.

    Does not mutate `df`, does not change resolve_schema()'s default
    (semantic-off) behavior, and is safe to run on any DataFrame at
    any time.
    """
    from .schema_resolution import resolve_schema as _resolve_schema  # local import: no cycle

    active_resolver = resolver or get_default_resolver(config)
    _, deterministic_resolutions = _resolve_schema(df)  # semantic OFF: pure exact+regex pass
    by_col = {r.raw_column: r for r in deterministic_resolutions}

    reports = []
    for raw_col in df.columns:
        det = by_col.get(raw_col)
        det_method = det.method if det else None
        det_field = det.canonical_field if det else None
        reports.append(active_resolver.resolve(
            raw_col, deterministic_method=det_method, deterministic_field=det_field,
        ))
    return reports


def print_semantic_report(reports: list[SemanticMatchReport]) -> None:
    sep = "─" * 88
    print(f"\n{sep}\n  SEMANTIC SCHEMA MATCH REPORT\n{sep}")
    for r in reports:
        if r.deterministic_method not in (None, 'unresolved'):
            status = f"SUPPRESSED (by {r.deterministic_method})"
        elif r.accepted:
            status = "APPLIED"
        elif r.top_candidates:
            status = "BELOW THRESHOLD"
        else:
            status = "NO CANDIDATES"
        top_name = r.top_candidates[0].canonical_field if r.top_candidates else "—"
        print(f"  {r.raw_column:<28} status={status:<26} top={top_name:<20} conf={r.confidence:.3f}")
        print(f"      {r.explanation}")
        if r.precedence_note:
            print(f"      note: {r.precedence_note}")
    print(sep)


# ══════════════════════════════════════════════════════════════════
# CONVENIENCE WRAPPER — the named Chunk 1 routing flow, one call
# ══════════════════════════════════════════════════════════════════

def resolve_with_semantics(
    df,
    config: SemanticConfig | None = None,
    resolver: SemanticSchemaResolver | None = None,
):
    """
    Schema Resolution -> Alias Resolver -> Semantic Resolver ->
    Canonical Registry -> Feature Pipeline, in one call.

    Thin, explicit wrapper around
    schema_resolution.resolve_schema(df, enable_semantic=True, ...) —
    exists so callers who want the Chunk 1 behavior don't need to
    know resolve_schema()'s keyword arguments. Equivalent to:

        resolve_schema(df, enable_semantic=True, semantic_resolver=resolver)
    """
    from .schema_resolution import resolve_schema
    active_resolver = resolver or get_default_resolver(config)
    return resolve_schema(df, enable_semantic=True, semantic_resolver=active_resolver)
