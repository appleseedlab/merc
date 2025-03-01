# MerC

A Python tool for detecting and translating easy to translate C macros

## Dependencies:
- Python 3.10
- [Maki](https://github.com/appleseedlab/maki)

## Instructions for using MerC
### 1. Download and extract source for target program.

For example, if running on bc:
```
PROGRAM_DIRECTORY="./programs"
mkdir $PROGRAM_DIRECTORY
wget https://mirrors.kernel.org/gnu/bc/bc-1.07.tar.gz
tar -xzf bc-1.07.tar.gz -C $PROGRAM_DIRECTORY
```
Ensure you have the bc dependencies:
```
apt-get install ed
apt-get install texinfo
```
### 2. Use Bear or cmake to intercept the build process to create a `compile_commands.json`

For example, if running on bc:
```
cd $PROGRAM_DIRECTORY/bc-1.07 # Replace with your program src dir
bear -- ./configure
bear -- make
```

Alternatively, programs using CMake can use the `CMAKE_EXPORT_COMPILE_COMMANDS` environment variable to generate a `compile_commands.json` file in the build directory, i.e
```
export CMAKE_EXPORT_COMPILE_COMMANDS=on
# Continue with normal Cmake commands.
```

You should now have a `compile_commands.json` in the directory of your target program.

### 3. Run `run_maki_on_compile_commands.py` from MerC 

MerC needs an analysis of macros within each source file. `run_maki_on_compile_commands.py` will facilitate running Maki on each file in the `compile_commands.json`, and outputting a single analysis file for MerC.

The format for running the script is as follows:
```
python3 run_maki_on_compile_commands.py \
    -p <path to maki plugin> \
    -i <target program source directory> \
    -c <path to program's compile_commands.json> \
    -o <path to output maki analysis file, default is analysis.maki> \
    -j <number of threads, default is number of CPUs on system> \
    -v <verbose> \
    --cache-dir <optional, use directory to store intermediate analysis results> 
```

For example, running on bc may look like this: 
```
MAKI_DIR="../maki"
python3 run_maki_on_compile_commands.py \
    -p $MAKI_DIR/build/lib/libmaki.so \
    -i $PROGRAM_DIRECTORY/bc-1.07/ \
    -c $PROGRAM_DIRECTORY/bc-1.07/compile_commands.json
```

You should now have a generated `analysis.maki` file in the MerC directory (unless you specified another output directory) 

### 4. Run `emit_translations.py` on the `analysis.maki` file 

The format for running the script is as follows: 

```
python3 emit_translations.py \
    -i <(required) path to target program source directory> \
    -m <(required) path to maki analysis file> \
    -o <(required) path to output directory for translation> \
    [--read-only, --no-read-only] <(optional) set or don't set output translations to read only. Read-only is the default.> \
    -v <(optional) specify for verbose output> \
    --output-csv <(optional) CSV file to output translation info to> \
    --program-name <(optional) program name in CSV output> \
    --int-size <(optional) size of int type on platform>
```

For example, running on bc may look like this: 
```
# copy bc's code to a new directory
cp -r $PROGRAM_DIRECTORY/bc-1.07 $PROGRAM_DIRECTORY/bc-1.07-translated

python3 emit_translations.py -i $PROGRAM_DIRECTORY/bc-1.07/ -m analysis.maki -o $PROGRAM_DIRECTORY/bc-1.07-translated
```

You should now have a translated source for your target program.
