import sys
import os
import hashlib
import stat
import optparse

BLOCK_SIZE = 64*1024


class HashIndex(object):

    INDEX_SIZE = 1
    INDEX_HASH = 2
    INDEX_SIZE_HASH = 4
    INDEX_FILENAME = 8

    def __init__(self, fname):
        self.index_fname = fname
        self.i_by_size = {}
        self.i_by_hash = {}
        self.i_by_size_hash = {}
        self.i_by_filename = {}

    def load(self, index):
        fp = open(self.index_fname)
        for l in fp:
            l = l.strip()
            size, hash, filename = l.split(None, 2)
            size = int(size)
            entry = [size, hash, filename, False]
            if index & self.INDEX_SIZE:
                self.i_by_size[size] = entry
            if index & self.INDEX_HASH:
                self.i_by_hash[hash] = entry
            if index & self.INDEX_SIZE_HASH:
                self.i_by_size_hash[(size, hash)] = entry
            if index & self.INDEX_FILENAME:
                self.i_by_filename[filename] = entry

    def by_filename(self, filename):
        return self.i_by_filename.get(filename)

    def mark(self, filename):
        self.i_by_filename[filename][3] = True

    def unmarked(self):
        for entry in self.i_by_filename.itervalues():
            if not entry[3]:
                yield entry

def hash_file(fname):
    fp = open(fname)
    hasher = hashlib.md5()
    while True:
        block = fp.read(BLOCK_SIZE)
        if not block:
            break
        hasher.update(block)
    fp.close()
    return hasher.hexdigest()

def format_index_entry(size, hash, fullname):
    return "%10d  %s  %s\n" % (size, hash, fullname)

def output_index_entry(fullname, out_fp, prefix=""):
        st = os.stat(fullname)
        out_fp.write(prefix + format_index_entry(st[stat.ST_SIZE], hash_file(fullname), fullname))

def index_directory(path, out_fp, index=None, prefix=""):
    for dirpath, dirnames, filenames in os.walk(path):
        for fname in filenames:
            fullname = os.path.join(dirpath, fname)
            if index and index.by_filename(fullname):
                index.mark(fullname)
                continue
            output_index_entry(fullname, out_fp, prefix)

oparser = optparse.OptionParser(usage="%prog <command> <index file>")
oparser.add_option('-c', '--create', action="store_true", help="Create index")
oparser.add_option('', '--changes', action="store_true", help="Show changes between index and directory")

(options, args) = oparser.parse_args()
if len(args) < 2:
    oparser.error("Not enough arguments")


if options.create:
    out_fp = open(args[0], "w")
    index_directory(args[1], out_fp)
    out_fp.close()
elif options.changes:
    index = HashIndex(args[0])
    index.load(HashIndex.INDEX_FILENAME)
    index_directory(args[1], sys.stdout, index, '+')
    dir = args[1]
    if dir[-1] != '/':
        dir += '/'
    for e in index.unmarked():
        if e[2].startswith(dir):
            sys.stdout.write('-' + format_index_entry(*e[0:3]))
else:
    oparser.error("No command")
