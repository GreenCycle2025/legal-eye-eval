from authority_expectations_v2 import validate


def _bundle(anchor, quote="", statute_refs=None):
    return {
        "anchor_label": anchor,
        "anchor_quote": quote,
        "statute_refs": statute_refs or [],
    }


def test_product_liability_rejects_unrelated_authority():
    result = validate(
        "אחריות יצרן למוצר פגום",
        "torts",
        _bundle("פקודת הניתוב", "הוראות בדבר ניתוב"),
    )
    assert result["strict_domain_ok"] is True
    assert result["strict_authority_ok"] is False


def test_product_liability_accepts_primary_statute():
    result = validate(
        "אחריות יצרן למוצר פגום",
        "torts",
        _bundle('חוק האחריות למוצרים פגומים, התש"ם-1980'),
    )
    assert result["strict_domain_ok"] is True
    assert result["strict_authority_ok"] is True


def test_constructive_dismissal_rejects_daka_case():
    result = validate(
        "התפטרות בדין מפוטר",
        "labor",
        _bundle('ע"א 2781/93', "דעקה בית חולים כרמל אוטונומיה"),
    )
    assert result["strict_authority_ok"] is False


def test_exact_primary_authority_can_cover_missing_domain_tag():
    result = validate(
        "שעות עבודה ומנוחה לפי החוק",
        None,
        _bundle('חוק שעות עבודה ומנוחה, התשי"א-1951'),
    )
    assert result["strict_authority_ok"] is True
    assert result["strict_domain_ok"] is True


def test_conflicting_explicit_domain_still_fails_closed():
    result = validate(
        "שעות עבודה ומנוחה לפי החוק",
        "criminal",
        _bundle('חוק שעות עבודה ומנוחה, התשי"א-1951'),
    )
    assert result["strict_authority_ok"] is True
    assert result["strict_domain_ok"] is False


def test_hgraph_promotion_accepts_verified_primary_statute_below_cluster_gate():
    from eval_graph_arguments import _hgraph_promoted

    assert _hgraph_promoted({
        "anchor_quote": "סעיף חוק מאומת",
        "cluster_score": 0.20,
        "coverage": 0.05,
        "statute_evidence_verified": True,
    }) is True


def test_hgraph_promotion_does_not_bypass_cluster_gate_without_verified_statute():
    from eval_graph_arguments import _hgraph_promoted

    assert _hgraph_promoted({
        "anchor_quote": "מקור כלשהו",
        "cluster_score": 0.20,
        "coverage": 0.05,
        "statute_evidence_verified": False,
    }) is False
