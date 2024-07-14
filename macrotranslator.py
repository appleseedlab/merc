from macros import MacroMap, Macro, Invocation
from translationconfig import TranslationConfig
import logging
import re

logger = logging.getLogger(__name__)


class MacroTranslator:
    def __init__(self, translation_config: TranslationConfig) -> None:
        self.translation_config = translation_config

    def generate_macro_translations(self,
                                    mm: MacroMap) -> dict[Macro, str | None]:
        translationMap: dict[Macro, str | None] = {}

        for macro, invocations in mm.items():
            translationMap[macro] = self.get_macro_translation(macro, invocations)

        return translationMap

    def get_macro_translation(self, macro: Macro, invocations: set[Invocation]) -> str | None:

        if self.should_skip_due_to_technical_limitations(macro, invocations):
            return None

        if macro.IsFunctionLike:
            return self.translate_function_like_macro(macro, invocations)
        elif macro.IsObjectLike:
            return self.translate_object_like_macro(macro, invocations)

    def should_skip_due_to_technical_limitations(self, macro: Macro, invocations: set[Invocation]) -> bool:
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
            return True

        # If body contains a DeclRefExpr and is in a header file, skip
        # TODO(Joey/Brent): Find better way on Maki side to handle this
        invocation = next(iter(invocations))

        invocation_has_decl_ref_expr = invocation.DoesBodyContainDeclRefExpr
        if invocation_has_decl_ref_expr and invocation.DefinitionLocationFilename.endswith(".h"):
            logger.debug(f"Skipping {macro.Name} as it contains a DeclRefExpr")
            return True

        return False

    def translate_function_like_macro(self, macro: Macro, invocations: set[Invocation]) -> str:
        # Make sure we don't return for void functions,
        # but do return for void * and anything else
        invocation = next(iter(invocations))
        is_void = invocation.IsExpansionTypeVoid

        returnStatement = "return" if not is_void else ""
        return f"static inline {invocation.TypeSignature} {{ {returnStatement} {macro.Body}; }}"

    def translate_object_like_macro(self, macro: Macro, invocations: set[Invocation]) -> str | None:
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
                return f"enum {{ {macro.Name} = {macro.Body} }};"
            else:
                # Can't fit into an enum
                return None

        # Not a constant expression (or ICE) so safe to translate to a static const
        if not invoked_where_constant_expression_required:
            return f"static const {invocation.TypeSignature} = {macro.Body};"
        # We're a constant expression but not an ICE - can't handle
        else:
            return None
