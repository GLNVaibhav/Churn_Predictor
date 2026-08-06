"""Cross-sector semantic regression benchmark; does not execute ML prediction."""
from __future__ import annotations

from pathlib import Path
import json
import pandas as pd

from ..intelligence_pipeline import infer_intelligence


_DATASETS = {
    "telecom": "data/telecom/new_telecom_customers.csv",
    "banking": "data/banking/banking_new_customers.csv",
    "retail": "data/ecommerce/ecommerce_new_customers.csv",
    "healthcare": "data/healthcare/healthcare_new_patients.csv",
}


def run_semantic_benchmark(output_path: str = "outputs/diagnostics/cross_sector_semantic_benchmark.json") -> dict:
    """Compare typed semantic outputs using the same pipeline for every sector."""
    report = {}
    for sector, filename in _DATASETS.items():
        path = Path(filename)
        if not path.is_file():
            report[sector] = {"status": "dataset_unavailable"}
            continue
        intelligence = infer_intelligence(pd.read_csv(path).head(250))
        report[sector] = {
            "status": "ok",
            "business_understanding": sum(item.confidence for item in intelligence.business_meanings) / len(intelligence.business_meanings),
            "domain": intelligence.context.dataset_domain,
            "canonical_confidence": intelligence.canonical_mapping.overall_confidence,
            "coverage": intelligence.coverage.summary.overall_coverage,
            "readiness": intelligence.coverage.summary.readiness,
            "selected_pipeline": intelligence.routing.decision.selected_pipeline,
            "routing_confidence": intelligence.routing.decision.confidence,
        }
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
