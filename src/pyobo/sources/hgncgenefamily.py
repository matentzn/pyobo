# -*- coding: utf-8 -*-

"""Converter for HGNC Gene Families."""

from collections import defaultdict
from typing import Iterable, List, Mapping

import pandas as pd
from tqdm import tqdm

from ..struct import Obo, Reference, Synonym, SynonymTypeDef, Term, from_species
from ..utils.path import ensure_path

PREFIX = "hgnc.genegroup"
FAMILIES_URL = "ftp://ftp.ebi.ac.uk/pub/databases/genenames/new/csv/genefamily_db_tables/family.csv"
# TODO use family_alias.csv
HIERARCHY_URL = (
    "ftp://ftp.ebi.ac.uk/pub/databases/genenames/new/csv/genefamily_db_tables/hierarchy.csv"
)

symbol_type = SynonymTypeDef(id="symbol", name="symbol")


def get_obo(force: bool = False) -> Obo:
    """Get HGNC Gene Groups as OBO."""
    return Obo(
        ontology=PREFIX,
        name="HGNC Gene Groups",
        iter_terms=get_terms,
        iter_terms_kwargs=dict(force=force),
        synonym_typedefs=[symbol_type],
        typedefs=[from_species],
        auto_generated_by=f"bio2obo:{PREFIX}",
    )


def get_hierarchy(force: bool = False) -> Mapping[str, List[str]]:
    """Get the HGNC Gene Families hierarchy as a dictionary."""
    path = ensure_path(PREFIX, url=HIERARCHY_URL, force=force)
    df = pd.read_csv(path, dtype={"parent_fam_id": str, "child_fam_id": str})
    d = defaultdict(list)
    for parent_id, child_id in df.values:
        d[child_id].append(parent_id)
    return dict(d)


COLUMNS = ["id", "abbreviation", "name", "pubmed_ids", "desc_comment", "desc_go"]


def get_terms(force: bool = False) -> Iterable[Term]:
    """Get the HGNC Gene Group terms."""
    terms = list(_get_terms_helper(force=force))
    hierarchy = get_hierarchy(force=force)

    id_to_term = {term.reference.identifier: term for term in terms}
    for child_id, parent_ids in hierarchy.items():
        child = id_to_term[child_id]
        for parent_id in parent_ids:
            parent: Term = id_to_term[parent_id]
            child.parents.append(
                Reference(
                    prefix=PREFIX,
                    identifier=parent_id,
                    name=parent.name,
                )
            )
    return terms


def _get_terms_helper(force: bool = False) -> Iterable[Term]:
    path = ensure_path(PREFIX, url=FAMILIES_URL, force=force)
    df = pd.read_csv(path, dtype={"id": str})

    it = tqdm(df[COLUMNS].values, desc=f"Mapping {PREFIX}")
    for gene_group_id, symbol, name, pubmed_ids, definition, desc_go in it:
        if not definition or pd.isna(definition):
            definition = None
        term = Term(
            reference=Reference(prefix=PREFIX, identifier=gene_group_id, name=name),
            definition=definition,
        )
        if pubmed_ids and pd.notna(pubmed_ids):
            for s in pubmed_ids.split(","):
                term.append_provenance(Reference(prefix="pubmed", identifier=s.strip()))
        if desc_go and pd.notna(desc_go):
            go_id = desc_go[len("http://purl.uniprot.org/go/") :]
            term.append_xref(Reference(prefix="go", identifier=go_id))
        if symbol and pd.notna(symbol):
            term.append_synonym(Synonym(name=symbol, type=symbol_type))
        term.set_species(identifier="9606", name="Homo sapiens")
        yield term


if __name__ == "__main__":
    get_obo(force=True).write_default(force=True, write_obo=True)
