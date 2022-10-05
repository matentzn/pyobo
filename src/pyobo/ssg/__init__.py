"""Static site generator."""

import itertools as itt
from collections import defaultdict
from operator import attrgetter
from pathlib import Path
from typing import Optional, Union

import bioregistry
from jinja2 import Environment, FileSystemLoader
from tqdm import tqdm

from pyobo import Obo
from pyobo.struct import part_of

__all__ = [
    "make_page",
    "make_site",
]

HERE = Path(__file__).parent.resolve()
environment = Environment(
    autoescape=True, loader=FileSystemLoader(HERE), trim_blocks=True, lstrip_blocks=True
)
environment.globals["bioregistry"] = bioregistry
term_template = environment.get_template("term.html")
typedef_template = environment.get_template("typedef.html")
index_template = environment.get_template("index.html")


def make_site(
    obo: Obo,
    directory: Union[str, Path],
    use_subdirectories: bool = True,
    manifest: bool = False,
    resource: Optional[bioregistry.Resource] = None,
) -> None:
    """Make a website in the given directory.

    :param obo: The ontology to generate a site for
    :param directory: The directory in which to generate the site
    :param use_subdirectories: If true, creates directories for each term/property/typedef with an index.html
        inside. If false, creates HTML files named with the identifiers.
    :param manifest: If true, lists all entries on the homepage.
    :param resource: A custom resource
    """
    directory = Path(directory)
    directory.mkdir(exist_ok=True, parents=True)

    if resource is None:
        resource = bioregistry.get_resource(obo.ontology)
    if resource is None:
        raise KeyError

    if not manifest:
        _manifest = None
    else:
        _manifest = sorted(
            (term for term in itt.chain(obo, obo.typedefs or []) if term.prefix == obo.ontology),
            key=attrgetter("identifier"),
        )

    terms = list(obo)

    directory.joinpath("index.html").write_text(
        index_template.render(
            obo=obo, resource=resource, manifest=_manifest, number_terms=len(terms)
        )
    )

    parent_to_child = defaultdict(list)
    for term in tqdm(terms, desc=f"{obo.ontology} caching parents", unit="term", unit_scale=True):
        for parent in term.parents or []:
            parent_to_child[parent.curie].append(term)

    parts = defaultdict(list)
    for term in tqdm(terms, desc=f"{obo.ontology} caching parents", unit="term", unit_scale=True):
        for whole in term.get_relationships(part_of):
            parts[whole.curie].append(term)

    for term in tqdm(terms, desc=f"{obo.ontology} website", unit="term", unit_scale=True):
        if use_subdirectories:
            subdirectory = directory.joinpath(term.identifier)
            subdirectory.mkdir(exist_ok=True, parents=True)
            path = subdirectory.joinpath("index.html")
        else:
            path = directory.joinpath(term.identifier).with_suffix(".html")
        path.write_text(
            term_template.render(
                term=term,
                obo=obo,
                resource=resource,
                children=parent_to_child.get(term.curie),
                parts=parts.get(term.curie),
            )
        )

    for typedef in obo.typedefs or []:
        if typedef.prefix != obo.ontology:
            continue
        if use_subdirectories:
            subdirectory = directory.joinpath(typedef.identifier)
            subdirectory.mkdir(exist_ok=True, parents=True)
            path = subdirectory.joinpath("index.html")
        else:
            path = directory.joinpath(typedef.identifier).with_suffix(".html")
        path.write_text(typedef_template.render(typedef=typedef, obo=obo, resource=resource))


def _main():
    from pyobo.sources import HGNCGetter, UniProtPtmGetter

    for cls in [UniProtPtmGetter, HGNCGetter]:
        obo = cls()
        make_site(obo, f"/Users/cthoyt/Desktop/pyobo-sites/{obo.ontology}/")


if __name__ == "__main__":
    _main()
