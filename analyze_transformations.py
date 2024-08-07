import json
from typing import Set, Any
import logging
from collections import Counter
import re

from macros import Macro, MacroMap, PreprocessorData, Invocation
from predicates.argument_altering import aa_invocation
from predicates.call_site_context_altering import csca_invocation
from predicates.declaration_altering import da_invocation
from predicates.interface_equivalent import ie_def
from predicates.metaprogramming import mp_invocation
from predicates.thunkizing import thunkizing_invocation

logger = logging.getLogger(__name__)


def easy_to_transform_invocation(i: Invocation,
                                 pd: PreprocessorData,
                                 ie_invocations: Set[Invocation]):
    return ((i in ie_invocations) or
            ((aa_invocation(i, pd) or da_invocation(i, pd)) and
             (not csca_invocation(i, pd)) and
             (not thunkizing_invocation(i, pd)) and
             (not mp_invocation(i, pd))))


def easy_to_transform_definition(m: Macro,
                                 pd: PreprocessorData,
                                 ie_invocations: Set[Invocation]):
    return all(
        easy_to_transform_invocation(i, pd, ie_invocations)
        for i in pd.mm[m]
    )

def filter_definitions(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Count the number of definitions with a given name
    name_counts = Counter(obj["Name"] for obj in entries if obj["Kind"] == "Definition")

    # Create set of definition names that only appear once
    filtered_names = {name for name in name_counts if name_counts[name] == 1}

    # Filter out definitions and invocations that are not in filtered_names
    filtered_entries = [
        obj for obj in entries
        if not ((obj["Kind"] == "Definition" and obj["Name"] not in filtered_names) or
               (obj["Kind"] == "Invocation" and obj["Name"] not in filtered_names))
    ]

    return filtered_entries

def get_interface_equivalent_preprocessordata(results_file: str) -> PreprocessorData:

    with open(results_file) as fp:
        entries = json.load(fp)

    # Filter out duplicate definitions: keep none if there is more than one
    # We need to do this to avoid (possibly) breaking the one definition rule
    # i.e if file B includes file A, both have a definition with the same name
    filtered_entries = filter_definitions(entries)

    # We need definitions to come first as we map invocations to them
    filtered_entries.sort(key=lambda obj: obj["Kind"] == "Definition", reverse=True)

    pd = PreprocessorData()

    # src directory, to be initialized during the analysis
    src_dir = ''

    # We need this because invocations don't have all the information necessary
    # to construct a macro to use as a key in the macro map (pd.mm)
    # NOTE: Currently ignores macros without FileEntry data (i.e compiler built-ins)
    macroDefinitionLocationToMacroObject: dict[str, Macro] = {}

    for entry in filtered_entries:
        if entry["Kind"] == "Definition":
            del entry["Kind"]
            m = Macro(**entry)
            if m not in pd.mm:
                pd.mm[m] = set()
            if m.IsDefinitionLocationValid:
                macroDefinitionLocationToMacroObject[entry["DefinitionLocation"]] = m
                logging.debug(f"Adding name {m.Name} to macroDefinitionLocationToMacroObject")
        elif entry["Kind"] == 'InspectedByCPP':
            pd.inspected_macro_names.add(entry["Name"])
        elif entry["Kind"] == "Include":
            if entry["IsValid"]:
                pd.local_includes.add(entry["IncludeName"])
        elif entry["Kind"] == 'Invocation':
            del entry["Kind"]
            i = Invocation(**entry)
            if i.IsDefinitionLocationValid:
                m = macroDefinitionLocationToMacroObject[i.DefinitionLocation]
                # Only record unique invocations - two invocations may have the same
                # location if they are the same nested invocation
                if all(j.InvocationLocation != i.InvocationLocation for j in pd.mm[m]):
                    pd.mm[m].add(i)

    # src_pd only records preprocessor data about source macros
    src_pd = PreprocessorData(
        {m: is_ for m, is_ in pd.mm.items() if m.defined_in(src_dir)},
        pd.inspected_macro_names,
        pd.local_includes
    )

    # tlna_src_pd only records preprocessor data about top-level,
    # non-argument source macros
    tlna_src_pd = PreprocessorData(
        {m: is_ for m, is_ in src_pd.mm.items()
         if all([i.IsTopLevelNonArgument for i in is_])},
        src_pd.inspected_macro_names,
        src_pd.local_includes
    )

    # ie_pd only records preprocessor data about interface-equivalent
    # macros
    ie_pd = PreprocessorData(
        {m: is_ for m, is_ in tlna_src_pd.mm.items()
         if ie_def(m, tlna_src_pd)},
        tlna_src_pd.inspected_macro_names,
        tlna_src_pd.local_includes
    )

    return ie_pd
