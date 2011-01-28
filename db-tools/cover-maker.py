# coding: utf8
import sys
import os
import urllib2
import logging
import shutil
import optparse
import re
import time

import MySQLdb
import MySQLdb.cursors


#pdftoppm -f 1 -l 1 -scale-to 150 -jpeg Математика\ 2006-11.pdf .

#ddjvu -format=ppm -page=1 -size=150x150 Силин_А.В.\,_Шмакова_Н.А.-Открываем_неевклидову_геометрию\(1988\).djvu a.ppm

class LoggingReadCursor(MySQLdb.cursors.Cursor):

    def execute(self, sql, values=None):
        log.debug("Executing SQL: %s; args: %s", sql, values)
        MySQLdb.cursors.Cursor.execute(self, sql, values)

class LoggingWriteCursor(MySQLdb.cursors.Cursor):

    def execute(self, sql, values=None):
        global options
        if options.dry_run:
            log.debug("Would execute SQL: %s; args: %s", sql, values)
        else:
            log.debug("Executing SQL: %s; args: %s", sql, values)
            MySQLdb.cursors.Cursor.execute(self, sql, values)

def download_cover(cover_url, main_file_name):
    global dest_root, options
    cover_ext = os.path.splitext(cover_url)[1]
    if not cover_ext:
        log.warning("%s: cover url has no file extension, using 'img' placeholder", row)
        cover_ext = '.img'

    # -d suffix means "downloaded"
    dest_cover_name = main_file_name + "-d" + cover_ext
    dest_cover_path = os.path.join(dest_root, dest_cover_name)
    if not options.force and os.path.exists(dest_cover_path):
        log.info("Cover %s already exists, using as is", dest_cover_path)
        return dest_cover_name

    attempt = 0
    while True:
        try:
            try:
                net_fp = urllib2.urlopen(cover_url)
            except urllib2.HTTPError, e:
                log.error("Could not fetch %s, server response: %s", cover_url, e)
                return None

            cover_fp = open("cover.tmp", "wb")
            shutil.copyfileobj(net_fp, cover_fp)
            cover_fp.close()
            net_fp.close()
            break
        except IOError, e:
            if attempt >= options.retry:
                log.error("Could not download cover %s, skipping: %s", cover_url, e)
                return None
            attempt += 1
            log.warning("Could not download cover, will retry: %s", e)
            time.sleep(2)

    if not os.path.isdir(os.path.dirname(dest_cover_path)):
        os.makedirs(os.path.dirname(dest_cover_path))
    shutil.move("cover.tmp", dest_cover_path)
    log.info("Downloaded cover to %s", dest_cover_path)
    return dest_cover_name

# Global vars
log = None
options = None
lib_root = None
dest_root = None

def main():
    global options, log, lib_root, dest_root
    oparser = optparse.OptionParser(usage="%prog <options> <lib path> <dest path>", description="""\
Make coverpage thumbnails for LibGen library, either by downloading them or
generating from first page of PDF/DJVU (todo). Path to library is given by first
argument, covers are put under separate root specified by second argument
(may be equal to library path).""")

    oparser.add_option("", "--retry", type="int", default=3, help="Number of retries on network errors")
    oparser.add_option("", "--force", action="store_true", help="Ignore local files, force redownloading/reconversion")
    oparser.add_option("-n", "--dry-run", action="store_true", help="Don't write anything to DB")
    oparser.add_option("-d", "--debug", action="store_true", default=False, help="Show debug logging (e.g. SQL)")

    optgroup = optparse.OptionGroup(oparser, "Record selection options")
    optgroup.add_option("", "--all", action="store_true", help="Process all records")
    optgroup.add_option("", "--id", metavar="ID[-IDLAST]", help="Process record(s) with given id(s)")
    optgroup.add_option("", "--hash", help="Process only record with given hash")
    optgroup.add_option("-l", "--limit", type="int", default=-1, help="Make at most LIMIT covers")
    oparser.add_option_group(optgroup)

    optgroup = optparse.OptionGroup(oparser, "DB connection options")
    optgroup.add_option("", "--db-host", default="localhost", help="DB host (%default)")
    optgroup.add_option("", "--db-name", default="bookwarrior", help="DB name (%default)")
    optgroup.add_option("", "--db-user", help="DB user")
    optgroup.add_option("", "--db-passwd", metavar="PASSWD", default="", help="DB password (empty)")
    oparser.add_option_group(optgroup)

    (options, args) = oparser.parse_args()
    if len(args) != 2:
        oparser.error("Wrong number of arguments")
    if len(filter(None, [options.all, options.id, options.hash])) != 1:
        oparser.error("One (and only one) of --all, --id= or --hash= must be specified")
    if not options.db_user:
        oparser.error("--db-user is required")

    logging.basicConfig(level=[logging.INFO, logging.DEBUG][options.debug])
    log = logging.getLogger()

    lib_root = args[0]
    dest_root = args[1]
    if options.all:
        range_where = ""
    elif options.id:
        m = re.match(r"(\d+)-(\d+)", options.id)
        if m:
            range_where = " AND ID BETWEEN %s AND %s" % (m.group(1), m.group(2))
        else:
            range_where = " AND ID=%d" % int(options.id)
    elif options.hash:
        range_where = " AND MD5='%s'" % options.hash

    conn = MySQLdb.connect(host=options.db_host, user=options.db_user, passwd=options.db_passwd, db=options.db_name, use_unicode=True)
    cursor = conn.cursor(LoggingReadCursor)
    cursor.execute("SELECT ID, MD5, Filename, Coverurl FROM updated WHERE Coverurl LIKE 'http:%'" + range_where)
    cursor_write = conn.cursor(LoggingWriteCursor)
    total = 0
    processed = 0
    while True:
        if options.limit >= 0 and processed >= options.limit:
            break
        row = cursor.fetchone()
        if not row:
            break
        total += 1
        dest_cover_name = download_cover(row[3], row[2])
        if dest_cover_name:
            cursor_write.execute("UPDATE updated SET Coverurl=%s WHERE ID=%s", (dest_cover_name, row[0]))
            processed += 1

    print "Total records processed: %d, new covers made: %d" % (total, processed)
    conn.commit()
    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
