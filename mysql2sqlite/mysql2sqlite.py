import sys
import re
from cStringIO import StringIO


f = open(sys.argv[1])

f_creates = open("schema.sql", "w")

table_map = {}
def open_for_table(table):
    "Overwrite file on 1st open, and append on all next."
    if table not in table_map:
        table_map[table] = True
        return open(table + ".sql", "w")
    else:
        return open(table + ".sql", "a")

def break_insert(l):
    "Break multi-row insert into single-row ones."
    i = l.index('(')
    statement = l[:i]
    m = re.match(r"INSERT INTO `?(.+?)`? VALUES", statement)
    table = m.group(1)
    print table
    f = open_for_table(table)
    f.write("BEGIN;\n")

    l = l[i:]
    i = 0
    while l[i] == '(':
        out = StringIO()
        out.write(l[i])
        i += 1
        while l[i] != ')':
            if l[i] != "'":
                out.write(l[i])
                i += 1
            else:
                out.write(l[i])
                i += 1
                while l[i] != "'":
                    if l[i] == "\\":
                        i += 1
                        if l[i] == "'":
                            out.write("''")
                        else:
                            out.write(l[i])
                        i += 1
                    else:
                        out.write(l[i])
                        i += 1
                out.write(l[i])
                i += 1 # Skip trailing "'"
        assert l[i] == ")"
        out.write(l[i])
        i += 1 # skip trailing ')'
        f.write(statement)
        f.write(out.getvalue())
        f.write(';\n')
        if l[i] == ',':
            i += 1
    assert l[i] == ';', l[i:i+30]
    f.write("END;\n")
    f.write('--\n')
    f.close()


def process_col_decs(decl):
    if "FULLTEXT KEY" in decl:
        return ""
    if re.match(" *KEY `", decl):
        return ""
    decl = re.sub(r"UNIQUE KEY `.+?`", "UNIQUE", decl)
    decl = re.sub(r"AUTO_INCREMENT", "", decl)
    decl = re.sub(r"unsigned", "", decl)
    decl = re.sub(r"ON UPDATE (.+),?", "", decl)
    return decl

for l in f:
    if l.startswith("INSERT"):
        break_insert(l)
    else:
        if re.match(r"^CREATE DATABASE|^USE|^LOCK|^UNLOCK", l):
            continue
        if l.startswith("CREATE TABLE"):
            create = []
            while not l.rstrip().endswith(';'):
                create.append(l.rstrip())
                l = f.next()
            create.append(l.strip())
            print "Before:"
            print "\n".join(create)
            cols = create[1:-1]
            cols = [decl[:-1] if decl.endswith(',') else decl for decl in cols]
            indexes = [decl.strip().split() for decl in cols if "KEY" in decl]
            cols = [process_col_decs(decl) for decl in cols]
            # Remove empty decls
            cols = [decl for decl in cols if decl]
            print "After:"
            out = create[0] + "\n" + ",\n".join(cols) + "\n);\n"
            print out
            print "Indexes:"
            print indexes
            f_creates.write(out)

            m = re.match(r"CREATE TABLE `?(.+?)`? \(", create[0])
            table = m.group(1)
            for ind in indexes:
                if ind[0] == "KEY":
                    #['KEY', '`lastdate`', '(`lastdate`)']
                    f_creates.write("CREATE INDEX %s ON %s%s;\n" % (ind[1], table, ind[2]))
        else:
            f_creates.write(l)
