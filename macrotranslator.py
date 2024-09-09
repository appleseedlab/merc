from macros import MacroMap, Macro, Invocation, PreprocessorData
from translationconfig import TranslationConfig
import logging
import re
from translationstats import TranslationRecord, TranslationRecords, SkipRecord, MacroRecord
from translationstats import TranslationType
from translationstats import SkipType
import predicates.interface_equivalent


logger = logging.getLogger(__name__)


class MacroTranslator:
    def __init__(self, translation_config: TranslationConfig) -> None:
        self.translation_config = translation_config
        self.translation_stats = TranslationRecords()

    def generate_macro_translations(self,
                                    pd: PreprocessorData) -> dict[Macro, str | None]:
        translationMap: dict[Macro, str | None] = {}


        for macro, invocations in pd.mm.items():
            record = self.get_macro_record(macro, invocations, pd)
            if isinstance(record, TranslationRecord):
                self.translation_stats.add_translation_record(record)
            elif isinstance(record, SkipRecord):
                self.translation_stats.add_skip_record(record)

        for skip_record in self.translation_stats.skip_records:
            translationMap[skip_record.macro] = None

        for translation_record in self.translation_stats.translation_records:
            translationMap[translation_record.macro] = translation_record.macro_translation

        return translationMap

    def get_macro_record(self, macro: Macro, invocations: set[Invocation], pd: PreprocessorData) -> MacroRecord:
        ie_result = predicates.interface_equivalent.ie_def(macro, pd)
        if  ie_result != predicates.interface_equivalent.IEResult.VALID:
            return SkipRecord(macro, SkipType.NOT_INTERFACE_EQUIVALENT, ie_result)


        skip_reason = self.should_skip_due_to_technical_limitations(macro, invocations)
        if skip_reason:
            return SkipRecord(macro, skip_reason)
        

        if macro.IsFunctionLike:
            return self.translate_function_like_macro(macro, invocations)

        return self.translate_object_like_macro(macro, invocations)


    def should_skip_due_to_technical_limitations(self, macro: Macro, invocations: set[Invocation]) -> SkipType | None:
        """
        Skips are due to technical limitations of Maki and MerC and not
        due to irreconcilable differences in macro and C semantics.

        These skips are subject to removal as Maki and MerC are improved.

        Skips due to differences in macro and C semantics
        are handled by predicates.interface_equivalent.ie_def
        """

        # For now, skip translating anything with a function pointer type
        # As Maki does not output the correct C syntax for these

        # If any part of the type signature has a function pointer
        invocation_has_function_type = \
            any(i.IsExpansionTypeFunctionType or i.IsAnyArgumentTypeFunctionType for i in invocations)

        # TODO(Joey): Implement a way to translate these
        if invocation_has_function_type:
            logger.debug(f"Skipping {macro.Name} as it has a function pointer type")
            return SkipType.DEFINITION_HAS_FUNCTION_POINTER

        # If body contains a DeclRefExpr and is in a header file, skip
        # TODO(Joey/Brent): Find better way on Maki side to handle this
        invocation = next(iter(invocations))

        invocation_has_decl_ref_expr = invocation.DoesBodyContainDeclRefExpr
        if invocation_has_decl_ref_expr and invocation.DefinitionLocationFilename.endswith(".h"):
            logger.debug(f"Skipping {macro.Name} as it contains a DeclRefExpr")
            return SkipType.BODY_CONTAINS_DECL_REF_EXPR

        return None

    def translate_function_like_macro(self, macro: Macro, invocations: set[Invocation]) -> TranslationRecord:
        invocation = next(iter(invocations))

        # Determine if we return or not
        is_void = invocation.IsExpansionTypeVoid or invocation.IsStatement
        returnStatement = "return" if not is_void else ""

        translation_type = TranslationType.NON_VOID if not is_void else TranslationType.VOID

        translation = f"static inline {invocation.TypeSignature} {{ {returnStatement} {macro.Body}; }}"
        return TranslationRecord(macro, translation, translation_type)

    def translate_object_like_macro(self, macro: Macro, invocations: set[Invocation]) -> MacroRecord:
        invocation = next(iter(invocations))

        # All invocations where an ICE is required must be representable by type int
        # to be translatable to an enum
        can_translate_to_enum = all(
            i.CanBeTurnedIntoEnumWithIntSize(self.translation_config.int_size)
            for i in invocations if i.IsInvokedWhereICERequired
        )

        invoked_where_ICE_required = any(i.IsInvokedWhereICERequired for i in invocations)
        invoked_where_constant_expression_required = \
            any(i.IsInvokedWhereConstantExpressionRequired for i in invocations)

        # If we're an ICE and translatable to an enum, translate to enum
        if invoked_where_ICE_required:
            if can_translate_to_enum:
                translation = f"enum {{ {macro.Name} = {macro.Body} }};"
                return TranslationRecord(macro, translation, TranslationType.ENUM)
            else:
                # Can't fit into an enum
                return SkipRecord(macro, SkipType.CANT_FIT_ICE_IN_ENUM_SIZE)

        # Not a constant expression (or ICE) so safe to translate to a static const
        if not invoked_where_constant_expression_required:
            translation = f"static const {invocation.TypeSignature} = {macro.Body};"
            return TranslationRecord(macro, translation, TranslationType.CONST_STATIC)
        # We're a constant expression but not an ICE - can't handle
        else:
            return SkipRecord(macro, SkipType.INVOCATION_REQUIRES_CONSTANT_EXPRESSION)
