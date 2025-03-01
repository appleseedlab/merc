#!/usr/bin/python3

import argparse
import logging
import os
import pathlib

from stat import S_IREAD, S_IRGRP, S_IROTH
from analyze_transformations import get_tlna_src_preprocessordata
from macros import Macro
from macrotranslator import MacroTranslator
from translationconfig import TranslationConfig, IntSize

logger = logging.getLogger(__name__)


def translate_src_files(src_dir: pathlib.Path,
                        out_dir: pathlib.Path,
                        translations: dict[Macro, str | None],
                        read_only: bool) -> None:
    # dict of src files to their contents in lines
    src_file_contents: dict[str, list[str]] = {}
    for macro, translation in translations.items():
        # If we don't have a translation for this macro, skip it
        if translation is None:
            continue

        # open the source file
        startDefLocParts = macro.DefinitionLocation.split(":")
        endDefLocParts = macro.EndDefinitionLocation.split(":")

        src_file_path = startDefLocParts[0]

        # only open files in src dir
        if not src_file_path.startswith(str(src_dir)):
            logger.warning(f"Skipping {src_file_path} because it is not in the source directory {src_dir}")
            continue

        logger.info(f"Translating {src_file_path}")

        src_file_content: list[str]

        if src_file_path not in src_file_contents:
            with open(src_file_path, 'r') as f:
                src_file_contents[src_file_path] = f.readlines()
                src_file_content = src_file_contents[src_file_path]
        else:
            src_file_content = src_file_contents[src_file_path]

        # replace macro with translation
        # Clear lines between start and end definition location
        startLine = int(startDefLocParts[1]) - 1
        endLine = int(endDefLocParts[1]) - 1

        endLineContent = src_file_content[endLine]

        # Some code bases may define macros with an opening comment on the last line,
        # preserve it here
        # TODO(Joey): This is a really hacky way to do this, look into a parser for this.
        endLineComment = ''
        if '/*' in endLineContent.strip() and '*/' not in endLineContent.strip():
                endLineComment = '/*' + endLineContent.split('/*', 1)[1]

        for i in range(startLine, endLine + 1):
            src_file_content[i] = '\n'

        logger.debug(f"Translation for {src_file_path}: {translation}")

        # Insert the translation
        src_file_content[startLine] = translation

        # Append the comment back to the end of the line
        src_file_content[endLine] += endLineComment + '\n'

    for src_file_path, src_file_content in src_file_contents.items():
        dst_file_path = os.path.join(out_dir, os.path.relpath(src_file_path, src_dir))
        os.makedirs(os.path.dirname(dst_file_path), exist_ok=True)
        with open(dst_file_path, 'w') as f:
            f.writelines(src_file_content)

        if read_only:
            os.chmod(dst_file_path, S_IREAD|S_IRGRP|S_IROTH)


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument('-i', '--input_src_dir', type=pathlib.Path, required=True,
                    help='Path to the program source directory')
    ap.add_argument('-m', '--maki_analysis_file', type=pathlib.Path, required=True,
                    help='Path to the maki analysis file.')
    ap.add_argument('-o', '--output_translation_dir', type=pathlib.Path, required=True,
                    help='Output directory for translated source files.')
    ap.add_argument('--read-only', action=argparse.BooleanOptionalAction, default=True,
                    help="Set or don't set output translations to read-only. On by default.")
    ap.add_argument('-v', '--verbose', action='store_true',
                    help='Enable verbose logging')
    ap.add_argument('--output-csv', type=pathlib.Path, required=False,
                    help='Output the macro translations to a CSV file.')
    ap.add_argument('--program-name', type=str, required=False,
                    help='Name of the program being translated. Used in the CSV output.')

    # Translation args
    ap.add_argument('--int-size', type=int, choices=[size.value for size in IntSize], default=IntSize.Int32,
                    help='Size of int type in bits')

    args = ap.parse_args()

    input_src_dir = args.input_src_dir.resolve()
    maki_analysis_path = args.maki_analysis_file.resolve()
    output_translation_dir = args.output_translation_dir.resolve()
    read_only = args.read_only

    translation_config = TranslationConfig.from_args(args)

    log_level = logging.INFO if args.verbose else logging.WARNING
    logging.basicConfig(level=log_level)

    tlna_src_pd = get_tlna_src_preprocessordata(maki_analysis_path)
    translator = MacroTranslator(translation_config)
    translations = translator.generate_macro_translations(tlna_src_pd)

    translate_src_files(input_src_dir, output_translation_dir, translations, read_only) 

    translator.translation_stats.print_totals()
    if args.output_csv:
        path = os.path.abspath(args.output_csv)
        program_name = args.program_name or input_src_dir.name
        translator.translation_stats.output_csv(path, program_name)


if __name__ == '__main__':
    main()
