# file: Makefile
# vim:fileencoding=utf-8:fdm=marker:ft=make
#
# Copyright © 2020 R.F. Smith <rsmith@xs4all.nl>
# Created: 2020-09-26T13:04:37+0200
# Last modified: 2020-09-26T13:13:25+0200
.SUFFIXES: .inp .msh

all: test1.msh



.inp.msh:
	../gmsh-inp-filter.py $< $* 2>/dev/null
	diff -q $* $*.msh.ref
	rm -f $*
