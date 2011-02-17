import sys
import re
from cStringIO import StringIO
import optparse
import re


oparser = optparse.OptionParser(usage="%prog <options> <mysql db dump>", description="""\
Convert MySQL DB dump into SQLite DB dump
""")
oparser.add_option("", "--no-data", action="store_true", help="Ignore INSERT data")
oparser.add_option("", "--delay-constraints", action="store_true", help="Delay adding constraints until after data INSERTed")

(options, args) = oparser.parse_args()
if len(args) != 1:
    oparser.error("Wrong number of arguments")

f = open(args[0])

f_creates = open("schema.sql", "w")

table_map = {}
def open_for_table(table):
    "Overwrite file on 1st open, and append on all next."
    if table not in table_map:
        table_map[table] = True
        fp = open(table + ".sql", "w")
#        fp.write("PRAGMA synchronous =  OFF;\n")
        return fp
    else:
        return open(table + ".sql", "a")

re_term = re.compile(r"'.*?'|[^,)]+")
re_slash = re.compile(r"\\.")

def repl_f(m):
    s = m.group()
    if s[1] == "'":
        return "\x01"
    return s[1]

def break_insert(l):
    "Break multi-row insert into single-row ones."
    i = l.index('(')
    statement = l[:i]
    m = re.match(r"INSERT INTO `?(.+?)`? VALUES", statement)
    table = m.group(1)
#    print table
    f = open_for_table(table)
    f.write("BEGIN;\n")

    l = l[i:]
    l = re.sub(re_slash, repl_f, l)
    i = 0
    while l[i] == '(':
        out = StringIO()
        out.write(l[i])
        i += 1
        while l[i] != ')':
            m = re_term.match(l, i)
            assert m, l[i:i+30]
#            print "=%s=" % m.group()
            t = m.group()
            t = t.replace("\x01", "''")
            if "),(" in t:
                print "!!!", t[0:3000]
            out.write(t)
            i = m.end(0)
            assert l[i] in (',', ')')
            if l[i] == ',':
                out.write(l[i])
                i += 1
#        assert l[i] == ")"
        out.write(l[i])
        i += 1 # skip trailing ')'
        f.write(statement)
        f.write(out.getvalue())
        f.write(';\n')
#        assert l[i] in (',', ';')
        if l[i] == ',':
            i += 1
    assert l[i] == ';', l[i:i+30]
    f.write("COMMIT;\n")
    f.write('--\n')
    f.close()


def process_col_decs(decl):
    if "FULLTEXT KEY" in decl:
        return ""
    if re.match(r" *(UNIQUE )?KEY `", decl):
        return ""
    decl = re.sub(r"int\(\d+\)", "INTEGER", decl)
    decl = re.sub(r"UNIQUE KEY `.+?`", "UNIQUE", decl)
    decl = re.sub(r"AUTO_INCREMENT", "", decl)
    decl = re.sub(r"unsigned", "", decl)
    decl = re.sub(r"ON UPDATE (.+),?", "", decl)
    return decl

def clean_name(n):
    if n[0] == "`":
        return n[1:-1]
    return n


delayed_constarints = []

for l in f:
    if l.startswith("INSERT"):
        if not options.no_data:
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
#            print "Before:"
#            print "\n".join(create)
            cols = create[1:-1]
            cols = [decl[:-1] if decl.endswith(',') else decl for decl in cols]
            indexes = [decl.strip().split() for decl in cols if "KEY" in decl]
            cols = [process_col_decs(decl) for decl in cols]
            # Remove empty decls
            cols = [decl for decl in cols if decl]
#            print "After:"
            out = create[0] + "\n" + ",\n".join(cols) + "\n);\n"
#            print out
#            print "Indexes:"
#            print indexes
            f_creates.write(out)

            m = re.match(r"CREATE TABLE `?(.+?)`? \(", create[0])
            table = m.group(1)
            for ind in indexes:
                if ind[0] == "KEY":
                    #['KEY', '`lastdate`', '(`lastdate`)']
                    ind_name = clean_name(ind[1])
                    f_creates.write("CREATE INDEX %s_%s ON %s%s;\n" % (table, ind_name, table, ind[2]))
                elif ind[0] == "UNIQUE":
                    ind_name = clean_name(ind[2])
                    sql = "CREATE UNIQUE INDEX IF NOT EXISTS %s_%s ON %s%s;\n" % (table, ind_name, table, ind[3])
                    if options.delay_constraints:
                        delayed_constarints.append(sql)
                    else:
                        f_creates.write(sql)
        else:
            if l.startswith("/*"):
                continue
            f_creates.write(l)

if delayed_constarints:
    fp = open("schema-post.sql", "w")
    fp.write("".join(delayed_constarints))
