import logging
from macros import Macro, Invocation, PreprocessorData
from predicates.interface_equivalent import ie_def, TranslationTarget
from translationconfig import TranslationConfig
from translationstats import TechnicalSkip
from translationstats import TranslationRecord, TranslationRecords, SkipRecord, MacroRecord

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
        ie_result, translation_target = ie_def(macro, pd, self.translation_config)

        if translation_target is not None:
            skip_reason = self.should_skip_due_to_technical_limitations(macro, invocations)
            if skip_reason:
                return SkipRecord(macro, invocations, skip_reason)

        match translation_target:
            case TranslationTarget.VOID_FUNCTION:
                return self.translate_macro_to_void_function(macro, invocations)
            case TranslationTarget.NON_VOID_FUNCTION:
                return self.translate_macro_to_non_void_function(macro, invocations)
            case TranslationTarget.GLOBAL_VARIABLE:
                return self.translate_macro_to_global_variable(macro, invocations)
            case TranslationTarget.ENUM:
                return self.translate_macro_to_enum(macro, invocations)
            case None:
                return SkipRecord(macro, invocations, ie_result)

    def should_skip_due_to_technical_limitations(self, macro: Macro, invocations: set[Invocation]) -> TechnicalSkip | None:
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
            return TechnicalSkip.DEFINITION_HAS_FUNCTION_POINTER

        # If body contains a DeclRefExpr and is in a header file, skip
        # TODO(Joey/Brent): Find better way on Maki side to handle this
        invocation = next(iter(invocations))

        invocation_has_decl_ref_expr = invocation.DoesBodyContainDeclRefExpr
        if invocation_has_decl_ref_expr and invocation.DefinitionLocationFilename.endswith(".h"):
            logger.debug(f"Skipping {macro.Name} as it contains a DeclRefExpr")
            return TechnicalSkip.BODY_CONTAINS_DECL_REF_EXPR

        return None

    def translate_macro_to_void_function(self, macro: Macro, invocations: set[Invocation]) -> TranslationRecord:
        invocation = next(iter(invocations))

        translation = f"static inline {invocation.TypeSignature} {{ {macro.Body}; }}"
        return TranslationRecord(macro, invocations, translation, TranslationTarget.VOID_FUNCTION)
    
    def translate_macro_to_non_void_function(self, macro: Macro, invocations: set[Invocation]) -> TranslationRecord:
        invocation = next(iter(invocations))

        translation = f"static inline {invocation.TypeSignature} {{ return {macro.Body}; }}"
        return TranslationRecord(macro, invocations, translation, TranslationTarget.NON_VOID_FUNCTION)

    def translate_macro_to_global_variable(self, macro: Macro, invocations: set[Invocation]) -> MacroRecord:
        invocation = next(iter(invocations))
        translation = f"static const {invocation.TypeSignature} = {macro.Body};"
        return TranslationRecord(macro, invocations, translation, TranslationTarget.GLOBAL_VARIABLE)

    def translate_macro_to_enum(self, macro: Macro, invocations: set[Invocation]) -> MacroRecord:
        translation = f"enum {{ {macro.Name} = {macro.Body} }};"
        return TranslationRecord(macro, invocations, translation, TranslationTarget.ENUM)
