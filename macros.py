from dataclasses import dataclass, field
from typing import Literal, Set
from translationconfig import IntSize


@dataclass(frozen=True)
class Macro:
    Name: str
    IsObjectLike: bool
    IsDefinitionLocationValid: bool
    IsDefinedAtGlobalScope: bool
    Body: str
    DefinitionLocation: str
    EndDefinitionLocation: str

    def defined_in(self, dir: str):
        '''Returns true if the macro was defined in the given dir'''
        return self.IsDefinitionLocationValid and self.DefinitionLocation.startswith(dir)

    @property
    def IsFunctionLike(self) -> bool:
        return not self.IsObjectLike


@dataclass(frozen=True)
class Invocation:
    Name: str
    DefinitionLocation: str
    InvocationLocation: str
    ASTKind: Literal['Decl', 'Stmt', 'TypeLoc', 'Expr']
    TypeSignature: str

    InvocationDepth: int
    NumASTRoots: int
    NumArguments: int

    HasStringification: bool
    HasTokenPasting: bool
    HasAlignedArguments: bool
    HasSameNameAsOtherDeclaration: bool

    IsExpansionControlFlowStmt: bool

    DoesBodyReferenceMacroDefinedAfterMacro: bool
    DoesBodyReferenceDeclDeclaredAfterMacro: bool
    DoesBodyContainDeclRefExpr: bool
    DoesBodyEndWithCompoundStmt: bool
    DoesSubexpressionExpandedFromBodyHaveLocalType: bool
    DoesSubexpressionExpandedFromBodyHaveTypeDefinedAfterMacro: bool

    DoesAnyArgumentHaveSideEffects: bool
    DoesAnyArgumentContainDeclRefExpr: bool

    IsHygienic: bool
    IsICERepresentableByInt32: bool
    IsICERepresentableByInt16: bool
    IsDefinitionLocationValid: bool
    IsInvocationLocationValid: bool
    IsObjectLike: bool
    IsInvokedInMacroArgument: bool
    IsNamePresentInCPPConditional: bool
    IsExpansionICE: bool

    IsExpansionTypeNull: bool
    IsExpansionTypeAnonymous: bool
    IsExpansionTypeLocalType: bool
    IsExpansionTypeDefinedAfterMacro: bool
    IsExpansionTypeVoid: bool
    IsExpansionTypeFunctionType: bool

    IsAnyArgumentTypeNull: bool
    IsAnyArgumentTypeAnonymous: bool
    IsAnyArgumentTypeLocalType: bool
    IsAnyArgumentTypeDefinedAfterMacro: bool
    IsAnyArgumentTypeVoid: bool
    IsAnyArgumentTypeFunctionType: bool

    IsInvokedWhereModifiableValueRequired: bool
    IsInvokedWhereAddressableValueRequired: bool
    IsAnyArgumentExpandedWhereConstExprRequired: bool
    IsInvokedWhereICERequired: bool
    IsInvokedWhereConstantExpressionRequired: bool

    IsAnyArgumentExpandedWhereModifiableValueRequired: bool
    IsAnyArgumentExpandedWhereAddressableValueRequired: bool
    IsAnyArgumentConditionallyEvaluated: bool
    IsAnyArgumentNeverExpanded: bool
    IsAnyArgumentNotAnExpression: bool

    @property
    def DefinitionLocationFilename(self) -> str:
        if not self.IsDefinitionLocationValid:
            return self.DefinitionLocation
        else:
            file, _line, _col = self.DefinitionLocation.split(':')
            return file

    @property
    def IsFunctionLike(self) -> bool:
        return not self.IsObjectLike

    @property
    def IsTopLevelNonArgument(self) -> bool:
        return all([self.InvocationDepth == 0,
                    not self.IsInvokedInMacroArgument,
                    self.IsInvocationLocationValid,
                    self.IsDefinitionLocationValid])

    @property
    def IsAligned(self) -> bool:
        assert self.IsTopLevelNonArgument
        return all([self.IsTopLevelNonArgument,
                    self.NumASTRoots == 1,
                    self.HasAlignedArguments])

    @property
    def HasSemanticData(self) -> bool:
        return all([
            # TODO: Check that we don't end with a compound statement
            self.IsTopLevelNonArgument,
            not self.IsAnyArgumentNeverExpanded,
            self.IsAligned,
            not (self.ASTKind == 'Expr' and self.IsExpansionTypeNull)
        ])

    @property
    def CanBeTurnedIntoEnum(self) -> bool:
        assert self.HasSemanticData
        # Enums have to be ICEs
        return self.IsExpansionICE

    @property
    def CanBeTurnedIntoVariable(self) -> bool:
        assert self.HasSemanticData
        return all([
            # Variables must be exprs
            self.ASTKind == 'Expr',
            # Variables cannot contain DeclRefExprs
            not self.DoesBodyContainDeclRefExpr,
            # Variables cannot be invoked where ICEs are required
            not self.IsInvokedWhereICERequired,
            # Variables cannot have the void type
            not self.IsExpansionTypeVoid
        ])

    @property
    def IsExpansionConstantExpression(self) -> bool:
        return all([
            self.ASTKind == 'Expr',
            # Variables cannot contain DeclRefExprs
            not self.DoesBodyContainDeclRefExpr,
        ])

    @property
    def CanBeTurnedIntoEnumOrVariable(self) -> bool:
        assert self.HasSemanticData
        return self.CanBeTurnedIntoEnum or self.CanBeTurnedIntoVariable

    @property
    def CanBeTurnedIntoFunction(self) -> bool:
        assert self.HasSemanticData
        return all([
            # Functions must be stmts or expressions
            (self.ASTKind == 'Stmt' or self.ASTKind == 'Expr'),
            # Functions cannot be invoked where ICEs are required
            not self.IsInvokedWhereICERequired
        ])

    @property
    def CanBeTurnedIntoAFunctionOrVariable(self) -> bool:
        assert self.HasSemanticData
        return (self.CanBeTurnedIntoFunction or
                self.CanBeTurnedIntoVariable)

    @property
    def CanBeTurnedIntoTypeDef(self) -> bool:
        assert self.HasSemanticData
        return self.ASTKind == 'TypeLoc'

    @property
    def MustAlterArgumentsOrReturnTypeToTransform(self) -> bool:
        assert self.HasSemanticData
        return any([
            not self.IsHygienic,
            self.IsInvokedWhereModifiableValueRequired,
            self.IsInvokedWhereAddressableValueRequired,
            self.IsAnyArgumentExpandedWhereModifiableValueRequired,
            self.IsAnyArgumentExpandedWhereAddressableValueRequired
        ])

    @property
    def MustAlterDeclarationsToTransform(self) -> bool:
        assert self.HasSemanticData
        return any([
            self.HasSameNameAsOtherDeclaration,
            self.DoesBodyReferenceMacroDefinedAfterMacro,
            self.DoesBodyReferenceDeclDeclaredAfterMacro,
            self.DoesSubexpressionExpandedFromBodyHaveLocalType,
            self.DoesSubexpressionExpandedFromBodyHaveTypeDefinedAfterMacro,
            self.IsExpansionTypeAnonymous,
            self.IsExpansionTypeLocalType,
            self.IsExpansionTypeDefinedAfterMacro,
            self.ASTKind == 'TypeLoc'
        ])

    @property
    def MustAlterCallSiteToTransform(self) -> bool:
        if not self.IsAligned:
            return True

        assert self.HasSemanticData
        return self.IsAnyArgumentConditionallyEvaluated

    @property
    def MustCreateThunksToTransform(self) -> bool:
        return any([
            self.DoesAnyArgumentHaveSideEffects,
            self.IsAnyArgumentTypeVoid
        ])

    @property
    def MustUseMetaprogrammingToTransform(self) -> bool:
        return ((self.HasStringification or self.HasTokenPasting) or
                (self.HasSemanticData and
                 self.IsFunctionLike and
                 self.CanBeTurnedIntoFunction and
                 self.IsAnyArgumentNotAnExpression) or
                self.IsExpansionControlFlowStmt or
                self.IsNamePresentInCPPConditional)

    @property
    def SatisfiesASyntacticProperty(self) -> bool:
        return not self.IsAligned

    @property
    def SatisfiesAScopingRuleProperty(self) -> bool:
        assert self.HasSemanticData
        return any([
            not self.IsHygienic,
            self.IsInvokedWhereModifiableValueRequired,
            self.IsInvokedWhereAddressableValueRequired,
            self.IsAnyArgumentExpandedWhereModifiableValueRequired,
            self.IsAnyArgumentExpandedWhereAddressableValueRequired,
            self.DoesBodyReferenceMacroDefinedAfterMacro,
            self.DoesBodyReferenceDeclDeclaredAfterMacro,
            self.DoesSubexpressionExpandedFromBodyHaveLocalType,
            self.DoesSubexpressionExpandedFromBodyHaveTypeDefinedAfterMacro,
            self.IsAnyArgumentTypeDefinedAfterMacro,
            self.IsAnyArgumentTypeLocalType,
        ])

    @property
    def SatisfiesATypingProperty(self) -> bool:
        assert self.HasSemanticData
        return any([
            self.IsExpansionTypeAnonymous,
            self.IsAnyArgumentTypeAnonymous,
            self.DoesSubexpressionExpandedFromBodyHaveLocalType,
            self.IsAnyArgumentTypeDefinedAfterMacro,
            self.DoesSubexpressionExpandedFromBodyHaveTypeDefinedAfterMacro,
            self.IsAnyArgumentTypeVoid,
            (self.IsObjectLike and self.IsExpansionTypeVoid),
            self.IsAnyArgumentTypeLocalType
        ])

    @property
    def SatisfiesACallingConventionProperty(self) -> bool:
        assert self.HasSemanticData
        return any([
            self.DoesAnyArgumentHaveSideEffects,
            self.IsAnyArgumentConditionallyEvaluated,
        ])

    @property
    def SatisfiesALanguageSpecificProperty(self) -> bool:
        return self.MustUseMetaprogrammingToTransform
        
    @property
    def IsExpression(self) -> bool:
        return self.ASTKind == 'Expr'

    @property
    def IsStatement(self) -> bool:
        return self.ASTKind == 'Stmt'

    def CanBeTurnedIntoEnumWithIntSize(self, int_size: IntSize) -> bool:
        return self.CanBeTurnedIntoEnum and \
        (self.IsICERepresentableByInt32 if int_size == IntSize.Int32
         else self.IsICERepresentableByInt16)

    @property
    def IsValidStatementKind(self) -> bool:
        if self.IsObjectLike:
            return self.IsExpression
        else:
            return self.IsExpression or self.IsStatement

    @property
    def IsCalledByName(self) -> bool:
        return any([
            self.IsAnyArgumentConditionallyEvaluated,
            self.DoesAnyArgumentHaveSideEffects,
            ])

    @property
    def ArgumentsCaptureEnvironment(self) -> bool:
        return any([
            self.IsAnyArgumentTypeAnonymous,
            self.IsAnyArgumentTypeLocalType,
            self.IsAnyArgumentTypeDefinedAfterMacro,
            ])


MacroMap = dict[Macro, Set[Invocation]]


@dataclass
class PreprocessorData:
    mm: MacroMap = field(default_factory=dict)
    inspected_macro_names: Set[str] = field(default_factory=set)
    local_includes: Set[str] = field(default_factory=set)
