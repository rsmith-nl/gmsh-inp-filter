#!/usr/bin/env python3
# file: inp-filter.py
# vim:fileencoding=utf-8:fdm=marker:ft=python
#
# Copyright © 2020 R.F. Smith <rsmith@xs4all.nl>
# Created: 2020-09-06T10:15:43+0200
# Last modified: 2020-09-18T14:22:57+0200
"""Filter an Abaqus input file (generated by gmsh) to only contain node sets,
solid elements and solid element surface sets.

Usage: inp-filter.py input.inp output.msh
"""

import functools as ft
import itertools as it
import logging
import sys


def main(args):
    # Configuration.
    # logging.basicConfig(level='DEBUG', format='%(levelname)s: %(message)s')
    logging.basicConfig(level='INFO', format='%(levelname)s: %(message)s')
    infn, outfn = checkargs(args)
    logging.info(f"input file name: “{infn}”.")
    logging.info(f"output file name: “{outfn}”.")
    # Read and process the input file.
    headings, lines = read_input(infn)
    nodes = retrieve_nodes(headings, lines)
    logging.info(f"nodes: {len(nodes)}.")
    volsets = retrieve_elements(headings, lines, "C3D20")
    logging.info(f"original solid element sets: {len(volsets)};")
    volsets = fix_set_names(lines, headings, volsets)
    surfsets = retrieve_elements(headings, lines, "CPS8")
    logging.info(f"original surface element sets: {len(surfsets)};")
    surfsets = fix_set_names(lines, headings, surfsets)
    nsets = retrieve_nodesets(headings, lines)
    logging.info(f"node sets: {len(nsets)};")
    for k in nsets.keys():
        logging.info(f"  “{k}”: {len(nsets[k])} nodes")
    # Gather all solid elements into Eall.
    Eall = {}
    for d in volsets.values():
        Eall.update(d)
    surfaces = {}
    for sname, sv in surfsets.items():
        logging.info(f"remapping surface set “{sname}”")
        surfaces[sname] = remap_surface(sv, Eall)
    # Get the node numbers used in Eall.
    Nall = set()
    for v in Eall.values():
        Nall.update(v)
    Nall = tuple(sorted(Nall))
    if min(Nall) == 1 and max(Nall) == len(Nall):
        logging.info("used nodes are continuous, not re-numbered.")
    else:
        # TODO: re-number nodes.
        logging.warning("nodes need re-numbering, not implemented yet.")
        pass
    # Write output file
    write_output(outfn, nodes, Eall, nsets, volsets, surfaces)


def checkargs(args):
    """Check that we have received a input filename and an output filename.
    If not, exit the program."""
    if len(args) != 2:
        logging.error("proper usage: inp-filter.py input.inp output.inp.")
        sys.exit(1)
    return args[0], args[1]


def read_input(ifn):
    """Read an Abaqus INP file, read its sections.
    Return the section headings and the lines.
    """
    with open(ifn) as inf:
        lines = [ln.strip() for ln in inf.readlines()]
    # Remove comments
    lines = [ln for ln in lines if not ln.startswith("**")]
    # Find section headers
    headings = [(ln[1:], n) for n, ln in enumerate(lines) if ln.startswith("*")]
    # Filter the headings so that every heading has a start-of-data and
    # end-of-data index.
    headings.append(("end", -1))
    ln = [h[1] for h in headings]
    headings = [
        (name, start + 1, end) for (name, start), end in zip(headings[:-1], ln[1:])
    ]
    return headings, lines


def retrieve_nodes(headings, lines):
    """Extract the nodes out of lines.
    Return a dict of nodes, indexed by the node number.
    A node is a 3-tuple of coordinate strings.
    The node coordinates are *not* converted to floats, so as to not lose precision.

    Arguments:
        headings (list): list of (name, start, end) tuples.
        lines (list): list of lines.

    Returns:
        A dict of nodes (x,y,z)-tuples indexed by the node number.
    """
    nodes = {}
    for h in headings:
        if h[0].lower().startswith("node"):
            for ln in lines[h[1]:h[2]]:
                idx, x, y, z = ln.split(",")
                nodes[int(idx)] = (x.strip(), y.strip(), z.strip())
            # Assuming there is only one NODE section.
            break
    return nodes


def retrieve_elements(headings, lines, eltype):
    """
    Extract element sets from the file contents.

    Arguments:
        headings (list): list of (name, start, end) tuples.
        lines (list): list of lines.
        eltype: (str): element type, like C3D20 or CPS8

    Returns:
        A dict of elements indexed by the volume name.
        Note that this is not a separately defined ELSET,
        but the built-in one.
    """
    element_sets = {}
    n = 1
    for h in headings:
        name = h[0]
        lname = name.lower()
        if not lname.startswith("element"):
            continue
        if f"type={eltype}".lower() not in lname:
            continue
        setname = [s.strip()[6:] for s in name.split(",") if "elset=" in s.lower()]
        if not setname:
            setname = f"unknown{n}"
            n += 1
        else:
            setname = setname[0]
        elements = read_elements(lines, h[1], h[2], setname)
        element_sets[setname] = elements
    return element_sets


def read_elements(lines, start, end, setname):
    """
    Extract elements.
    Returns dict of elements, indexed by the element number.
    An element is a n-tuple of node numbers.

    Arguments:
        lines (list): A list of lines.
        start (int): first line to process.
        end (int): one past the last line to process.
        setname (str): name of the element set

    Returns:
        A dict of elements, indexed by the element number.
    """
    # Consolidate multiline elements
    consol = []
    ncon = 0
    part = lines[start:end]
    for ln in part[::-1]:
        if ln.endswith(","):
            consol[0] = ln + consol[0]
            ncon += 1
        else:
            consol.insert(0, ln)
    logging.debug(f"consolidated {ncon} lines in set “{setname}”")
    elements = {}
    for ln in consol:
        elnum, *nodenums = [int(i) for i in ln.split(",")]
        elements[elnum] = nodenums
    return elements


def fix_set_names(lines, headings, element_sets):  # noqa
    """Rename and merge the element sets to the name we chose."""
    newsets = {}
    for h in headings:
        name = h[0]
        lname = name.lower()
        if not lname.startswith("elset"):
            continue
        try:
            setname = [s.strip()[6:] for s in name.split(",") if "elset=" in s.lower()][0]
        except IndexError:
            logging.error(f"set “{name}” without name")
            continue
        if setname == "all":
            continue
        elset = []
        for ln in lines[h[1]:h[2]]:
            elset += [int(j) for j in ln.strip().split(",") if j]
        for oname in element_sets.keys():
            if set(element_sets[oname].keys()).issubset(set(elset)):
                if setname not in newsets:
                    newsets[setname] = element_sets[oname]
                    logging.info(f"renamed “{oname}” to “{setname}”")
                else:
                    newsets[setname].update(element_sets[oname])
                    logging.info(f"added “{oname}” to “{setname}”")
    for st in newsets:
        logging.info(f"set “{st}” has {len(newsets[st])} elements")
    return newsets


def read_element_numbers(lines, first, last):
    rv = []
    for ln in lines[first:last]:
        rv += [int(j) for j in ln.strip().split(",")]
    return rv


def remap_surface(surface_set, Eall):
    """
    Map surface elements to sides of solid elements.

    Arguments:
        surface_set (dict): A dictionary of surface elements indexed by the
        element number and containing a list of node numbers.
        Eall (dict): A dictionary of volume elements indexed by the element number
        and containing lists of node numbers.

    Returns:
        A list of  2-tuples containing a volume element and surface, e.g. (1679, "S2").
    """
    newset = []
    ixs = {
        (0, 1, 2, 3): "S1", (4, 7, 6, 5): "S2", (0, 4, 5, 1): "S3",
        (1, 5, 6, 2): "S4", (1, 6, 7, 3): "S5"
    }
    for snum, snodes in surface_set.items():
        ssnodes = set(snodes)
        for vnum, vnodes in Eall.items():
            svnodes = set(vnodes)
            if ssnodes.issubset(svnodes):
                orig = set(snodes[:4])
                surf = "S6"
                for ix, sname in ixs.items():
                    comp = set(vnodes[j] for j in ix)
                    if orig == comp:
                        surf = sname
                        break
                newset.append((vnum, surf))
                logging.debug(f"surface {snum} maps to  “{vnum}, {surf}”")
                break
        else:
            logging.error(f"no mapping found for surface {snum}!")
    return newset


def retrieve_nodesets(headings, lines):
    nsets = {}
    n = 1
    for h in headings:
        name = h[0]
        lname = name.lower()
        if not lname.startswith("nset"):
            continue
        setname = [s.strip()[5:] for s in name.split(",") if "nset=" in s.lower()]
        if not setname:
            setname = f"unknown{n}"
            n += 1
        else:
            setname = setname[0]
        nodes = []
        for ln in lines[h[1]:h[2]]:
            nodes += [int(i) for i in ln.split(",") if i != ""]
        nsets[setname] = tuple(nodes)
    return nsets


def chunked(iterable, n):
    """
    Split an iterable up in chunks of length n.

    The second argument to the outer ``iter()`` is crucial to the way this works.
    See the documentation for ``iter()`` for details.
    """

    def take(n, iterable):
        return list(it.islice(iterable, n))

    return iter(ft.partial(take, n, iter(iterable)), [])


def write_output(outfn, nodes, elements, nsets, elsets, surfaces):
    with open(outfn, "w") as outf:
        logging.info(f"opened output file “{outfn}”.")
        write_nodes(outf, nodes)
        write_elements(outf, elements)
        write_node_sets(outf, nsets)
        write_element_sets(outf, elsets)
        write_surfaces(outf, surfaces)


def write_nodes(outf, nodes):
    outf.write("*NODE, NSET=Nall\n")
    for num, (x, y, z) in nodes.items():
        outf.write(f"{num:>8d},{x},{y},{z}\n")
    logging.info(f"wrote {len(nodes)} nodes to output file (node set “Nall”).")


def write_elements(outf, elements):
    outf.write("*ELEMENT, TYPE=C3D20, ELSET=Eall\n")
    for elnum, nodenums in elements.items():
        first, second = [elnum] + nodenums[:10], nodenums[10:]
        line = ",".join(f"{i:>6d}" for i in first) + ",\n"
        outf.write(line)
        line = "     " + ",".join(f"{i:>6d}" for i in second) + "\n"
        outf.write(line)
    logging.info(
        f"wrote {len(elements)} elements to output file. (element set “Eall”)"
    )


def write_node_sets(outf, nsets):
    for nsname, nsnodes in nsets.items():
        if nsname == "all":
            continue
        outf.write(f"*NSET, NSET=N{nsname}\n")
        for nums in chunked(nsnodes, 10):
            outf.write(', '.join(str(j) for j in nums) + ',\n')
        logging.info(f"wrote nodeset “N{nsname}”.")


def write_element_sets(outf, elsets):
    for esname, elnums in elsets.items():
        outf.write(f"*ELSET, ELSET=E{esname}\n")
        for nums in chunked(elnums, 10):
            outf.write(', '.join(str(j) for j in nums) + ',\n')
        logging.info(f"wrote element set “E{esname}”.")


def write_surfaces(outf, surfaces):
    for sname, sdata in surfaces.items():
        outf.write(f"*SURFACE, NAME=S{sname}\n")
        for num, face in sdata:
            outf.write(f"{num}, {face}\n")
        logging.info(f"wrote surface set “S{sname}”.")


if __name__ == '__main__':
    main(sys.argv[1:])
