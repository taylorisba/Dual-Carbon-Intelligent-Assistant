from datetime import date, timedelta

import pytest

pytest.importorskip("sqlmodel")
pytest.importorskip("pydantic_settings")

from app.services.retrieval_service import RetrievalService



def test_compute_final_score_uses_weighted_formula():
    score = RetrievalService.compute_final_score(0.8, 0.6, 1.0, 0.4)
    assert round(score, 4) == round(0.40 * 0.8 + 0.35 * 0.6 + 0.15 * 1.0 + 0.10 * 0.4, 4)



def test_region_and_freshness_score():
    assert RetrievalService.compute_region_score("江苏省", "江苏省", None, None) == 1.0
    assert RetrievalService.compute_region_score(None, None, None, None) == 0.5

    recent_date = date.today() - timedelta(days=100)
    old_date = date.today() - timedelta(days=365 * 6)
    assert RetrievalService.compute_freshness_score(recent_date) > RetrievalService.compute_freshness_score(old_date)
