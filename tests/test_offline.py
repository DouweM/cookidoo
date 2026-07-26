"""Offline unit tests (no network/credentials): URI templates, localization, models."""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))

import pytest

from cookidoo import models
from cookidoo.exceptions import CookidooConfigError
from cookidoo.hal import Link, expand_uri_template, parse_links
from cookidoo.localization import all_markets, get_market


# --- URI template expansion (RFC 6570) ---
def test_simple_var():
    assert (
        expand_uri_template('/recipes/recipe{/lang}/{id}', {'lang': 'es-MX', 'id': 'r1'}) == '/recipes/recipe/es-MX/r1'
    )


def test_query_params():
    out = expand_uri_template('/search{?query,limit}', {'query': 'pasta', 'limit': 5})
    assert out == '/search?query=pasta&limit=5'


def test_query_omits_missing():
    assert expand_uri_template('/x{?a,b}', {'a': '1'}) == '/x?a=1'


def test_explode_list():
    out = expand_uri_template('/s{?tags*}', {'tags': ['a', 'b']})
    assert out == '/s?tags=a&tags=b'


def test_path_expansion_encodes_reserved():
    assert expand_uri_template('{/id}', {'id': 'a b'}) == '/a%20b'


# --- localization ---
def test_market_lookup():
    mx = get_market('mx')
    assert mx.base_url == 'https://cookidoo.mx'
    assert mx.default_language == 'es-MX'


def test_market_alias_country():
    assert get_market('DE').market_code == 'de'


def test_unknown_market():
    with pytest.raises(CookidooConfigError):
        get_market('zz')


def test_all_markets_nonempty():
    assert len(all_markets()) >= 20


def test_language_fallback():
    ch = get_market('ch')
    assert ch.language_for('fr') == 'fr-CH'
    assert ch.language_for(None) == ch.default_language


# --- HAL links ---
def test_parse_links():
    doc = {'_links': {'self': {'href': '/x'}, 'a:b': {'href': '/y{?q}', 'templated': True}}}
    links = parse_links(doc)
    assert links['self'].href == '/x'
    assert links['a:b'].templated is True


def test_link_expand():
    assert Link('/r/{id}', True).expand(id='7') == '/r/7'
    assert Link('/static', False).expand(id='7') == '/static'


# --- models ---
def test_recipe_summary_aliases():
    rs = models.RecipeSummary.model_validate({'id': 'r1', 'title': 'T', 'numberOfRatings': 10, 'totalTime': 900})
    assert rs.number_of_ratings == 10 and rs.total_time == 900


def test_subscription_active_alias():
    s = models.Subscription.model_validate({'subscriptionActive': True, 'type': 'REGULAR', 'autoRenewingActive': True})
    assert s.active and s.auto_renewing and s.type == 'REGULAR'


def test_recipe_nested_parsing():
    r = models.Recipe.model_validate(
        {
            'id': 'r1',
            'title': 'X',
            'recipeIngredientGroups': [
                {'title': 'G', 'recipeIngredients': [{'id': 'i1', 'ingredientNotation': 'salt'}]}
            ],
            'recipeStepGroups': [{'title': 'S', 'recipeSteps': [{'formattedText': 'do it'}]}],
            'thermomixVersions': ['TM6'],
        }
    )
    assert r.recipe_ingredient_groups[0].recipe_ingredients[0].name == 'salt'
    assert r.recipe_step_groups[0].recipe_steps[0].formatted_text == 'do it'
    assert r.thermomix_versions == ['TM6']


def test_extra_fields_preserved():
    rs = models.RecipeSummary.model_validate({'id': 'r1', 'brandNewField': 42})
    assert rs.model_extra is not None
    assert rs.model_extra['brandNewField'] == 42


def test_shopping_list_flat_ingredients():
    sl = models.ShoppingList.model_validate(
        {
            'recipes': [
                {
                    'id': 'r',
                    'recipeIngredientGroups': [
                        {
                            'id': 'i1',
                            'ingredientNotation': 'salt',
                            'isOwned': False,
                            'quantity': {'value': 5},
                            'unitNotation': 'g',
                        }
                    ],
                }
            ],
            'customerRecipes': [],
            'additionalItems': [],
        }
    )
    ings = sl.ingredients()
    assert len(ings) == 1
    assert ings[0].name == 'salt'
    assert ings[0].quantity is not None
    assert ings[0].quantity.value == 5
