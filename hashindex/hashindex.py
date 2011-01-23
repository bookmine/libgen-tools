import sys
import os
import re
import hashlib
import stat
import optparse

BLOCK_SIZE = 64*1024


class HashIndexParser(object):
    "Class to parse various formats of hash index records, with auto-detection."

    FORMATS = [
        ("size-hash-mtime", r" *(?P<size>\d+)  (?P<hash>[0-9A-Fa-f]{32})  (?P<mtime>[12]\d{3}[01]\d[0-3]\dT[02]\d{5})  (?P<filename>.+)"),
        ("size-hash", r" *(?P<size>\d+)  (?P<hash>[0-9A-Fa-f]{32})  (?P<filename>.+)"),
        ("hash", r"(?P<hash>[0-9A-Fa-f]{32})  (?P<filename>.+)"),
    ]

    def __init__(self):
        self.format_name = None
        self.format_regexp = None

    def detect_format(self, l):
        for name, regexp in self.FORMATS:
            if re.match(regexp, l):
                self.format_name = name
                self.format_regexp = regexp
                return
        self.parse_error(l)

    def parse(self, l):
        if not self.format_regexp:
            self.detect_format(l)
        m = re.match(self.format_regexp, l)
        if not m:
            self.parse_error(l)
        entry = m.groupdict()
        # Some fields are implicitly integers
        if "size" in entry:
            entry["size"] = int(entry["size"])
        return entry

    def parse_error(self, line):
        raise NotImplementedError('Format of hash index entry not recognized: "' + line + '"')


class HashIndexReader(object):
    "Reads hash entries from file object using iterator protocol."

    def __init__(self, fp, hash_index_parser=None):
        self.fp = fp
        # Prefer injection over inheritance
        if hash_index_parser is None:
            self.parser = HashIndexParser()
        else:
            self.parser = hash_index_parser

    def __iter__(self):
        return self

    def next(self):
        l = self.fp.next()
        if l[-1] == '\n':
            l = l[:-1]
        return self.parser.parse(l)


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
        fp = HashIndexReader(open(self.index_fname))
        for e in fp:
            e["mark"] = False
            if index & self.INDEX_SIZE:
                self.i_by_size[e["size"]] = e
            if index & self.INDEX_HASH:
                self.i_by_hash[e["hash"]] = e
            if index & self.INDEX_SIZE_HASH:
                self.i_by_size_hash[(e["size"], e["hash"])] = e
            if index & self.INDEX_FILENAME:
                self.i_by_filename[e["filename"]] = e

    def by_filename(self, filename):
        return self.i_by_filename.get(filename)

    def mark(self, filename):
        self.i_by_filename[filename]["mark"] = True

    def unmarked(self):
        for entry in self.i_by_filename.itervalues():
            if not entry["mark"]:
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

def format_index_entry(e):
    return "%10d  %s  %s\n" % (e["size"], e["hash"], e["filename"])

def output_existing_entry(entry, params):
    params["fp"].write(params.get("prefix", "") + format_index_entry(entry))

def output_new_entry(fullname, params):
    st = os.stat(fullname)
    e = {"size": st[stat.ST_SIZE], "hash": hash_file(fullname), "filename": fullname}
    params["fp"].write(params.get("prefix", "") + format_index_entry(e))

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


def main():
    oparser = optparse.OptionParser(usage="%prog <command> <index file>")
    oparser.add_option('-c', '--create', action="store_true", help="Create index")
    oparser.add_option('', '--diff', action="store_true", help="Show changes between index and directory")
    oparser.add_option('-u', "--update", action="store_true", help="Update index")

    (options, args) = oparser.parse_args()
    if len(args) < 2:
        oparser.error("Not enough arguments")


    if options.create or options.update and not os.path.exists(args[0]):
        out_fp = open(args[0], "w")
        index_directory(args[1], on_miss=output_new_entry, params={"fp": out_fp})
        out_fp.close()
    elif options.diff:
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
            if e["filename"].startswith(dir):
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

if __name__ == "__main__":
    main()
