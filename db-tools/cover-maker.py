# coding: utf8
import sys
import os
import MySQLdb
import MySQLdb.cursors
import urllib2
import logging
import shutil
import optparse

LIB_ROOT = '/media/freeagent/ebook/lib-libgen'


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

def get_ext(fname, default_ext=None):
    if '.' in fname:
        return fname.rsplit('.', 1)[1]
    return default_ext

def download_cover(cover_url, main_file_name):
    cover_ext = get_ext(cover_url)
    if not cover_ext:
        log.warning("%s: cover url has no file extension, using 'img' placeholder", row)
        cover_ext = 'img'

    try:
        net_fp = urllib2.urlopen(cover_url)
    except urllib2.HTTPError, e:
        log.error("Could not fetch %s, server response: %s", cover_url, e)
        return None

    cover_fp = open("cover.tmp", "wb")
    shutil.copyfileobj(net_fp, cover_fp)
    cover_fp.close()
    net_fp.close()
    dest_cover_name = main_file_name + "." + cover_ext
    dest_cover_path = os.path.join(LIB_ROOT, dest_cover_name)
    shutil.move("cover.tmp", dest_cover_path)
    log.info("Downloaded cover to %s", dest_cover_path)
    return dest_cover_name

# Global vars
log = None
options = None

def main():
    global options, log
    oparser = optparse.OptionParser(usage="%prog <options>")
    oparser.add_option("-n", "--dry-run", action="store_true", help="Don't write anything to DB")
    oparser.add_option("-d", "--debug", action="store_true", default=False, help="Show debug logging (e.g. SQL)")
    oparser.add_option("-l", "--limit", type="int", default=-1, help="Process at most LIMIT records")
    oparser.add_option("", "--hash", help="Process only record with hash")
    oparser.add_option("", "--id", metavar="ID[-IDLAST]", help="Process record(s) with given id(s)")

    (options, args) = oparser.parse_args()
    if len(args) != 0:
        oparser.error("Only options are expected")

    logging.basicConfig(level=[logging.INFO, logging.DEBUG][options.debug])
    log = logging.getLogger()

    conn = MySQLdb.connect(host="localhost", user="pfalcon", passwd="", db="bookwarrior", use_unicode=True)
    cursor = conn.cursor(LoggingReadCursor)
    cursor.execute("SELECT ID, MD5, Filename, Coverurl FROM updated WHERE Coverurl LIKE 'http:%' LIMIT 100")
    cursor_write = conn.cursor(LoggingWriteCursor)
    processed = 0
    while True:
        if options.limit >= 0 and processed >= options.limit:
            break
        row = cursor.fetchone()
        if not row:
            break
        print row
        dest_cover_name = download_cover(row[3], row[2])
        if dest_cover_name:
            cursor_write.execute("UPDATE updated SET Coverurl=%s WHERE ID=%s", (dest_cover_name, row[0]))
            processed += 1

    conn.rollback()
    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
