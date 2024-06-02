#!/usr/bin/python3

import argparse
import logging
from dataclasses import dataclass
import os
import json
import subprocess
import concurrent.futures
import queue

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CompileCommand:
    directory: str
    arguments: list[str]
    file: str

    @staticmethod
    def from_json(json: dict) -> 'CompileCommand':
        return CompileCommand(
            directory=json["directory"],
            arguments=json["arguments"],
            file=json["file"]
        )


def run_maki_on_compile_command(cc: CompileCommand, src_dir: str, maki_so_path: str, out_file_path: str,
                                result_queue: queue.Queue) -> None:
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

        result_queue.put(json.loads(process.stdout))
        # stderr
        if process.stderr:
            logger.warning(f"clang stderr: {process.stderr}")
    except subprocess.CalledProcessError as e:
        logger.exception(f"Error running maki with args {args} on {cc.file}: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--maki_so_path", type=str)
    ap.add_argument("--src_dir", type=str)
    ap.add_argument("--compile_commands", type=str)
    ap.add_argument("--maki_out_path", type=str, default="analysis.maki")
    ap.add_argument("--num_threads", type=int, default=os.cpu_count())
    ap.add_argument("-v", "--verbose", action='store_true')
    args = ap.parse_args()

    maki_so_path = os.path.abspath(args.maki_so_path)
    src_dir = os.path.abspath(args.src_dir)
    compile_commands = os.path.abspath(args.compile_commands)
    maki_out_path = os.path.abspath(args.maki_out_path)
    num_threads = args.num_threads

    log_level = logging.INFO if args.verbose else logging.WARNING
    logging.basicConfig(level=log_level)

    # Load the compile_commands.json file (fail if it doesn't exist)
    try:
        with open(compile_commands) as fp:
            compile_commands = json.load(fp)
    except FileNotFoundError:
        logger.critical(f"Could not find compile_commands.json in {src_dir}")

    compile_commands = [CompileCommand.from_json(cc) for cc in compile_commands]

    # Store results in queue
    result_queue = queue.Queue()

    # Run maki on each compile command threaded
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        for cc in compile_commands:
            executor.submit(run_maki_on_compile_command, cc, src_dir, maki_so_path, maki_out_path, result_queue)

    # Collect results (JSON Arrays) into one large JSON Array
    # Doing this to avoid duplicates, which there was many of especially for compiler builtins
    results_set = set()
    while not result_queue.empty():
        # merge into set
        res = result_queue.get()
        for obj in res:
            obj_tuple = tuple(obj.items())
            results_set.add(obj_tuple)

    results = [dict(obj) for obj in results_set]

    # Write results to file 
    with open(maki_out_path, 'w') as out:
        json.dump(results, out)


if __name__ == "__main__":
    main()
