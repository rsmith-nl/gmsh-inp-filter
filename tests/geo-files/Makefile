# file: Makefile
# vim:fileencoding=utf-8:ft=make

all: beam.msh plate.msh

beam.msh:  beam-mesh.inp ../../gmsh-inp-filter.py
	python ../../gmsh-inp-filter.py -r beam-mesh.inp beam.msh

plate.msh:  plate-mesh.inp ../../gmsh-inp-filter.py
	python ../../gmsh-inp-filter.py -r plate-mesh.inp plate.msh


beam-mesh.inp: beam.geo
	gmsh beam.geo -

plate-mesh.inp: plate.geo
	gmsh plate.geo -


.PHONY: clean
clean::
	rm -f beam.msh plate.msh beam-mesh.inp plate-mesh.inp
