DB=libgen.sqlite3
TIME=time

.%.sql: %.sql
	$(TIME) sqlite3 $(DB) <$^
	touch $@

all: $(DB) .service.sql .description.sql .updated.sql .constraints

schema.sql: backup_ba.sql
	$(TIME) python mysql2sqlite.py --delay $^

$(DB): schema.sql
	rm -f $(DB) .*.sql
	sqlite3 $@ <$^

.constraints: schema-post.sql
	$(TIME) sqlite3 $(DB) <$^

libgen.csv: $(DB)
	echo "SELECT Filename, Filesize, MD5 FROM updated WHERE Filename != '';" | sqlite3 -csv $(DB) >$@

clean:
	rm -f service.sql description.sql updated.sql schema.sql schema-post.sql
