#!/usr/bin/python3

import argparse
import json
from typing import Callable, List, Set

from macros import Invocation, Macro, MacroMap, PreprocessorData
from predicates.argument_altering import aa_invocation
from predicates.call_site_context_altering import csca_invocation
from predicates.declaration_altering import da_invocation
from predicates.interface_equivalent import ie_def
from predicates.metaprogramming import mp_invocation
from predicates.thunkizing import thunkizing_invocation
from predicates.property_categories import *

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


def generate_macro_translations(mm: MacroMap) -> dict[Macro, str]:
    translationMap: dict[Macro, str] = {}

    for macro, invocations in mm.items():
        # We only need to look at the first invocation to determine the translation
        # Already verified that all type signatures are the same
        invocation = next(iter(invocations), None)
        assert invocation is not None

        if macro.IsFunctionLike:
            translationMap[macro] = f"{invocation.TypeSignature} {{ return {macro.Body} }};" 
        # For now just make it a variable. Consider anonymous enum in the future
        elif macro.IsObjectLike:
            translationMap[macro] = f"{invocation.TypeSignature} = {macro.Body};" 

    return translationMap


def get_interface_equivalent_preprocessordata(results_file: str) -> PreprocessorData:
    try:
        with open(results_file) as fp:
            entries = json.load(fp)
    except Exception as e:
        print(f"Error reading file {results_file}: {e}")
        exit(1)

    pd = PreprocessorData()

    # src directory, to be initialized during the analysis
    src_dir = ''


    # We need this because invocations don't have all the information necessary
    # to construct a macro to use as a key in the macro map (pd.mm)
    # NOTE: Currently ignores macros without FileEntry data (i.e compiler built-ins)
    macroDefinitionLocationToMacroObject: dict[str, Macro] = {}

    for entry in entries:
        #print(entry)
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

    return ie_pd


def get_interface_equivalent_translations(results_file: str) -> dict[Macro, str]:
    ie_pd = get_interface_equivalent_preprocessordata(results_file)
    return generate_macro_translations(ie_pd.mm)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('results_file', type=str)
    ap.add_argument('-o', '--output_file')
    args = ap.parse_args()

    #output_translations(args.results_file, args.output_file)


if __name__ == '__main__':
    main()
