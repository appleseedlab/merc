import argparse
import os
from analyze_transformations import Macro, PreprocessorData, InvocationPredicate, Invocation, get_interface_equivalent_preprocessordata, get_interface_equivalent_translations


def translate_src_files(src_dir: str, out_dir: str, translations: dict[Macro, str]) -> None:
    # dict of src files to their contents in lines
    src_file_contents : dict[str, list[str]] = {}
    for macro, translation in translations.items():
        # If we don't have a translation for this macro, skip it
        if translation is None:
            continue

        # open the source file
        startDefLocParts = macro.DefinitionLocation.split(":")
        endDefLocParts = macro.EndDefinitionLocation.split(":")

        src_file_path = startDefLocParts[0]

        # only open files in src dir
        if not src_file_path.startswith(src_dir):
            print(f"Skipping {src_file_path} because it is not in the source directory {src_dir}")
            continue

        print(f"Translating {src_file_path}")

        src_file_content: list[str] = None

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

        for i in range(startLine, endLine + 1):
            src_file_content[i] = '\n'

        print(f"Translation: {translation}")

        # Insert the translation
        src_file_content[startLine] = translation + '\n'

    for src_file_path, src_file_content in src_file_contents.items():
        dst_file_path = os.path.join(out_dir, os.path.relpath(src_file_path, src_dir))
        os.makedirs(os.path.dirname(dst_file_path), exist_ok=True)
        with open(dst_file_path, 'w') as f:
            f.writelines(src_file_content)



def main():
    args = argparse.ArgumentParser()

    args.add_argument('input_src_dir', type=str)
    args.add_argument('maki_results_path', type=str)
    args.add_argument('translation_output_dir', type=str)

    args = args.parse_args()


    input_src_dir = os.path.abspath(args.input_src_dir)
    maki_results_path = os.path.abspath(args.maki_results_path)
    translation_output_dir = args.translation_output_dir

    translations = get_interface_equivalent_translations(maki_results_path)
    translate_src_files(input_src_dir, translation_output_dir, translations)


if __name__ == '__main__':
    main()

