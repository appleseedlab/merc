#!/usr/bin/python3

import argparse
import logging
from dataclasses import dataclass
import os
import json
import subprocess
from functools import partial
import concurrent.futures
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CompileCommand:
    directory: str
    arguments: list[str]
    file: str

    @staticmethod
    def from_json(json_file: dict) -> 'CompileCommand':
        return CompileCommand(
            directory=json_file["directory"],
            arguments=json_file["arguments"],
            file=json_file["file"]
        )


def run_maki_on_compile_command(cc: CompileCommand, maki_so_path: str) -> dict[str, Any]:

    args = cc.arguments
    # pass cpp2c plugin shared library file
    args[0] = "clang"
    args.insert(1, f'-fplugin={maki_so_path}')
    args[-1] = cc.file
    # at the very end, specify that we are only doing syntactic analysis
    # so as to not waste time compiling
    args.append('-fsyntax-only')

    # Add ignore flags for system headers, builtins, and invalid locations
    args.append('-fplugin-arg-maki---no-system-macros')
    args.append('-fplugin-arg-maki---no-builtin-macros')
    args.append('-fplugin-arg-maki---no-invalid-macros')


    try:
        # lot of build processes do include paths relative to source file directory
        os.chdir(cc.directory)

        logger.info(f"Compiling {cc.file} with args {" ".join(args)}")

        process = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # stderr
        if process.stderr:
            logger.warning(f"clang stderr with args {" ".join(args)}:")
            logger.warning(f"{process.stderr.decode()}")

        return json.loads(process.stdout.decode())
    except subprocess.CalledProcessError as e:
        logger.exception(f"Error running maki with args {args} on {cc.file}: {e}")
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-p', '--plugin_path', type=str, required=True,
                    help='Path to maki clang plugin')
    ap.add_argument('-i', '--input_src_dir', type=str, required=True,
                    help='Path to program source directory')
    ap.add_argument('-c', '--compile_commands', type=str, required=True,
                    help='Path to compile_commands.json')
    ap.add_argument('-o', '--analysis_out_path', type=str, default='analysis.maki',
                    help='Path to output maki analysis file. Default is analysis.maki')
    ap.add_argument('-j', '--num_jobs', type=int, default=os.cpu_count(),
                    help='Number of threads to use. Default is number of CPUs on system')
    ap.add_argument('-v', '--verbose', action='store_true')
    args = ap.parse_args()

    plugin_path = os.path.abspath(args.plugin_path)
    src_dir = os.path.abspath(args.input_src_dir)
    compile_commands = os.path.abspath(args.compile_commands)
    analysis_out_path = os.path.abspath(args.analysis_out_path)
    num_jobs = args.num_jobs

    log_level = logging.INFO if args.verbose else logging.WARNING
    logging.basicConfig(level=log_level)

    # Load the compile_commands.json file (fail if it doesn't exist)
    try:
        with open(compile_commands) as fp:
            compile_commands = json.load(fp)
    except FileNotFoundError:
        logger.critical(f"Could not find compile_commands.json in {src_dir}")
        return

    compile_commands = [CompileCommand.from_json(cc) for cc in compile_commands]


    # Run maki on each compile command threaded
    with concurrent.futures.ProcessPoolExecutor(max_workers=num_jobs) as executor:
        results = list(
            executor.map(
                partial(run_maki_on_compile_command, maki_so_path=plugin_path),
                compile_commands
            )
        )

    # Collect results (JSON Arrays) into one large JSON Array
    # Doing this to avoid duplicates, which there was many of especially for compiler builtins
    results_set = set()
    for result in results:
        # merge into set
        for obj in result:
            obj_tuple = tuple(obj.items())
            results_set.add(obj_tuple)

    results = [dict(obj) for obj in results_set]

    # Write results to file 
    with open(analysis_out_path, 'w') as out:
        json.dump(results, out)


if __name__ == "__main__":
    main()
