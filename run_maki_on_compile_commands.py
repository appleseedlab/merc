#!/usr/bin/python3

import argparse
import logging
import shlex
from dataclasses import dataclass
import os
import json
import subprocess
from functools import partial
import concurrent.futures
from typing import Any
import pathlib

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CompileCommand:
    directory: str
    arguments: list[str]
    file: str

    @staticmethod
    def from_json(json_file: dict) -> 'CompileCommand':

        # compile_commands.json can either have "arguments" or "command" key
        # We always want a list of arguments, so split command if there is no arguments list
        if "arguments" in json_file:
            arguments = json_file["arguments"]
        elif "command" in json_file:
            arguments = shlex.split(json_file["command"])
        else:
            raise ValueError("Compile command must have either 'arguments' or 'command' key")

        return CompileCommand(
            directory=json_file["directory"],
            arguments=arguments,
            file=json_file["file"]
        )

class AnalysisCache:
    def __init__(self, cache_dir: str) -> None:
        self.cache_dir = pathlib.Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

    def get_cached_result(self, cc: CompileCommand) -> list[dict[str, Any]] | None:
        cc_hash = hash(cc)

        cache_path = self.cache_dir / f"{cc_hash}.json"

        if cache_path.exists():
            try:
                with open(cache_path, 'r') as f:
                    logger.info(f"Loading {cc.file} from cache")
                    return json.load(f)
            except json.JSONDecodeError:
                logger.warning(f"Corrupted cache file for {cc.file} at path {cache_path}, ignoring")

        return None
        

    def cache_result(self, cc: CompileCommand, results: list[dict[str, Any]]) -> None:
        cc_hash = hash(cc)

        cache_path = self.cache_dir / f"{cc_hash}.json"

        with open(cache_path, 'w') as f:
            json.dump(results, f)


def run_maki_on_compile_command(cc: CompileCommand, maki_so_path: str, cache: AnalysisCache) -> list[dict[str, Any]]:

    if (result := cache.get_cached_result(cc)) is not None:
        return result

    # pass cpp2c plugin shared library file
    args = cc.arguments
    args[0] = "clang-17"
    args.insert(1, f'-fplugin={maki_so_path}')
    args.append(cc.file)
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

        logger.info(f"Compiling {cc.file} with args {' '.join(args)}")

        process = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

        # stderr
        if process.stderr:
            logger.warning(f"clang stderr with args {' '.join(args)}:")
            logger.warning(f"{process.stderr.decode()}")

        result = json.loads(process.stdout.decode())
        cache.cache_result(cc, result)

        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"ERROR ON file {cc.file} w/ returncode {e.returncode}\n"
                     f"Command: {' '.join(args)}\n"
                     f"{e.stderr.decode()}")
        return []

def is_source_file(arg: str) -> bool:
    return arg.endswith('.c')

def split_compile_commands_by_src_file(cc: CompileCommand) -> list[CompileCommand]:
    """
    Take a compile command and split it into multiple compile commands
    for each source file in the compile command
    """

    # Filter out all source files from the arguments
    arguments_no_src_files = [arg for arg in cc.arguments if not is_source_file(arg)]

    # Return a list of CompileCommands for each source file in the original compile command args
    return [
        CompileCommand(directory=cc.directory, arguments=arguments_no_src_files, file=src_file)
        for src_file in cc.arguments if is_source_file(src_file)
    ]
    

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
    ap.add_argument('--cache-dir', type=pathlib.Path, default=pathlib.Path('.maki_cache'),
                    help='Directory to store cached analysis results')
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

    # Split compile commands into multiple compile commands for each source file
    split_compile_commands = [split_cc for cc in compile_commands 
                           for split_cc in split_compile_commands_by_src_file(cc)]

    # Run maki on each compile command threaded
    cache = AnalysisCache(args.cache_dir)
    with concurrent.futures.ProcessPoolExecutor(max_workers=num_jobs) as executor:
        results = list(
            executor.map(
                partial(run_maki_on_compile_command, maki_so_path=plugin_path, cache=cache),
                split_compile_commands
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
