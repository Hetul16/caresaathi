"""Completeness of a document decides whether the omission catch may raise anything (invariant 10)."""
import pytest

from app.safety.reconcile import document_completeness


def test_empty_page_is_incomplete():
    assert document_completeness(["Page 1 of 2\nTab A 5 mg", "  "]) == "incomplete"


def test_fewer_pages_than_the_marker_says_is_incomplete():
    assert document_completeness(["DISCHARGE SUMMARY\nPage 1 of 3\nTab A 5 mg"]) == "incomplete"


def test_all_pages_present_with_a_marker_is_complete():
    assert document_completeness(["Page 1 of 2\nTab A 5 mg", "Page 2 of 2\nReview in two weeks"]) == "complete"


def test_a_single_page_marked_one_of_one_is_complete():
    assert document_completeness(["Page 1 of 1\nTab A 5 mg"]) == "complete"


def test_no_marker_means_unknown_not_complete():
    # We cannot tell that nothing is missing, so the omission catch must stay quiet.
    assert document_completeness(["Tab A 5 mg 1-0-1\nReview in two weeks"]) == "unknown"


def test_no_pages_is_incomplete():
    assert document_completeness([]) == "incomplete"


@pytest.mark.parametrize("marker", ["page 1 of 1", "Page 1/1", "PAGE 1 OF 1"])
def test_marker_spellings(marker):
    assert document_completeness([f"{marker}\nTab A 5 mg"]) == "complete"
