import json
from typing import Set, Any
import logging

from macros import Macro, MacroMap, PreprocessorData
from predicates.argument_altering import aa_invocation
from predicates.call_site_context_altering import csca_invocation
from predicates.declaration_altering import da_invocation
from predicates.interface_equivalent import ie_def
from predicates.metaprogramming import mp_invocation
from predicates.property_categories import *
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
    return all([
        easy_to_transform_invocation(i, pd, ie_invocations)
        for i in pd.mm[m]
    ])


def generate_macro_translations(mm: MacroMap) -> dict[Macro, str | None]:
    translationMap: dict[Macro, str | None] = {}

    for macro, invocations in mm.items():
        # We only need to look at the first invocation to determine the translation
        # Already verified that all type signatures are the same
        invocation = next(iter(invocations), None)
        assert invocation is not None

        # Static to avoid breaking the one definition rule
        if macro.IsFunctionLike:
            # return only if not void
            returnStatement = "return" if not invocation.TypeSignature.startswith("void") else ""
            translationMap[macro] = f"static inline {invocation.TypeSignature} {{ {returnStatement} {macro.Body}; }}"

        elif macro.IsObjectLike:
            # All invocations where an ICE is required must be representable by type int 
            # to be translatable to an enum
            can_translate_to_enum = all(
                [i.IsICERepresentableByInt32 for i in invocations if i.IsInvokedWhereICERequired])

            # If no invocations require ICE, just make it a static const variable
            not_invoked_where_ICE_required = all([not i.IsInvokedWhereICERequired for i in invocations])

            if not_invoked_where_ICE_required:
                translationMap[macro] = f"static const {invocation.TypeSignature} = {macro.Body};"
            elif can_translate_to_enum:
                translationMap[macro] = f"enum {{ {macro.Name} = {macro.Body} }};"
            else:
                translationMap[macro] = None

    return translationMap


def get_interface_equivalent_preprocessordata(results_file: str) -> PreprocessorData:
    unique_names : dict[str, Any] = {}

    with open(results_file) as fp:
        entries = json.load(fp)

        # Keep only one macro definition. if there's more than one, keep none
        for obj in entries:
            if obj["Kind"] == "Definition":
                if obj["Name"] in unique_names:
                    unique_names[obj["Name"]] = None
                else:
                    unique_names[obj["Name"]] = obj


    # Filter out the None values.
    filtered_entries = [obj for obj in entries if obj["Name"] is not None]

    # Sort the entries so that Definitions come first (we need to know them before we look at invocations)
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


def get_interface_equivalent_translations(results_file: str) -> dict[Macro, str | None]:
    ie_pd = get_interface_equivalent_preprocessordata(results_file)
    return generate_macro_translations(ie_pd.mm)
