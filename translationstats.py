from dataclasses import dataclass, field 
from textwrap import indent

@dataclass(slots=True)
class SkipStats:
    # Skipped due to Maki limitations
    skipped_function_ptr: int = 0
    skipped_decl_ref_expr: int = 0

    @property
    def total_skipped(self) -> int:
        return self.skipped_function_ptr + self.skipped_decl_ref_expr

    def __str__(self) -> str:
        return (
                f"- Skipped due to function pointer type: {self.skipped_function_ptr}\n"
                f"- Skipped due to DeclRefExpr: {self.skipped_decl_ref_expr}"
                )

@dataclass(slots=True)
class ObjectLikeStats:
    translated_to_enum: int = 0
    translated_to_static_const: int = 0

    @property
    def total_translated(self) -> int:
        return self.translated_to_enum + self.translated_to_static_const

    skipped_stats: SkipStats = field(default_factory=SkipStats)

    untranslatable_constant_expr: int = 0
    untranslatable_enum_size: int = 0

    @property
    def total_skipped(self) -> int:
        return self.skipped_stats.total_skipped + self.untranslatable_constant_expr \
                + self.untranslatable_enum_size

    def __str__(self) -> str:
        return (
                f"Object-like stats:\n"
                f"  - Total translated: {self.total_translated}\n"
                f"    - Translated to enum: {self.translated_to_enum}\n"
                f"    - Translated to static const: {self.translated_to_static_const}\n"
                f"  - Total skipped: {self.total_skipped}\n"
                f"{indent(str(self.skipped_stats), '    ')}\n"
                f"    - Untranslatable because enum size too small to represent ICE: {self.untranslatable_enum_size}\n"
                f"    - Untranslatable constant expressions: {self.untranslatable_constant_expr}"
                )

@dataclass(slots=True)
class FunctionLikeStats:
    translated_to_void: int = 0
    translated_to_non_void: int = 0

    @property
    def total_translated(self) -> int:
        return self.translated_to_void + self.translated_to_non_void

    skipped_stats: SkipStats = field(default_factory=SkipStats)

    @property
    def total_skipped(self) -> int:
        return self.skipped_stats.total_skipped
    
    def __str__(self) -> str:
        return (
                f"Function-like stats:\n"
                f"  - Total translated: {self.total_translated}\n"
                f"    - Translated to void: {self.translated_to_void}\n"
                f"    - Translated to non-void: {self.translated_to_non_void}\n"
                f"  - Total skipped: {self.total_skipped}\n"
                f"{indent(str(self.skipped_stats), '    ')}\n"
                )

@dataclass 
class MacroTranslatorStats:
    object_like_stats: ObjectLikeStats = field(default_factory=ObjectLikeStats)
    function_like_stats: FunctionLikeStats = field(default_factory=FunctionLikeStats)

    # Could happen for object-like or function-like macros
    skipped_function_ptr: int = 0
    skipped_decl_ref_expr: int = 0

    @property
    def total_translated(self) -> int:
        return self.object_like_stats.total_translated + self.function_like_stats.total_translated

    @property
    def total_skipped(self) -> int:
        return self.object_like_stats.total_skipped + self.function_like_stats.total_skipped

    def __str__(self) -> str:
        return (
                f"Total translated: {self.total_translated}\n"
                f"Total skipped: {self.total_skipped}\n"
                f"{self.object_like_stats}\n"
                f"{self.function_like_stats}"
                )

