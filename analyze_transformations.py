#!/usr/bin/python3

import argparse
import json
import sys
from dataclasses import asdict
from itertools import chain
from typing import Callable, List, Set

from analysis import Analysis, MacroStat, definition_stat, invocation_stat
from macros import Invocation, Macro, PreprocessorData
from predicates.argument_altering import aa_invocation
from predicates.call_site_context_altering import csca_invocation
from predicates.declaration_altering import da_invocation
from predicates.interface_equivalent import ie_def
from predicates.mennie import mennie_def
from predicates.metaprogramming import mp_invocation
from predicates.thunkizing import thunkizing_invocation
from predicates.property_categories import *

ANALYSES_DIR = r'ANALYSES'
DELIM = '\t'


TRANSFORMATIONS = [aa_invocation, da_invocation,
                   csca_invocation, mp_invocation,
                   thunkizing_invocation]


InvocationPredicate = Callable[[Invocation, PreprocessorData], bool]


def only(i: Invocation,
         pd: PreprocessorData,
         p: InvocationPredicate,
         ps: List[InvocationPredicate]):
    '''
    Returns true if the predicate p is the only one that this
    transformation satisfies.
    '''
    assert p in ps
    satisfied = [p for p in ps if p(i, pd)]
    return satisfied == [p]


def mdefs_only_p(pd: PreprocessorData,
                 p: InvocationPredicate,
                 ps: List[InvocationPredicate]):
    return definition_stat(
        pd,
        lambda m, pd: all([only(i, pd, p, ps) for i in pd.mm[m]]))


def mdefs_at_least_p(pd, p):
    return definition_stat(pd,
                           lambda m, pd: any([p(i, pd) for i in pd.mm[m]]))


def invocations_only_p(pd, p, ps):
    return invocation_stat(pd, lambda i, pd_: only(i, pd_, p, ps))


def invocations_at_least_p(pd, p):
    return invocation_stat(pd, p)


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
    return all([
        easy_to_transform_invocation(i, pd, ie_invocations)
        for i in pd.mm[m]
    ])


def avg_or_zero(values):
    return round(sum(values) / len(values), 2) if values else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('results_file', type=str)
    ap.add_argument('-o', '--output_file')
    args = ap.parse_args()

    lines: list[str] = []
    with open(args.results_file) as fp:
        entries = json.load(fp)

    pd = PreprocessorData()

    # src directory, to be initialized during the analysis
    src_dir = ''


    # We need this because invocations don't have all the information necessary
    # to construct a macro to use as a key in the macro map (pd.mm)
    # NOTE: Currently ignores macros without FileEntry data (i.e compiler built-ins)
    macroDefinitionLocationToMacroObject: dict[str, Macro] = {}

    for entry in entries:
        print(entry)
        if entry["Kind"] == "Definition":
            m = Macro(entry["Name"], entry["IsObjectLike"],
                    entry["IsDefinitionLocationValid"], entry["Body"], entry["DefinitionLocation"], entry["EndDefinitionLocation"])
            if m not in pd.mm:
                pd.mm[m] = set()
            if m.IsDefinitionLocationValid: 
                macroDefinitionLocationToMacroObject[entry["DefinitionLocation"]] = m

        elif entry["Kind"] == 'InspectedByCPP':
            pd.inspected_macro_names.add(entry["Name"])
        elif entry["Kind"] == "Include":
            if entry["IsIncludeLocationValid"]:
                pd.local_includes.add(entry["IncludeName"])
        elif entry["Kind"] == 'Invocation':
            del entry["Kind"]
            i = Invocation(**entry)
            if i.IsDefinitionLocationValid: 
                m = macroDefinitionLocationToMacroObject[i.DefinitionLocation]
                # Only record unique invocations - two invocations may have the same
                # location if they are the same nested invocation
                if all([j.InvocationLocation != i.InvocationLocation for j in pd.mm[m]]):
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


if __name__ == '__main__':
    main()
