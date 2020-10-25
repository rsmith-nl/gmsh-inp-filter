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

check::
	pylama ${PROG}
