import argparse
import os
from analyze_transformations import Macro, PreprocessorData, InvocationPredicate, Invocation, get_interface_equivalent_preprocessordata, get_interface_equivalent_translations


def get_interface_translations_on_dir(results_dir: str) -> list[dict[Macro, str]]:
    translations : list[dict[Macro,str]] = []
    for root, dirs, files in os.walk(results_dir):
        for file in files:
            if file.endswith('.maki'):
                translation = get_interface_equivalent_translations(os.path.join(root, file))
                
                translations.append(translation)

    return translations


def translate_src_files(src_dir: str, out_dir: str, translations: list[dict[Macro, str]]) -> None:
    # compress into one dictionary
    translation_dict = {} 
    for translation in translations:
        for macro, translation in translation.items():
            translation_dict[macro] = translation

    # dict of src files to their contents in lines
    src_file_contents : dict[str, list[str]] = {}
    for macro, translation in translation_dict.items():
        # open the source file
        startDefLocParts = macro.DefinitionLocation.split(":")
        endDefLocParts = macro.EndDefinitionLocation.split(":")

        src_file_path = startDefLocParts[0]

        # only open files in src dir
        if not src_file_path.startswith(src_dir):
            print(f"Skipping {src_file_path} because it is not in the source directory {src_dir}")
            continue

        dst_file_path = os.path.join(out_dir, os.path.relpath(src_file_path, src_dir))

        

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

        # write the new source file

        with open(dst_file_path, 'w') as f:
            f.writelines(src_file_content)



def main():
    args = argparse.ArgumentParser()

    args.add_argument('input_src_dir', type=str)
    args.add_argument('maki_results_dir', type=str)
    args.add_argument('translation_output_dir', type=str)

    args = args.parse_args()


    input_src_dir = os.path.abspath(args.input_src_dir)
    maki_results_dir = os.path.abspath(args.maki_results_dir)
    translation_output_dir = args.translation_output_dir

    translations = get_interface_translations_on_dir(maki_results_dir)
    translate_src_files(input_src_dir, translation_output_dir, translations)


if __name__ == '__main__':
    main()

