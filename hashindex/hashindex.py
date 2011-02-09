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
        self.count = 0

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
            self.count += 1

    def by_filename(self, filename):
        return self.i_by_filename.get(filename)

    def by_hash(self, hash):
        return self.i_by_hash.get(hash)

    def mark(self, filename):
        self.i_by_filename[filename]["mark"] = True

    def all(self):
        for entry in self.i_by_filename.itervalues():
            yield entry

    def unmarked(self):
        for entry in self.i_by_filename.itervalues():
            if not entry["mark"]:
                yield entry

    def __len__(self):
        return self.count

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

def output_new_entry(fullname, output_name, params):
    st = os.stat(fullname)
    e = {"size": st[stat.ST_SIZE], "hash": hash_file(fullname), "filename": output_name}
    params["fp"].write(params.get("prefix", "") + format_index_entry(e))

def index_directory(options, path, index=None, params={}, on_match=None, on_miss=None):
    """Recursively scan directory. For each file found, if index given, look
    it up there. If found, mark file in index, call on_match function if any.
    Otherwise, call on_miss function.
    """
    if not options.relative_path:
        path = os.path.abspath(path)
    l = len(path)

    for dirpath, dirnames, filenames in os.walk(path):
        for fname in filenames:
            if fname.startswith(".index.hash.txt"): continue
            fullname = output_name = os.path.join(dirpath, fname)
            if options.bare_path:
                output_name = fullname[l + 1:]
            if index:
                e = index.by_filename(fullname)
                if e:
                    index.mark(fullname)
                    on_match and on_match(e, params)
                    continue
            on_miss and on_miss(fullname, output_name, params)

class NowrapHelpFormatter(optparse.IndentedHelpFormatter):
    def format_description(self, description):
        if description:
            return description + "\n"
        else:
            return ""

class MyOptionParser(optparse.OptionParser):

    def parse_args(self):
        self.my_options, self.my_args = optparse.OptionParser.parse_args(self)
        return (self.my_options, self.my_args)

    def need_args(self, num):
        if len(self.my_args) != num:
            self.error("Wrong number of arguments")

def splitext(fname):
    parts = os.path.splitext(fname)
    if len(parts[1]) < 6:
        if parts[1] in (".gz", ".bz2"):
            parts2 = os.path.splitext(parts[0])
            if len(parts2[1]) < 6:
                return (parts2[0], parts2[1] + parts[1])
        return parts
    return (fname, '')


class IndexSpec(object):
    "Store location of index and related collection"

    def __init__(self, spec=None, index=None, coll=None):
        if spec:
            self.parse(spec)
        else:
            self.index = index
            self.coll = coll

    def parse(self, spec):
        if spec[0] == '@':
            self.coll = spec[1:]
            self.index = self.coll + "/.index.hash.txt"
        elif spec[0] == '^':
            self.coll = spec[1:]
            dir, base = os.path.split(self.coll)
            self.index = os.path.join(dir, base + ".hash.txt")
        elif '@' in spec:
            self.index, self.coll = spec.split('@', 1)
        else:
            self.index = spec
            self.coll = None

    def index_exists(self):
        return os.path.exists(self.index)

    def coll_exists(self):
        return os.path.isdir(self.coll)

def main():
    oparser = MyOptionParser(usage="%prog <command> <index spec> [<index spec>]", formatter=NowrapHelpFormatter(),
                             description="""\
Perform operations on a hash index(es) of digital collection.

<index spec> gives location of the collection and index:
@<path>: collection at <path>, index at <path>/.index.hash.txt
^<path>: collection at <path>, index at <dirname path>/<basename path>.hash.txt
<index path>@<collection path>: as specified""")
    oparser.add_option("-l", "--relative-path", action="store_true", help="Don't convert file paths to absolute")
    oparser.add_option("-b", "--bare-path", action="store_true", help="Store path relative to the collection root")
    oparser.add_option("--limit", type="int", default=None, help="Limit action to N iterations")
    oparser.add_option('-c', '--create', action="store_true", help="Create index")
    oparser.add_option('', '--changes', action="store_true", help="Show changes between index and directory")
    oparser.add_option('-u', "--update", action="store_true", help="Update index")
    oparser.add_option("", "--stats", action="store_true", help="Show stats on index")

    (options, args) = oparser.parse_args()

    if len(args) > 0:
        index1_spec = IndexSpec(args[0])
    else:
        index1_spec = IndexSpec()

    if options.create or (options.update and not index1_spec.index_exists()):
        print index1_spec.index
        oparser.need_args(1)
        out_fp = open(index1_spec.index, "w")
        index_directory(options, index1_spec.coll, on_miss=output_new_entry, params={"fp": out_fp})
        out_fp.close()
    elif options.changes:
        oparser.need_args(1)
        index = HashIndex(index1_spec.index)
        index.load(HashIndex.INDEX_FILENAME)
        # Output only files not existing in index
        params = {"fp": sys.stdout, "prefix": "+"}
        index_directory(options, index1_spec.coll, index, on_miss=output_new_entry, params=params)
        # Now unmarked files in index - deleted from dir
        dir = index1_spec.coll
        # Make sure we compare complete path components and don't match "/foo" with "/foobar"
        if dir[-1] != '/':
            dir += '/'
        for e in index.unmarked():
            if e["filename"].startswith(dir):
                params["prefix"] = "-"
                output_existing_entry(e, params=params)
    elif options.update:
        oparser.need_args(1)
        index = HashIndex(index1_spec.index)
        index.load(HashIndex.INDEX_FILENAME)
        out_fp = open(index1_spec.index + ".tmp", "w")
        # Just calc hash and dump for new files, and re-dump existing entries
        # Old entries are automagically gone
        index_directory(options, index1_spec.coll, index, on_miss=output_new_entry, on_match=output_existing_entry, params={"fp": out_fp})
        out_fp.close()
        os.rename(index1_spec.index + ".tmp", index1_spec.index)
    elif options.stats:
        oparser.need_args(1)
        index = HashIndex(index1_spec.index)
        index.load(HashIndex.INDEX_FILENAME)
        print "%-10s %d" % ("Total:", len(index))
        by_ext = {}
        for e in index.all():
            ext = splitext(e["filename"])[1].lower()
            by_ext[ext] = by_ext.get(ext, 0) + 1
        for ext, count in sorted(by_ext.items(), key=lambda p: p[1], reverse=True)[:options.limit]:
            print "%-10s %d" % (ext, count)
    else:
        oparser.error("No command")

if __name__ == "__main__":
    main()
