import argparse
import shutil
import os
import glob
import gzip
import sys
import argparse
import tarfile
import requests
import urllib.request
from tqdm import tqdm
from typing import List

sys.path.append('.')

class ExistingOutput(Exception):
    def __init__(self, message):
        super().__init__(message)

def gunzip_file(gz_file, unzipped_file):
    with gzip.open(gz_file, 'rt', encoding="utf-8") as gzf, open(unzipped_file, 'w') as f:
        f.write(gzf.read())

# https://stackoverflow.com/questions/480214/how-do-i-remove-duplicates-from-a-list-while-preserving-order
def dedup_preserve_order(list):
    seen = set()
    seen_add = seen.add
    return [x for x in list if not (x in seen or seen_add(x))]

def write_output(codes, pngs, output_dir):
    with open(os.path.join(output_dir, "tikzcd.txt"), 'w') as f:
        f.write("\n".join(codes))
    return len(codes)

def process_arxiv_ids(ids, output_dir, force):
    print(f"Processing {len(ids)} IDs...")

    for id in tqdm(ids) if len(ids) > 1 else ids:
        try:
            process_arxiv_id(id, output_dir, force)
        except ExistingOutput as path:
            print(f"{path} already exists, skipping this ID. Overwrite with --force")
        except Exception as e:
            print(f"Failed processing for id={id}, error={e}")

def arxiv_find_main(id_output_dir):
    main = ''
    try:
        readme = open(os.path.join(id_output_dir, '00README.XXX'), 'r', encoding='utf-8').read()
        filename = re.search(r'^\s*(.*)\.tex\s*toplevelfile\s*$', readme, flags=re.MULTILINE).group(1) + '.tex'
        # print(f"Found main arxiv file in directory %s: %s" %(id_output_dir, filename))
        main = open(os.path.join(id_output_dir, filename), 'r', encoding='utf-8').read()
    except FileNotFoundError:
        for filename in glob.glob('*.tex', root_dir = id_output_dir):
            tex = open(os.path.join(id_output_dir, filename), 'r', encoding='utf-8').read()
            if re.search(r'\\documentclass', tex):
                main = open(os.path.join(id_output_dir, filename), 'r', encoding='utf-8').read()
                # print(f"Found main arxiv file in directory %s: %s" %(id_output_dir, filename))
                break
    except Exception as e:
        print(f"Error while finding main arxiv file in directory %s: {e}" %id_output_dir)
    return main
    
find_input = r'''
    ^[^%\n]*
    (?<input>\\input\s*\{\s*(?<input_path>.*?)\s*\})    |
    (?<include>\\include\s*\{\s*(?<include_path>.*?)\s*\})    |
    (?<usepkg>\\usepackage\s*\{\s*(?<usepkg_path>.*?)\s*\})    |
    (?<import>\\import\s*\{\s*(?<import_path>.*?)\s*\}\s*\{\s*(?<import_file>.*?)\s*\})   |
    (?<subimport>\\subimport\s*\{\s*(?<subimport_path>.*?)\s*\}\s*\{\s*(?<subimport_file>.*?)\s*\})  |
    (?<subfile>\\subfile(?:include)\s*?\{\s*(?<subfile_path>.*?)\s*\})
'''
find_input = re.sub(r'\s+', '', find_input)

def file_replacement(directory):
    def replacement(match):
        if match.group('input'):
            if re.search(r'\.', match.group('input_path')):
                path = match.group('input_path')
            else:
                path = match.group('input_path') + '.tex'
            try:
                called_file = open(os.path.join(directory, path), 'r', encoding='utf-8').read()
            except FileNotFoundError:
                print("FileNotFoundError: Couldn't open the file called by %s at %s"  %(match.group(0), os.path.join(directory, path)))
                return match.group(0)
            else:
                return arxiv_unfold_dir(directory, main = called_file)
        elif match.group('include'):
            path = match.group('include_path') + '.tex'
            try:
                called_file = '\n' + r'\clearpage' + '\n' + open(os.path.join(directory, path), 'r', encoding='utf-8').read() + '\n' + r'\clearpage' + '\n'
            except FileNotFoundError:
                print("FileNotFoundError: Couldn't open the file called by %s at %s"  %(match.group(0), os.path.join(directory, path)))
                return match.group(0)
            else:
                return arxiv_unfold_dir(directory, main = called_file)
        elif match.group('usepkg'):
            unfolded = ''
            for called_package in re.finditer(r'[a-z0-9\+\-\.]+', match.group('usepkg_path')):
                path = called_package[0] + '.sty'
                try:
                    unfolded += '\n' + r'\makeatletter' + '\n' + arxiv_unfold_dir(directory, main = open(os.path.join(directory, path), 'r', encoding='utf-8').read()) + '\n' + r'\makeatother' + '\n'
                except FileNotFoundError:
                    unfolded += r'\usepackage{' + called_package[0] + '}\n'
            return unfolded
        else:
            print("The command %s is not implemented yet" %match.group(0))
            return match.group(0)
    return replacement

def arxiv_unfold_dir(id_output_dir, main = None):
    if main is None:
        main = arxiv_find_main(id_output_dir)
    replacement = file_replacement(id_output_dir)
    return re.sub(find_input, replacement, main, flags=re.MULTILINE)

def process_arxiv_id(id, output_dir, force):
    # Set up output directory
    id_output_dir = os.path.join(output_dir, id)
    try:
        os.makedirs(id_output_dir, exist_ok=force)
    except OSError as e:
        raise ExistingOutput(id_output_dir)

    # Download the raw data
    downloaded_data = os.path.join(id_output_dir, 'tmp_data')
    url = 'https://export.arxiv.org/e-print/' + id
    urllib.request.urlretrieve(url, downloaded_data)

    raw_data = os.path.join(id_output_dir, "raw_data")
    os.makedirs(raw_data, exist_ok=True)

    try:
        with tarfile.open(downloaded_data, 'r') as tf:
            tf.extractall(raw_data)
    except tarfile.ReadError:
        unzipped_file = os.path.join(raw_data, "source.tex")
        try:
            gunzip_file(downloaded_data, unzipped_file)
        except gzip.BadGzipFile:
            shutil.copy(downloaded_data, unzipped_file)

    os.remove(downloaded_data)
    
    tex = arxiv_unfold_dir(raw_data)
    with open(os.path.join('dataset/unfolded_tex', id + '.tex'), 'w') as f:
        f.write(tex)

    return tex
    
def get_all_arxiv_ids(num, category, year) -> List[str]:
    print(f"Getting first {num} arxiv ID's from {category} in year {year}...")

    arxiv_id_regex = re.compile(r'(?<!\d)(\d{4}\.\d{5})(?!\d)')
    url = f"https://arxiv.org/list/{category}/{year}?skip=0&show={num}"
    print(url)
    content = requests.get(url).text
    # We slice it at num because sometimes arxix returns a few more ID's than we asked for.
    return dedup_preserve_order([id for id in arxiv_id_regex.findall(content)])[:num]

def main(args):
    if args.out is None:
        print("Output directory (-o) is missing")
        return
    elif not os.path.exists(args.out):
        print(f"Output directory '{args.out}' does not exist")
        return
    
    if args.memory_limit is None:
        # Default to 3GB for now
        args.memory_limit = 3*(1 << 30)
    
    #P# This was creating issues for me: to be fixed.
    # resource.setrlimit(resource.RLIMIT_RSS, (args.memory_limit, args.memory_limit))
    
    ids = []

    if args.mode == 'top':
        num = int(args.args[0])
        print(num)
        category = args.args[1]
        print(category)
        year = "24" #"pastyear"
        ids = get_all_arxiv_ids(num, category, year)

    if args.mode == 'ids':
        ids = args.args

    process_arxiv_ids(ids, args.out, args.force)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Extract tikzcd from Latex')
    parser.add_argument('-m', '--mode', required=True, choices=['top', 'ids'],
                        help='Where to extract code from: \n \
                                top:  Get n latest papers in a given category using the arxiv category encoding. (Usage: python arxiv.py -m top <n> <category>)\n \
                                ids:  Specific arxiv ids (Usage:python arxiv.py -m id <ids>)')
    parser.add_argument(nargs='*', dest='args', default=[])
    parser.add_argument('-o', '--out', help='output directory')
    parser.add_argument('-s', '--save', type=str, help='When downloading files from arxiv. Where to save uncompressed files. Default: Only temporary')
    parser.add_argument('-f', '--force', action='store_true', help='If output for this arxiv id already exists, overwrite it')
    parser.add_argument('-l', '--memory_limit', help='Set a max memory limit')

    main(parser.parse_args())