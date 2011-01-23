SCRIPTS=$(dir $(MAKEFILE_LIST))

all: md5deep.txt.dup.size-fname

md5deep.txt:
	python "$(SCRIPTS)/hashindex.py" $@ --update $(LIB)
#	md5deep -e -l -r -z ../lib >$@

md5deep.txt.sorted: md5deep.txt
	sort -n md5deep.txt >md5deep.txt.sorted

md5deep.txt.big: md5deep.txt.sorted
	awk '$$1 > 100000' $^ >$@

md5deep.txt.dup-hashes: md5deep.txt.big
	uniq -c -w44 $^ | awk '$$1 > 1 { print $$3 }' >$@

md5deep.txt.dup: md5deep.txt.dup-hashes md5deep.txt.big
	if [ -s md5deep.txt.dup-hashes ]; then grep -F -f $^ >$@; else >$@; fi

md5deep.txt.dup.size-fname: md5deep.txt.dup
	python $(SCRIPTS)/process-dups.py --format $^ >$@
