import pytest
from universal_churn.business_meaning import BusinessMeaning
from universal_churn.context_validation import ContextValidation, validate_context
from universal_churn.semantic_graph import infer_semantic_knowledge_graph, SemanticKnowledgeGraph

# Helper to create a minimal BusinessMeaning instance
def make_bm(concept, domain, metric, dimension, confidence, tags):
    return BusinessMeaning(
        primary_business_concept=concept,
        secondary_concepts=[],
        domain=domain,
        metric_type=metric,
        customer_dimension=dimension,
        business_category=domain,
        business_tags=tags,
        confidence=confidence,
        reasoning="",
        supporting_features={},
    )

@pytest.fixture
def sample_business_meanings():
    return [
        make_bm("Revenue", "Financial", "Money", "Financial", 0.95, ["revenue", "financial"]),
        make_bm("Cost", "Financial", "Money", "Financial", 0.90, ["cost", "financial"]),
        make_bm("CustomerCount", "Customer", "Count", "Demographic", 0.85, ["customer", "count"]),
        make_bm("Churn", "Risk", "Score", "Risk", 0.80, ["churn", "risk"]),
    ]

def test_semantic_graph_structure(sample_business_meanings):
    # Use a minimal ContextValidation (can be created via validate_context)
    ctx = validate_context(sample_business_meanings)
    graph = infer_semantic_knowledge_graph(sample_business_meanings, ctx)
    # Basic sanity checks
    assert isinstance(graph, SemanticKnowledgeGraph)
    assert graph.node_count == 4
    assert graph.edge_count > 0
    assert 0.0 <= graph.consistency_score <= 1.0
    # Central concept should be one of the node IDs
    assert any(node.node_id == graph.central_concept_id for node in graph.nodes)

def test_determinism(sample_business_meanings):
    ctx = validate_context(sample_business_meanings)
    g1 = infer_semantic_knowledge_graph(sample_business_meanings, ctx)
    g2 = infer_semantic_knowledge_graph(sample_business_meanings, ctx)
    assert g1 == g2

def test_immutability(sample_business_meanings):
    ctx = validate_context(sample_business_meanings)
    graph = infer_semantic_knowledge_graph(sample_business_meanings, ctx)
    with pytest.raises(AttributeError):
        # Attempt to mutate a frozen dataclass
        graph.node_count = 999
