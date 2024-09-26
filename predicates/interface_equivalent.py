from macros import Invocation, Macro, PreprocessorData
from enum import Enum, auto

class IEResult(Enum):
    VALID = auto()
    
    MACRO_NEVER_EXPANDED = auto()
    POLYMORPHIC = auto()
    NON_GLOBAL_SCOPE = auto()
    SYNTACTICALLY_INVALID_PROPERTY = auto()
    CANNOT_TRANSFORM = auto()

    USE_METAPROGRAMMING = auto()
    CALLED_BY_NAME = auto()
    CALLSITE_CONTEXT_ALTERING = auto()
    DYNAMICALLY_SCOPED = auto()
    ADDRESSABLE_VALUE_REQUIRED = auto()
    INVALID_STATEMENT_KIND = auto()


def ie_def(m: Macro, pd: PreprocessorData) -> IEResult:
    is_ = pd.mm[m]
    # We only analyze top-level non-argument invocations
    assert all([i.IsTopLevelNonArgument for i in is_])
    # We must have semantic data for all invocations
    if not all([i.HasSemanticData for i in is_]):
        return IEResult.SYNTACTICALLY_INVALID_PROPERTY
    # The macro must be expanded at least once
    if len(is_) == 0:
        return IEResult.MACRO_NEVER_EXPANDED
    # All invocations must have the same type signature
    if len(set([i.TypeSignature for i in is_])) != 1:
        return IEResult.POLYMORPHIC
    # The macro must be defined at global scope
    if not m.IsDefinedAtGlobalScope:
        return IEResult.NON_GLOBAL_SCOPE

    def check_conditions(i: Invocation):
        CONDITIONS = [
                (i.HasSemanticData, IEResult.SYNTACTICALLY_INVALID_PROPERTY), 

                (not i.IsInvokedWhereAddressableValueRequired and not i.IsInvokedWhereModifiableValueRequired, IEResult.ADDRESSABLE_VALUE_REQUIRED),

                (i.IsValidStatementKind, IEResult.INVALID_STATEMENT_KIND),

                (i.CanBeTurnedIntoEnumOrVariable if m.IsObjectLike else i.CanBeTurnedIntoFunction, IEResult.CANNOT_TRANSFORM),

                (i.DefinitionLocationFilename not in pd.local_includes, IEResult.DYNAMICALLY_SCOPED),
                (not i.MustAlterDeclarationsToTransform, IEResult.DYNAMICALLY_SCOPED),

                (not i.IsCalledByName, IEResult.CALLED_BY_NAME),

                (not i.MustUseMetaprogrammingToTransform, IEResult.USE_METAPROGRAMMING),
                (i.Name not in pd.inspected_macro_names, IEResult.USE_METAPROGRAMMING),
                ]
        for condition, result in CONDITIONS:
            if not condition:
                return result
        return None

    for i in is_:
        result = check_conditions(i)
        if result:
            return result

    return IEResult.VALID
    
