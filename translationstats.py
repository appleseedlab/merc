from dataclasses import dataclass, field
from predicates.interface_equivalent import IEResult, TranslationTarget
from collections import Counter
import csv
from macros import Macro, Invocation
from enum import Enum, auto


class MacroType(Enum):
    """
    Types of macros that we can handle
    """
    OBJECT_LIKE = auto()
    FUNCTION_LIKE = auto()

class TechnicalSkip(Enum):
    BODY_CONTAINS_DECL_REF_EXPR = auto()
    DEFINITION_HAS_FUNCTION_POINTER = auto()

@dataclass(slots=True)
class MacroRecord:
    """
    Base class for all macro records
    """
    macro: Macro
    invocations: set[Invocation]

SkipType = TechnicalSkip | IEResult

@dataclass(slots=True)
class SkipRecord(MacroRecord):
    skip_type: SkipType

@dataclass(slots=True)
class TranslationRecord(MacroRecord):
    macro_translation: str
    translation_type: TranslationTarget

@dataclass()
class TranslationRecords:
    records_by_type: Counter[tuple[MacroType, SkipType | TranslationTarget]] = field(default_factory=Counter)
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
        print(f"    - Translated to enum: {self.records_by_type[(MacroType.OBJECT_LIKE,TranslationTarget.ENUM)]}")
        print(f"    - Translated to const static: {self.records_by_type[(MacroType.OBJECT_LIKE,TranslationTarget.GLOBAL_VARIABLE)]}")
        print(f"  - Total skipped: {self.total_skipped_by_type(MacroType.OBJECT_LIKE)}")
        print(f"    - Skipped due to function pointer type: {self.records_by_type[(MacroType.OBJECT_LIKE,TechnicalSkip.DEFINITION_HAS_FUNCTION_POINTER)]}")
        print(f"    - Skipped due to DeclRefExpr: {self.records_by_type[(MacroType.OBJECT_LIKE,TechnicalSkip.BODY_CONTAINS_DECL_REF_EXPR)]}")

        print(f"Function-like stats:")
        print(f"  - Total translated: {self.total_translated_by_type(MacroType.FUNCTION_LIKE)}")
        print(f"    - Translated to void: {self.records_by_type[(MacroType.FUNCTION_LIKE,TranslationTarget.VOID_FUNCTION)]}")
        print(f"    - Translated to non-void: {self.records_by_type[(MacroType.FUNCTION_LIKE,TranslationTarget.NON_VOID_FUNCTION)]}")
        print(f"  - Total skipped: {self.total_skipped_by_type(MacroType.FUNCTION_LIKE)}")
        print(f"    - Skipped due to function pointer type: {self.records_by_type[(MacroType.FUNCTION_LIKE,TechnicalSkip.DEFINITION_HAS_FUNCTION_POINTER)]}")
        print(f"    - Skipped due to DeclRefExpr: {self.records_by_type[(MacroType.FUNCTION_LIKE,TechnicalSkip.BODY_CONTAINS_DECL_REF_EXPR)]}")

        # count not interface equivalent
        ie_reason_counter = Counter()
        for skip_record in self.skip_records:
            if skip_record.skip_type:
                ie_reason_counter[skip_record.skip_type] += 1

        print(f"- Total skipped due to not being interface equivalent: {sum(ie_reason_counter.values())}")
        for ie_reason, count in ie_reason_counter.items():
            print(f"    - {ie_reason}: {count}")

    
    def output_csv(self, filename: str, program_name: str) -> None:
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile, quoting=csv.QUOTE_MINIMAL)
            writer.writerow(["Program Name", "Macro", "Macro Type", "Action", "Translation or Macro Body", "Action Type", "Invocation Amount"])

            for translation_record in self.translation_records:
                writer.writerow([program_name,
                                 translation_record.macro.Name,
                                 self._get_macro_type(translation_record.macro),
                                 "Translated",
                                 translation_record.macro_translation,
                                 translation_record.translation_type,
                                 len(translation_record.invocations)]
                                )

            for skip_record in self.skip_records:
                writer.writerow([program_name,
                                 skip_record.macro.Name,
                                 self._get_macro_type(skip_record.macro),
                                 "Skipped",
                                 skip_record.macro.Body,
                                 skip_record.skip_type,
                                 len(skip_record.invocations)]
                                )
