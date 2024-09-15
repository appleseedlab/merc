from macros import Invocation, Macro, PreprocessorData
from enum import Enum, auto

class IEResult(Enum):
    VALID = auto()
    NO_SEMANTIC_DATA = auto()
    MACRO_NEVER_EXPANDED = auto()
    INVOCATIONS_HAVE_DIFFERENT_TYPE_SIGNATURES = auto()
    NOT_DEFINED_AT_GLOBAL_SCOPE = auto()
    LACKS_SEMANTIC_DATA = auto()
    CANNOT_TRANSFORM = auto()

    USE_METAPROGRAMMING = auto()
    THUNKIZING = auto()
    CALLSITE_CONTEXT_ALTERING = auto()
    CALLED_BY_NAME = auto()
    DYNAMICALLY_SCOPED = auto()

def ie_def(m: Macro, pd: PreprocessorData) -> IEResult:
    is_ = pd.mm[m]
    # We only analyze top-level non-argument invocations
    assert all([i.IsTopLevelNonArgument for i in is_])
    # We must have semantic data for all invocations
    if not all([i.HasSemanticData for i in is_]):
        return IEResult.NO_SEMANTIC_DATA
    # The macro must be expanded at least once
    if len(is_) == 0:
        return IEResult.MACRO_NEVER_EXPANDED
    # All invocations must have the same type signature
    if len(set([i.TypeSignature for i in is_])) != 1:
        return IEResult.INVOCATIONS_HAVE_DIFFERENT_TYPE_SIGNATURES
    # The macro must be defined at global scope
    if not m.IsDefinedAtGlobalScope:
        return IEResult.NOT_DEFINED_AT_GLOBAL_SCOPE

    def check_conditions(i: Invocation):
        CONDITIONS = [
                # Valid for analysis
                (i.HasSemanticData, IEResult.LACKS_SEMANTIC_DATA), 
                # Can be turn into an enum or variable
                (i.CanBeTurnedIntoEnumOrVariable if m.IsObjectLike else i.CanBeTurnedIntoFunction, IEResult.CANNOT_TRANSFORM),
                # Argument-altering
                (not i.MustAlterArgumentsOrReturnTypeToTransform, IEResult.CALLED_BY_NAME),
                # Declaration-altering
                (i.DefinitionLocationFilename not in pd.local_includes, IEResult.DYNAMICALLY_SCOPED),
                (i.Name not in pd.inspected_macro_names, IEResult.DYNAMICALLY_SCOPED),
                (not i.IsNamePresentInCPPConditional, IEResult.DYNAMICALLY_SCOPED),
                (not i.MustAlterDeclarationsToTransform, IEResult.DYNAMICALLY_SCOPED),
                # Call-site-context-altering
                (not i.MustAlterCallSiteToTransform, IEResult.CALLSITE_CONTEXT_ALTERING),
                # Thunkizing
                (not i.MustCreateThunksToTransform, IEResult.THUNKIZING),
                (not i.MustUseMetaprogrammingToTransform, IEResult.USE_METAPROGRAMMING)
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
    
