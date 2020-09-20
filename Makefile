.SUFFIXES: .py
.PHONY: help uninstall

# Name of the program
PROG:=gmsh-inp-filter.py

# Installation locations
PREFIX=/usr/local
BINDIR=$(PREFIX)/bin

help::
	@echo "As a normal user, you can:"
	@echo "'make check' to check the program with pylama."
	@echo "As root, use:"
	@echo "'make install' to install the program."
	@echo "'make uninstall' to remove the program."

check::
	pylama ${PROG}


install: ${PROG}
	@install -d ${BINDIR}
	install ${PROG} ${BINDIR}/${PROG:R}

uninstall::
	rm -f ${BINDIR}/${PROG:R}
