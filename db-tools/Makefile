DB=libgen.sqlite3

.%.sql: %.sql
	sqlite3 $(DB) <$^
	touch $@

all: $(DB) .service.sql .description.sql .updated.sql

$(DB): schema.sql
	rm $(DB) .*.sql
	sqlite3 $@ <$^

libgen.csv: $(DB)
	echo "SELECT Filename, Filesize, MD5 FROM updated WHERE Filename != '';" | sqlite3 -csv $(DB) >$@
