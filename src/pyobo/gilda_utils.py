# -*- coding: utf-8 -*-

"""PyOBO's Gilda utilities."""

from typing import Iterable, Optional, Tuple, Union

import bioregistry
import gilda.api
import gilda.term
from gilda.generate_terms import filter_out_duplicates
from gilda.grounder import Grounder
from gilda.process import normalize
from tqdm import tqdm

from pyobo import get_id_name_mapping, get_id_synonyms_mapping, get_ids
from pyobo.getters import NoBuild
from pyobo.utils.io import multidict

__all__ = [
    "iter_gilda_prediction_tuples",
    "get_grounder",
    "get_gilda_terms",
]


def iter_gilda_prediction_tuples(
    prefix: str,
    relation: str,
    grounder: Optional[Grounder] = None,
    identifiers_are_names: bool = False,
) -> Iterable[Tuple[str, str, str, str, str, str, str, str, float]]:
    """Iterate over prediction tuples for a given prefix."""
    if grounder is None:
        grounder = gilda.api.grounder
    id_name_mapping = get_id_name_mapping(prefix)
    for identifier, name in tqdm(id_name_mapping.items(), desc=f"Mapping {prefix}"):
        for scored_match in grounder.ground(name):
            target_prefix = scored_match.term.db.lower()
            yield (
                prefix,
                identifier,
                name,
                relation,
                target_prefix,
                normalize_identifier(target_prefix, scored_match.term.id),
                scored_match.term.entry_name,
                "lexical",
                scored_match.score,
            )

    if identifiers_are_names:
        for identifier in tqdm(get_ids(prefix), desc=f"Mapping {prefix} (id as names)"):
            for scored_match in grounder.ground(identifier):
                target_prefix = scored_match.term.db.lower()
                yield (
                    prefix,
                    identifier,
                    identifier,
                    relation,
                    target_prefix,
                    normalize_identifier(target_prefix, scored_match.term.id),
                    scored_match.term.entry_name,
                    "lexical",
                    scored_match.score,
                )


def normalize_identifier(prefix: str, identifier: str) -> str:
    """Normalize the identifier."""
    # TODO in bioregistry.resolve_identifier there is similar code. just combine with that
    banana = bioregistry.get_banana(prefix)
    if banana:
        if not identifier.startswith(banana):
            return f"{banana}:{identifier}"
    elif bioregistry.namespace_in_lui(prefix):
        banana = f"{prefix.upper()}:"
        if not identifier.startswith(banana):
            return f"{banana}{identifier}"
    return identifier


def get_grounder(
    prefix: Union[str, Iterable[str]], unnamed: Optional[Iterable[str]] = None
) -> Grounder:
    """Get a Gilda grounder for the given namespace."""
    unnamed = set() if unnamed is None else set(unnamed)
    if isinstance(prefix, str):
        prefix = [prefix]

    terms = []
    for p in prefix:
        try:
            p_terms = list(get_gilda_terms(p, identifiers_are_names=p in unnamed))
        except NoBuild:
            continue
        else:
            terms.extend(p_terms)
    terms = filter_out_duplicates(terms)
    terms = multidict((term.norm_text, term) for term in terms)
    return Grounder(terms)


def get_gilda_terms(prefix: str, identifiers_are_names: bool = False) -> Iterable[gilda.term.Term]:
    """Get gilda terms for the given namespace."""
    id_to_name = get_id_name_mapping(prefix)
    for identifier, name in tqdm(id_to_name.items(), desc="mapping names"):
        yield gilda.term.Term(
            norm_text=normalize(name),
            text=name,
            db=prefix,
            id=identifier,
            entry_name=name,
            status="name",
            source=prefix,
        )

    id_to_synonyms = get_id_synonyms_mapping(prefix)
    for identifier, synonyms in tqdm(id_to_synonyms.items(), desc="mapping synonyms"):
        name = id_to_name[identifier]
        for synonym in synonyms:
            yield gilda.term.Term(
                norm_text=normalize(synonym),
                text=synonym,
                db=prefix,
                id=identifier,
                entry_name=name,
                status="synonym",
                source=prefix,
            )

    if identifiers_are_names:
        for identifier in tqdm(get_ids(prefix), desc="mapping identifiers"):
            yield gilda.term.Term(
                norm_text=normalize(identifier),
                text=identifier,
                db=prefix,
                id=identifier,
                entry_name=None,
                status="identifier",
                source=prefix,
            )
