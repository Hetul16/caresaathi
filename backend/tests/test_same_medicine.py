"""When is a line in a new document a new VERSION of an existing plan item, and when is it a different item?
Merging two brands of one ingredient would hide a possible duplicate, so a different brand is a different item (A8)."""
import pytest

from app.safety.normalize import brand_key, same_medicine

P = frozenset({"paracetamol"})


def test_a_dose_change_is_the_same_item():
    assert same_medicine("Amlodipine 10 mg", frozenset({"amlodipine"}), "Amlodipine 5 mg", frozenset({"amlodipine"}))


def test_two_brands_of_one_ingredient_are_different_items():
    assert not same_medicine("Paraclear 500", P, "Fevonil 500", P)


def test_a_generic_name_matches_a_brand_of_the_same_ingredient():
    # "Paracetamol 500 mg" names the ingredient itself, so it is the same medicine as the brand beside it.
    assert same_medicine("Paracetamol 500 mg", P, "Paraclear 500", P)


def test_a_longer_generic_name_is_still_the_same_item():
    m = frozenset({"metformin"})
    assert same_medicine("Metformin 500 mg", m, "Metformin Hydrochloride 500 mg", m)


def test_different_ingredient_sets_are_different_items():
    assert not same_medicine("Amlodipine 5 mg", frozenset({"amlodipine"}), "Amlodipine Plus", frozenset({"amlodipine", "atenolol"}))


@pytest.mark.parametrize("a,b", [(frozenset(), frozenset()), (frozenset(), P), (P, frozenset())])
def test_no_ingredients_means_no_match(a, b):
    assert not same_medicine("X 5 mg", a, "X 5 mg", b)


@pytest.mark.parametrize("title,key", [("Amlodipine 10 mg", "amlodipine"), ("Tab Paraclear 500", "paraclear"),
                                       ("Metformin Hydrochloride 500 mg", "metformin hydrochloride"), ("500 mg", "")])
def test_brand_key(title, key):
    assert brand_key(title) == key
