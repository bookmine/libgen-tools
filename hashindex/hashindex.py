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

def output_existing_entry(entry, params):
    params["fp"].write(params.get("prefix", "") + format_index_entry(*entry[0:3]))

def output_new_entry(fullname, params):
    st = os.stat(fullname)
    params["fp"].write(params.get("prefix", "") + format_index_entry(st[stat.ST_SIZE], hash_file(fullname), fullname))

def index_directory(path, index=None, params={}, on_match=None, on_miss=None):
    """Recursively scan directory. For each file found, if index given, look
    it up there. If found, mark file in index, call on_match function if any.
    Otherwise, call on_miss function.
    """
    for dirpath, dirnames, filenames in os.walk(path):
        for fname in filenames:
            fullname = os.path.join(dirpath, fname)
            if index:
                e = index.by_filename(fullname)
                if e:
                    index.mark(fullname)
                    on_match and on_match(e, params)
                    continue
            on_miss and on_miss(fullname, params)

oparser = optparse.OptionParser(usage="%prog <command> <index file>")
oparser.add_option('-c', '--create', action="store_true", help="Create index")
oparser.add_option('', '--changes', action="store_true", help="Show changes between index and directory")
oparser.add_option('-u', "--update", action="store_true", help="Update index")

(options, args) = oparser.parse_args()
if len(args) < 2:
    oparser.error("Not enough arguments")


if options.create:
    out_fp = open(args[0], "w")
    index_directory(args[1], on_miss=output_new_entry, params={"fp": out_fp})
    out_fp.close()
elif options.changes:
    index = HashIndex(args[0])
    index.load(HashIndex.INDEX_FILENAME)
    # Output only files not existing in index
    params = {"fp": sys.stdout, "prefix": "+"}
    index_directory(args[1], index, on_miss=output_new_entry, params=params)
    # Now unmarked files in index - deleted from dir
    dir = args[1]
    # Make sure we compare complete path components and don't match "/foo" with "/foobar"
    if dir[-1] != '/':
        dir += '/'
    for e in index.unmarked():
        if e[2].startswith(dir):
            params["prefix"] = "-"
            output_existing_entry(e, params=params)
elif options.update:
    index = HashIndex(args[0])
    index.load(HashIndex.INDEX_FILENAME)
    out_fp = open(args[0] + ".tmp", "w")
    # Just calc hash and dump for new files, and re-dump existing entries
    # Old entries are automagically gone
    index_directory(args[1], index, on_miss=output_new_entry, on_match=output_existing_entry, params={"fp": out_fp})
    out_fp.close()
    os.rename(args[0] + ".tmp", args[0])
else:
    oparser.error("No command")
