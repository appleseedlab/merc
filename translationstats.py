from dataclasses import dataclass, field
from collections import Counter
import sys
import csv
from macros import Macro

# 3.10 compatibility
if sys.version_info <= (3, 10):
    from enum import Enum
    class StrEnum(str, Enum): pass
else:
    from enum import StrEnum

class MacroType(StrEnum):
    """
    Types of macros that we can handle
    """
    OBJECT_LIKE = "object_like"
    FUNCTION_LIKE = "function_like"

class TranslatorAction(StrEnum):
    pass

class TranslationType(TranslatorAction):
    VOID = "void"
    NON_VOID = "non_void"
    ENUM = "enum"
    CONST_STATIC = "const_static"

class SkipType(TranslatorAction):
    BODY_CONTAINS_DECL_REF_EXPR = "body_contains_decl_ref_expr"
    DEFINITION_HAS_FUNCTION_POINTER = "definition_has_function_pointer"

    # Object-like specifics
    CANT_FIT_ICE_IN_ENUM_SIZE = "cant_fit_ice_in_enum_size"
    INVOCATION_REQUIRES_CONSTANT_EXPRESSION = "invocation_requires_constant_expression"

@dataclass(slots=True)
class MacroRecord:
    """
    Base class for all macro records
    """
    macro: Macro

@dataclass(slots=True)
class SkipRecord(MacroRecord):
    skip_type: SkipType

@dataclass(slots=True)
class TranslationRecord(MacroRecord):
    macro_translation: str
    translation_type: TranslationType

@dataclass()
class TranslationRecords:
    records_by_type: Counter[tuple[MacroType, TranslatorAction]] = field(default_factory=Counter)
    translation_records: list[TranslationRecord] = field(default_factory=list)
    skip_records: list[SkipRecord] = field(default_factory=list)

    @property
    def total_translated(self) -> int:
        return len(self.translation_records)

    @property
    def total_skipped(self) -> int:
        return len(self.skip_records)

    def total_translated_by_type(self, macro_type: MacroType) -> int:
        return len(list(record for record in self.translation_records if self._get_macro_type(record.macro) == macro_type))

    def total_skipped_by_type(self, macro_type: MacroType) -> int:
        return len(list(record for record in self.skip_records if self._get_macro_type(record.macro) == macro_type))

    def _get_macro_type(self, macro: Macro) -> MacroType:
        return MacroType.FUNCTION_LIKE if macro.IsFunctionLike else MacroType.OBJECT_LIKE

    def add_translation_record(self, record: TranslationRecord) -> None:
        macro_type = self._get_macro_type(record.macro)

        self.translation_records.append(record)
        self.records_by_type[(macro_type, record.translation_type)] += 1

    def add_skip_record(self, record: SkipRecord):
        macro_type = self._get_macro_type(record.macro)

        self.skip_records.append(record)
        self.records_by_type[(macro_type, record.skip_type)] += 1

    def print_totals(self):
        print(f"Total translated: {self.total_translated}")
        print(f"Total skipped: {self.total_skipped}")

        print(f"Object-like stats:")
        print(f"  - Total translated: {self.total_translated_by_type(MacroType.OBJECT_LIKE)}")
        print(f"    - Translated to enum: {self.records_by_type[(MacroType.OBJECT_LIKE,TranslationType.ENUM)]}")
        print(f"    - Translated to enum: {self.records_by_type[(MacroType.OBJECT_LIKE,TranslationType.CONST_STATIC)]}")
        print(f"  - Total skipped: {self.total_skipped_by_type(MacroType.OBJECT_LIKE)}")
        print(f"    - Skipped due to function pointer type: {self.records_by_type[(MacroType.OBJECT_LIKE,SkipType.DEFINITION_HAS_FUNCTION_POINTER)]}")
        print(f"    - Skipped due to DeclRefExpr: {self.records_by_type[(MacroType.OBJECT_LIKE,SkipType.BODY_CONTAINS_DECL_REF_EXPR)]}")
        print(f"    - Untranslatable because enum size too small to represent ICE:"
              f"{self.records_by_type[(MacroType.OBJECT_LIKE,SkipType.CANT_FIT_ICE_IN_ENUM_SIZE)]}")
        print(f"    - Untranslatable contant expressions:"
              f"{self.records_by_type[(MacroType.OBJECT_LIKE,SkipType.INVOCATION_REQUIRES_CONSTANT_EXPRESSION)]}")

        print(f"Function-like stats:")
        print(f"  - Total translated: {self.total_translated_by_type(MacroType.FUNCTION_LIKE)}")
        print(f"    - Translated to void: {self.records_by_type[(MacroType.FUNCTION_LIKE,TranslationType.VOID)]}")
        print(f"    - Translated to non-void: {self.records_by_type[(MacroType.FUNCTION_LIKE,TranslationType.NON_VOID)]}")
        print(f"  - Total skipped: {self.total_skipped_by_type(MacroType.FUNCTION_LIKE)}")
        print(f"    - Skipped due to function pointer type: {self.records_by_type[(MacroType.FUNCTION_LIKE,SkipType.DEFINITION_HAS_FUNCTION_POINTER)]}")
        print(f"    - Skipped due to DeclRefExpr: {self.records_by_type[(MacroType.FUNCTION_LIKE,SkipType.BODY_CONTAINS_DECL_REF_EXPR)]}")
    
    def output_csv(self, filename: str):
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile, quoting=csv.QUOTE_MINIMAL)
            writer.writerow(["Macro", "Action", "Translation", "Type"])

            for record in self.translation_records:
                writer.writerow([record.macro.Name, "Translated", record.macro_translation, record.translation_type])

            for record in self.skip_records:
                writer.writerow([record.macro.Name, "Skipped", "", record.skip_type])

