from collections.abc import Callable
from dataclasses import dataclass
from macros import Invocation, Macro, PreprocessorData
from enum import Enum, auto

from translationconfig import TranslationConfig

class IEResult(Enum):
    VALID = auto()
    
    MACRO_NEVER_EXPANDED = auto()
    POLYMORPHIC = auto()
    NON_GLOBAL_SCOPE = auto()
    SYNTACTICALLY_INVALID_PROPERTY = auto()

    INVOKED_WHERE_ICE_REQUIRED_AND_GREATER_THAN_INT_SIZE = auto()
    INVOKED_WHERE_CONSTANT_EXPRESSION_REQUIRED = auto()

    EXPANSION_NOT_CONSTANT_EXPRESSION = auto()
    EXPANSION_NOT_ICE = auto()
    EXPANSION_TYPE_VOID = auto()
    EXPANSION_TYPE_NON_VOID = auto()

    USE_METAPROGRAMMING = auto()
    CALLED_BY_NAME = auto()
    CAPTURES_ENVIRONMENT = auto()
    ADDRESSABLE_VALUE_REQUIRED = auto()
    INVALID_STATEMENT_KIND = auto()

    ARGUMENT_ADDRESSABLE_VALUE_REQUIRED = auto()
    ARGUMENT_TYPE_VOID = auto()
    ARGUMENT_TYPE_NOT_EXPRESSION = auto()
    ARGUMENT_INVOKED_WHERE_CONSTANT_EXPRESSION_REQUIRED = auto()
    ARGUMENT_CAPTURES_ENVIRONMENT = auto()
    ARGUMENT_CALLED_BY_NAME = auto()

class TranslationTarget(Enum):
    GLOBAL_VARIABLE = auto()
    ENUM = auto()
    NON_VOID_FUNCTION = auto()
    VOID_FUNCTION = auto()

@dataclass
class Condition:
    check: Callable[[Invocation, PreprocessorData], bool]
    result: IEResult

def check_conditions(invocations: set[Invocation], pd: PreprocessorData, conditions: list[Condition]) -> IEResult:
    for invocation in invocations:
        for condition in conditions:
            if not condition.check(invocation, pd):
                return condition.result
    return IEResult.VALID

GLOBAL_CONDITIONS = [
        Condition(lambda i, pd: i.HasSemanticData, IEResult.SYNTACTICALLY_INVALID_PROPERTY), 
        Condition(lambda i, pd: not i.DoesBodyEndWithCompoundStmt, IEResult.SYNTACTICALLY_INVALID_PROPERTY),

        Condition(lambda i, pd: not i.IsInvokedWhereAddressableValueRequired and not i.IsInvokedWhereModifiableValueRequired, IEResult.ADDRESSABLE_VALUE_REQUIRED),

        Condition(lambda i, pd: i.DefinitionLocationFilename not in pd.local_includes, IEResult.CAPTURES_ENVIRONMENT),
        Condition(lambda i, pd: not i.MustAlterDeclarationsToTransform, IEResult.CAPTURES_ENVIRONMENT),


        Condition(lambda i, pd: not i.MustUseMetaprogrammingToTransform, IEResult.USE_METAPROGRAMMING),
        Condition(lambda i, pd: i.Name not in pd.inspected_macro_names, IEResult.USE_METAPROGRAMMING),
]

VARIABLE_CONDITIONS = [
    Condition(lambda i, pd: not i.IsInvokedWhereConstantExpressionRequired, IEResult.INVOKED_WHERE_CONSTANT_EXPRESSION_REQUIRED),     
    Condition(lambda i, pd: i.IsExpansionConstantExpression, IEResult.EXPANSION_NOT_CONSTANT_EXPRESSION),
]

ENUM_CONDITIONS = [
    Condition(lambda i, pd: i.IsExpansionICE, IEResult.EXPANSION_NOT_ICE),
]

NON_VOID_CONDITIONS = [
    Condition(lambda i, pd: not i.IsInvokedWhereConstantExpressionRequired, IEResult.INVOKED_WHERE_CONSTANT_EXPRESSION_REQUIRED),     
    Condition(lambda i, pd: not i.IsExpansionTypeVoid, IEResult.EXPANSION_TYPE_VOID),
    Condition(lambda i, pd: i.IsExpression, IEResult.INVALID_STATEMENT_KIND),
]

VOID_CONDITIONS = [
    Condition(lambda i, pd: not i.IsInvokedWhereConstantExpressionRequired, IEResult.INVOKED_WHERE_CONSTANT_EXPRESSION_REQUIRED),     
    Condition(lambda i, pd: i.IsExpansionTypeVoid, IEResult.EXPANSION_TYPE_NON_VOID),
    Condition(lambda i, pd: i.IsExpression or i.IsStatement, IEResult.INVALID_STATEMENT_KIND),
]

ARGUMENT_CONDITIONS = [
    Condition(lambda i, pd: not i.IsCalledByName, IEResult.CALLED_BY_NAME),
    Condition(lambda i, pd: not i.IsAnyArgumentExpandedWhereConstExprRequired, IEResult.ARGUMENT_INVOKED_WHERE_CONSTANT_EXPRESSION_REQUIRED),
    Condition(lambda i, pd: not i.IsAnyArgumentTypeVoid, IEResult.ARGUMENT_TYPE_VOID),
    Condition(lambda i, pd: not (i.IsAnyArgumentExpandedWhereModifiableValueRequired or i.IsAnyArgumentExpandedWhereAddressableValueRequired), IEResult.ARGUMENT_ADDRESSABLE_VALUE_REQUIRED),
    Condition(lambda i, pd: not i.IsAnyArgumentNotAnExpression, IEResult.ARGUMENT_TYPE_NOT_EXPRESSION),
]



def ie_def(m: Macro, pd: PreprocessorData, translation_config: TranslationConfig) -> tuple[IEResult, TranslationTarget | None]:
    is_ = pd.mm[m]
    # We only analyze top-level non-argument invocations
    assert all([i.IsTopLevelNonArgument for i in is_])
    # We must have semantic data for all invocations
    if not all([i.HasSemanticData for i in is_]):
        return IEResult.SYNTACTICALLY_INVALID_PROPERTY, None
    # The macro must be expanded at least once
    if len(is_) == 0:
        return IEResult.MACRO_NEVER_EXPANDED, None
    # All invocations must have the same type signature
    if len(set([i.TypeSignature for i in is_])) != 1:
        return IEResult.POLYMORPHIC, None
    # The macro must be defined at global scope
    if not m.IsDefinedAtGlobalScope:
        return IEResult.NON_GLOBAL_SCOPE, None
    
    global_condition_check = check_conditions(invocations=is_,
                                              pd=pd,
                                              conditions=GLOBAL_CONDITIONS)
    if global_condition_check != IEResult.VALID:
        return global_condition_check, None

    if m.IsObjectLike:
        variable_condition_check = check_conditions(invocations=is_,
                                                    pd=pd,
                                                    conditions=VARIABLE_CONDITIONS)
        enum_condition_check = check_conditions(invocations=is_,
                                                pd=pd,
                                                conditions=ENUM_CONDITIONS)

        if variable_condition_check == IEResult.VALID:
            return IEResult.VALID, TranslationTarget.GLOBAL_VARIABLE
        elif enum_condition_check == IEResult.VALID:
            if all([i.CanBeTurnedIntoEnumWithIntSize(translation_config.int_size) for i in is_]):
                return enum_condition_check, TranslationTarget.ENUM
            else:
                return IEResult.INVOKED_WHERE_ICE_REQUIRED_AND_GREATER_THAN_INT_SIZE, None
        else:
            return enum_condition_check, None

        
    else:
        argument_condition_check = check_conditions(invocations=is_,
                                                    pd=pd,
                                                    conditions=ARGUMENT_CONDITIONS)

        if argument_condition_check != IEResult.VALID:
            return argument_condition_check, None

        non_void_condition_check = check_conditions(invocations=is_,
                                                    pd=pd,
                                                    conditions=NON_VOID_CONDITIONS)
        void_condition_check = check_conditions(invocations=is_,
                                                pd=pd,
                                                conditions=VOID_CONDITIONS)

        if non_void_condition_check == IEResult.VALID:
            return non_void_condition_check, TranslationTarget.NON_VOID_FUNCTION
        elif void_condition_check == IEResult.VALID:
            return void_condition_check, TranslationTarget.VOID_FUNCTION
        else:
            return void_condition_check, None
