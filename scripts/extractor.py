import argparse
import gzip
import os
import re
import shutil
import sys
import tarfile
import urllib.request

import requests
from tqdm import tqdm

from texphage.demacro import demacro
from texphage.unfold import unfold

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


def process_arxiv_id(id, output_dir, force):
    # Set up output directory
    id_output_dir = os.path.join(output_dir, id)
    try:
        os.makedirs(id_output_dir, exist_ok=force)
    except OSError:
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

    tex = unfold(raw_data)
    expanded_tex, packages, problems = demacro(tex)
    os.makedirs('cache/unfolded_tex', exist_ok=True)
    with open(os.path.join('cache/unfolded_tex', id + '.tex'), 'w') as f:
        f.write(tex)

    return tex


def get_all_arxiv_ids(num, category, year) -> list[str]:
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

    ids = []

    if args.mode == 'top':
        num = int(args.args[0])
        print(num)
        category = args.args[1]
        print(category)
        year = "24"
        ids = get_all_arxiv_ids(num, category, year)

    if args.mode == 'ids':
        ids = args.args

    process_arxiv_ids(ids, args.out, args.force)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Extract tikzcd from Latex')
    parser.add_argument('-m', '--mode', required=True, choices=['top', 'ids'],
                        help='Source: top=latest N papers in category, ids=specific arXiv IDs')
    parser.add_argument(nargs='*', dest='args', default=[])
    parser.add_argument('-o', '--out', help='output directory')
    parser.add_argument('-s', '--save', type=str,
                        help='Save uncompressed files here (default: temp only)')
    parser.add_argument('-f', '--force', action='store_true',
                        help='Overwrite existing output for an arXiv ID')
    parser.add_argument('-l', '--memory_limit', help='Set a max memory limit')

    main(parser.parse_args())
