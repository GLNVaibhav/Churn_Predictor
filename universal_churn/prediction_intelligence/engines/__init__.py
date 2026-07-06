"""
universal_churn/prediction_intelligence/engines
══════════════════════════════════════════════════════════════════════
The six engines of the Prediction Intelligence pipeline (Version 8.2):

    prediction_confidence.py   — Module 1: Prediction Confidence
    evidence_engine.py         — Module 2: Evidence Engine
    signal_intelligence.py     — Module 3: Signal Intelligence
    stability_engine.py        — Module 4: Stability Engine
    consistency_engine.py      — Module 5: Consistency Engine
    intelligence_score_engine.py — Module 6: Intelligence Score Engine

Each is a standalone, independently testable
interfaces.PredictionIntelligenceEngine implementation. None of them
import each other directly — orchestrator.py is the only module that
sequences them, per the architecture's "future engines should plug
into the orchestrator without changing external APIs" requirement.
"""
