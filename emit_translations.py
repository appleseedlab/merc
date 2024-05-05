import argparse
import os
import analyze_transformations
from analyze_transformations import Macro, PreprocessorData, InvocationPredicate, Invocation, get_interface_equivalent_preprocessordata, get_interface_equivalent_translations


def get_ie_pd_on_directory(results_dir: str) -> list[dict[Macro, str]]:
    translations = []
    for root, dirs, files in os.walk(results_dir):
        for file in files:
            if file.endswith('.maki'):
                translation = get_interface_equivalent_translations(os.path.join(root, file))
                
                for macro, translation in translation.items():
                    print(f"{macro} -> {translation}")





def main():
    args = argparse.ArgumentParser()

    args.add_argument('input_src_dir', type=str)
    args.add_argument('maki_results_dir', type=str)
    args.add_argument('translation_output_dir', type=str)

    args = args.parse_args()

    input_src_dir = args.input_src_dir
    maki_results_dir = args.maki_results_dir
    translation_output_dir = args.translation_output_dir

    get_ie_pd_on_directory(maki_results_dir)


if __name__ == '__main__':
    main()

