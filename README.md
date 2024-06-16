# MerC

A Python tool for detecting and translating easy to translate C macros

## Dependencies:
- Python 3.10
- [Maki](https://github.com/appleseedlab/maki)

## Instructions for using MerC
### 1. Download and extract source for target program.

For example, if running on bc:
```
wget https://mirrors.kernel.org/gnu/bc/bc-1.07.tar.gz
tar -xzf bc-1.07.tar.gz
```
Ensure you have the bc dependencies:
```
apt-get install ed
apt-get install texinfo
```
### 2. Use Bear or cmake to intercept the build process to create a `compile_commands.json`

For example, if running on bc, from within the bc directory: 
```
bear -- ./configure
bear -- make
```

You should now have a `compile_commands.json` in the directory of your target program.

### 3. Run `run_maki_on_compile_commands.py` from MerC 

The format for running the script is as follows:

```
python3 run_maki_on_compile_commands.py \
    -p <path to maki plugin> \
    -i <target program source directory> \
    -c <path to compile_commands.json> \
    -o <path to output maki analysis file, default is analysis.maki> \
    -j <number of threads, default is number of CPUs on system> \
    -v <verbose>
``` 

  
For example, running on bc may look like this: 
```
python3 run_maki_on_compile_commands.py \
    -p ../maki/build/lib/libmaki.so \
    -i ../bc-1.07/ \
    -c ../bc-1.07/compile_commands.json
```

You should now have a generated `analysis.maki` file in the MerC directory (unless you specified another output directory) 

### 4. Run `emit_translations.py` on the `analysis.maki` file 

The format for running the script is as follows: 

```
python3 emit_translations.py \
    -i <path to target program source directory> \
    -m <path to maki analysis file> \
    -o <(required) path to output directory for translation> \
    -v <verbose>
```

For example, running on bc may look like this: 
```
mkdir output
python3 emit_translations.py -i ../bc-1.07/ -m analysis.maki -o ./output
```
You should now have a translated source for your target program.
