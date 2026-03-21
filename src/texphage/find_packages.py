# This will read a latex file and recursively find all of its package dependencies.
# It also slowly build up a file that encodes the tree structure of latex packages dependencies, and a file that stores filepaths for these packages.
# The goal is that this creates a "minimal" list of packages to load to compile some document.

import regex as re
import subprocess
import pickle
import argparse
from texphage._regex import (
    embed_brackets, embed_braces, token, not_tokenizer_char,
    num_args, find_com, find_env, xparse,
)

find_file = re.compile(r'[a-z0-9\+\-\.]+')
find_pkg_lib = re.compile(r'^[^%%\n]*(?:\\(usepackage|RequirePackage)\s*%s\s*\{(?<packages>(?:[a-z0-9\+\-\.]+| |,)+)\}|\\use(?<type>tikz|pgf)library\s*\{(?<libraries>(?:[a-z0-9\+\-\.]+| |,)+)\})' %embed_braces('options'), flags=re.MULTILINE)

## This ones doesn't work (weird encoding) so you need to manually add it the first time
# texlive_dependencies['contour'] = ['contour', 'color', 'trig']

def get_path(file, tracker = False):
    if file in texlive_path:
        return texlive_path[file]
    else:
        if tracker:
            print("get_path: Getting location for " + file)
        if re.search(':', file):
            filename = re.sub(':','', file) + '.code.tex'
        else:
            filename = file + '.sty'
        path = subprocess.check_output(r'find /usr/local/texlive/2024/texmf-dist/tex -name ' + filename, shell=True).decode('utf-8').split('\n')[0]
        if path == '' and re.match('tikz', filename):
            filename = 'pgf' + filename[4:]
            path = subprocess.check_output(r'find /usr/local/texlive/2024/texmf-dist/tex -name ' + filename, shell=True).decode('utf-8').split('\n')[0]
        texlive_path[file] = path
        return path

def get_dependencies(file, dependencies = None, tracker = False):
    if dependencies is None:
        dependencies = []
    if file in texlive_dependencies:
        return texlive_dependencies[file]
    else:
        if tracker:
            print("get_dependencies: Getting dependencies for " + file)
        root = (dependencies == [])
        dependencies.append(file)
        try:
            path = get_path(file, tracker = tracker)
            code = open(path, 'r').read()
        except FileNotFoundError:
            print("FileNotFoundError: Couldn't find the package or library " + file + " at " + path)
            return [file]
        except UnicodeDecodeError:
            print("UnicodeDecodeError: Couldn't decode the package or library " + file + " at " + path)
            return [file]
        else:
            for match in find_pkg_lib.finditer(code):
                for package in find_file.finditer(match.group('packages') or ''):
                    if package[0] not in dependencies:
                        dependencies = get_dependencies(package[0], dependencies)
                for library in find_file.finditer(match.group('libraries') or ''):
                    if library[0] not in dependencies:
                        dependencies = get_dependencies(match.group('type') + 'library:' + library[0], dependencies)
            if root:
                texlive_dependencies[file] = dependencies
            return dependencies
        
def find_used_packages(tex, tracker = False):
    list_packages = []
    for match in find_pkg_lib.finditer(tex):
        for package in find_file.finditer(match.group('packages') or ''):
            if package[0] not in list_packages:
                list_packages += [i for i in get_dependencies(package[0], [], tracker = tracker) if i not in list_packages]
        for library in find_file.finditer(match.group('libraries') or ''):
            if library[0] not in list_packages:
                list_packages += [i for i in get_dependencies(match.group('type') + 'library:' + library[0], [], tracker = tracker) if i not in list_packages]
    return list_packages

def find_command(csname, list_packages, tracker = False):
    if re.search(r'[a-zA-Z]', csname):
        pattern_csname = r'(?:\{\s*\\%s\s*\}|\\%s[^a-zA-Z])' %(csname, csname)
    elif len(csname) == 1:
        pattern_csname = r'(?:\{\s*\\%s\s*\}|\\%s)' %(csname, csname)
    else:
        raise Exception('Incorrect Latex Command Format: the command must be either composed of letters only (as in [a-zA-Z]+) or of a single non-letter character (as in [^a-zA-Z])')
    pattern_env = r'''\\
        (
            (re)?newenvironmentx?    |
            (Declare|New|Renew|Provide)DocumentEnvironment  |
            NewEnviron    |
            newenviron
        )
        \s* \*? \s*
        %s
        ''' %pattern_csname
    pattern_cmd = r'''\\
        (
            (e|x|g)?def    |
            let     |
            ((re)?new|provide)commandx?     |
            (DeclareRobust|Check)Commandx?    |
            (New|Renew|Provide|Declare)(Expandable)?DocumentCommand
        )
        \s* \*? \s*
        %s
        ''' %pattern_csname
    pattern = re.compile(re.sub(r'\s+', '', pattern_env +'|' + pattern_cmd))
    for package in reversed(list_packages):
        if tracker:
            print('find_command: Searching for the command %s in %s' %(csname, package))
        try:
            path = get_path(package, tracker = tracker)
            code = open(path, 'r').read()
            if pattern.search(code):
                return package
        except FileNotFoundError:
            print("FileNotFoundError: Couldn't find the package " + package + " at " + path)
        except UnicodeDecodeError:
            print("UnicodeDecodeError: Couldn't decode package " + package + " at " + path)
    print(r"Couldn't find command %s in the provided list of packages" %csname)
    return ''

def main(args):
    tex = open(args.texfile, 'r').read()
    print('\nKnown Dependencies:')
    print(texlive_dependencies)
    print('\nKnown Paths:')
    print(texlive_path)
    if args.mode == 'tex':
        print(find_used_packages(tex, tracker = True))
    elif args.mode == 'cs':
        if args.cs:
            list_packages = find_used_packages(tex, tracker = True)
            print(list_packages)
            print(find_command(args.cs, list_packages, tracker = True))
        else:
            print("The argument '-c STRING' (where STRING is a latex command to find) is necessary for the 'cs' mode")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Find LaTeX packages')
    parser.add_argument('-m', '--mode', required=True, choices=['tex', 'cs'],
                        help='Two different operating modes: \n \
                                tex:  find all packages and tikz libraries called in a tex document\n \
                                cs:  finds in which package a specific command is defined within a document')
    parser.add_argument('-i', '--texfile', type=str, required=True, help='LateX source code file location')
    parser.add_argument('-c', '--cs', type=str, help='Command to find definition of in cs mode')
    with open('dataset/texlive_dependencies.pickle', 'rb') as file:
        texlive_dependencies = pickle.load(file)
    with open('dataset/texlive_path.pickle', 'rb') as file:
        texlive_path = pickle.load(file)
    main(parser.parse_args())
    with open('dataset/texlive_dependencies.pickle', 'wb') as file:
        pickle.dump(texlive_dependencies, file)
    with open('dataset/texlive_path.pickle', 'wb') as file:
        pickle.dump(texlive_path, file)