import sys
import os
import optparse

from hashindex import HashIndexReader


def main():
    oparser = optparse.OptionParser(usage="%prog <command> <dup file>")
    oparser.add_option("", "--format", action="store_true", help="Create a human-friendly file to spot and mark dups")
    oparser.add_option("", "--show", action="store_true", help="Show which files will be deleted with --delete")
    oparser.add_option("", "--delete", action="store_true", help="Execute deletes as marked in input file")

    (options, args) = oparser.parse_args()
    if len(args) != 1:
        oparser.error("Expected single input file")

    if options.format:
        last_size = None
        count = 0
        for e in HashIndexReader(open(args[0])):
            if last_size != e["size"]:
                count += 1
                print "#"
            print e["size"], e["filename"]
            last_size = e["size"]
        print "# Total dup groups: %s" % count
    elif options.show or options.delete:
        for l in open(args[0]):
            if l and l[0] == '*':
                l = l[:-1]
                size, fname = l.split(None, 1)
                if options.delete:
                    os.remove(fname)
                else:
                    print fname
    else:
        oparser.error("No command")

if __name__ == "__main__":
    main()
