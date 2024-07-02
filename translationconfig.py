import argparse
from enum import IntEnum
from dataclasses import dataclass

class IntSize(IntEnum):
    Int16 = 16
    Int32 = 32

@dataclass(frozen=True)
class TranslationConfig:
    int_size: IntSize = IntSize.Int32

    @classmethod
    def from_args(cls, args: argparse.Namespace):
        # automatically iterate over args w/ same field names
        return cls(**{field: getattr(args, field) for field in cls.__dataclass_fields__})
