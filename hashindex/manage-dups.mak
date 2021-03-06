SCRIPTS=$(dir $(MAKEFILE_LIST))
LIBSPEC=@$(LIB)
INDEX=$(LIB)/.index.hash.txt

all: md5deep.txt.dup.size-fname

$(INDEX):
	python "$(SCRIPTS)hashindex.py" --update $(LIBSPEC)
#	md5deep -e -l -r -z ../lib >$@

md5deep.txt.sorted: $(INDEX)
	sort -n $^ >md5deep.txt.sorted

md5deep.txt.big: md5deep.txt.sorted
	awk '$$1 > 100000' $^ >$@

md5deep.txt.dup-hashes: md5deep.txt.big
	uniq -c -w44 $^ | awk '$$1 > 1 { print $$3 }' >$@

md5deep.txt.dup: md5deep.txt.dup-hashes md5deep.txt.big
	if [ -s md5deep.txt.dup-hashes ]; then grep -F -f $^ >$@; else >$@; fi

md5deep.txt.dup.size-fname: md5deep.txt.dup
	python $(SCRIPTS)process-dups.py --format $^ >$@


# Diff index and lib dir
changes diff: $(INDEX)
	python "$(SCRIPTS)/hashindex.py" --changes $(LIBSPEC)

# Delete what's marked in md5deep.txt.dup.size-fname
delete: md5deep.txt.dup.size-fname
	python $(SCRIPTS)process-dups.py --delete $^

# Show what would be deleted with delete target
show-delete: md5deep.txt.dup.size-fname
	python $(SCRIPTS)process-dups.py --show $^
