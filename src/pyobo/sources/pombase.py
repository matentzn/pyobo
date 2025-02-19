# -*- coding: utf-8 -*-

"""Converter for PomBase."""

import logging
from collections import defaultdict
from typing import Iterable

import bioversions
import click
import pandas as pd
from more_click import verbose_option
from tqdm import tqdm

import pyobo
from pyobo import Reference
from pyobo.struct import Obo, Synonym, Term, from_species, has_gene_product, orthologous
from pyobo.utils.path import ensure_df

logger = logging.getLogger(__name__)

PREFIX = "pombase"
NAME = "PomBase"
URL = "https://www.pombase.org/data/names_and_identifiers/gene_IDs_names_products.tsv"
ORTHOLOGS_URL = "https://www.pombase.org/data/orthologs/human-orthologs.txt.gz"


def get_obo(force: bool = False) -> Obo:
    """Get OBO."""
    version = bioversions.get_version("pombase")
    return Obo(
        iter_terms=get_terms,
        iter_terms_kwargs=dict(force=force),
        name=NAME,
        ontology=PREFIX,
        typedefs=[from_species, has_gene_product],
        auto_generated_by=f"bio2obo:{PREFIX}",
        data_version=version,
    )


#: A mapping from PomBase gene type to sequence ontology terms
POMBASE_TO_SO = {
    "protein coding gene": "0001217",
    "pseudogene": "0000336",
    "tRNA gene": "0001272",
    "ncRNA gene": "0001263",
    "snRNA gene": "0001268",
    "snoRNA gene": "0001267",
    "rRNA gene": "0001637",
}


def get_terms(force: bool = False) -> Iterable[Term]:
    """Get terms."""
    orthologs_df = ensure_df(PREFIX, url=ORTHOLOGS_URL, force=force, header=None)
    identifier_to_hgnc_ids = defaultdict(set)
    hgnc_symbol_to_id = pyobo.get_name_id_mapping("hgnc")
    for identifier, hgnc_symbols in orthologs_df.values:
        if hgnc_symbols == "NONE":
            continue
        for hgnc_symbol in hgnc_symbols.split("|"):
            hgnc_id = hgnc_symbol_to_id.get(hgnc_symbol)
            if hgnc_id is not None:
                identifier_to_hgnc_ids[identifier].add(hgnc_id)

    df = ensure_df(PREFIX, url=URL, force=force, header=None)
    so = {
        gtype: Reference.auto("SO", POMBASE_TO_SO[gtype])
        for gtype in sorted(df[df.columns[6]].unique())
    }
    for _, reference in sorted(so.items()):
        yield Term(reference=reference)
    for identifier, _, symbol, chromosome, name, uniprot_id, gtype, synonyms in tqdm(df.values):
        term = Term.from_triple(
            prefix=PREFIX,
            identifier=identifier,
            name=symbol if pd.notna(symbol) else None,
            definition=name if pd.notna(name) else None,
        )
        term.append_property("chromosome", chromosome[len("chromosome_") :])
        term.append_parent(so[gtype])
        term.set_species(identifier="4896", name="Schizosaccharomyces pombe")
        for hgnc_id in identifier_to_hgnc_ids.get(identifier, []):
            term.append_relationship(orthologous, Reference.auto("hgnc", hgnc_id))
        if uniprot_id and pd.notna(uniprot_id):
            term.append_relationship(has_gene_product, Reference.auto("uniprot", uniprot_id))
        if synonyms and pd.notna(synonyms):
            for synonym in synonyms.split(","):
                term.append_synonym(Synonym(synonym))
        yield term


@click.command()
@verbose_option
def _main():
    obo = get_obo(force=True)
    obo.write_default(force=True, write_obo=True, write_obograph=True)


if __name__ == "__main__":
    _main()
