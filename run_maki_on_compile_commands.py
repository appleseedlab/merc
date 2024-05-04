import argparse
from dataclasses import dataclass
import os
import json
import subprocess

@dataclass(frozen=True)
class CompileCommand:
    directory: str
    arguments: list[str]
    file: str

    @staticmethod
    def from_json(json: dict):
        return CompileCommand(
            directory=json["directory"],
            arguments=json["arguments"],
            file=json["file"]
        )


def run_maki_on_compile_command(cc: CompileCommand, src_dir: str, maki_so_path: str, out_dir: str):
    # Enter source directory
    os.chdir(src_dir)

    print(os.path.relpath(cc.file, src_dir))

    args = cc.arguments
    # pass cpp2c plugin shared library file
    args[0] = "clang"
    args.insert(1, f'-fplugin={maki_so_path}')
    # at the very end, specify that we are only doing syntactic analysis
    # so as to not waste time compiling
    args.append('-fsyntax-only')

    dst_file = os.path.join(out_dir, os.path.relpath(cc.file, src_dir))

    # Create the output directory if it doesn't exist
    os.makedirs(os.path.dirname(dst_file), exist_ok=True)

    # Change the file extension to .maki
    root, _ = os.path.splitext(dst_file)
    dst_file = root + '.maki'

    print(" ".join(args))
    with open(dst_file, 'w') as ofp:
        os.chdir(os.path.dirname(cc.file))
        process = subprocess.run(args, stdout=ofp, stderr=subprocess.PIPE)

        # stderr
        if process.stderr:
            print(process.stderr)



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("maki_so_path", type=str)
    ap.add_argument("src_dir", type=str)
    ap.add_argument("compile_commands", type=str)
    ap.add_argument("out_dir", type=str)
    args = ap.parse_args()

    maki_so_path = os.path.abspath(args.maki_so_path)
    src_dir = os.path.abspath(args.src_dir)
    compile_commands = os.path.abspath(args.compile_commands)
    out_dir = os.path.abspath(args.out_dir)

    # Load the compile_commands.json file (fail if it doesn't exist)
    try:
        with open(compile_commands) as fp:
            compile_commands = json.load(fp)
    except FileNotFoundError:
        print(f"Could not find compile_commands.json in {src_dir}")
    
    compile_commands = [CompileCommand.from_json(cc) for cc in compile_commands]

    for cc in compile_commands:
        run_maki_on_compile_command(cc, src_dir, maki_so_path, out_dir)

if __name__ == "__main__":
    main()
