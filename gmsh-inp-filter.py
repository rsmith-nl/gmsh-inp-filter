#!/usr/bin/env python3
# file: gmsh-inp-filter.py
# vim:fileencoding=utf-8:fdm=marker:ft=python
#
# Copyright © 2020 R.F. Smith <rsmith@xs4all.nl>.
# SPDX-License-Identifier: MIT
# Created: 2020-09-06T10:15:43+0200
# Last modified: 2020-09-27T12:00:15+0200
"""Filter an Abaqus input file (generated by gmsh) to only contain node sets,
solid elements and solid element surface sets.

Optionally, it can replace nodes shared by volume elements sets by new nodes,
and establish contact using equations.

You should have the following options set in your geo-file to produce output
that can be processed by this script:

    Mesh.ElementOrder = 2; // Create second order elements.
    Mesh.SubdivisionAlgorithm = 2; // All hex elements
    Mesh.SecondOrderIncomplete = 1; // Use 20-node hex elements.
    Mesh.Format = 39; // Save mesh as INP format.
    Mesh.SaveGroupsOfNodes = 1;

It is advised to have the following options set in your geo-file:

    Mesh.Algorithm = 8;  // Frontal Delauney for quads.
    Mesh.Algorithm3D = 1; // Delauney
"""

import argparse
import functools as ft
import itertools as it
import logging
import sys

__version__ = '1.1'


def main(args):
    # Configuration.
    # logging.basicConfig(level='INFO', format='%(levelname)s: %(message)s')
    logging.basicConfig(level='DEBUG', format='%(levelname)s: %(message)s')
    opts = setup(args)
    logging.info(f"input file name: “{opts.infn}”.")
    logging.info(f"output file name: “{opts.outfn}”.")
    # Read and process the input file.
    headings, lines = read_input(opts.infn)
    nodes = retrieve_nodes(headings, lines)
    # “nodes” is a dict of (x,y,z)-tuples indexed by the node number.
    # nodes[number] = (x,y,z)
    logging.info(f"nodes: {len(nodes)}.")
    Eall, volsets, nreverse, setnodes = retrieve_C3D20(headings, lines)
    # “Eall”  is a dictionary of lists of node numbers indexed by the element number.
    # “volsets” is a dict of lists of element numbers indexed by the volume set name.
    # “nreverse” is a dict of lists of element numbers indexed by node number.
    # “setnodes” is a dict of sets of node numbers indexed by volume set name.
    logging.info(f"original solid element sets: {len(volsets)};")
    volsets, setnodes = fix_volume_set_names(lines, headings, volsets, setnodes)
    surfsets = retrieve_CPS8(headings, lines)
    logging.info(f"original surface element sets: {len(surfsets)};")
    surfsets = fix_surface_set_names(lines, headings, surfsets)
    # “surfsets” is a dict of surface sets indexed by name.
    # A surface set is a dict of n-tuples of nodes indexed by element number.
    logging.info(f"node sets: {len(setnodes)};")
    for k in setnodes.keys():
        logging.info(f"  “{k}”: {len(setnodes[k])} nodes")
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
        logging.warning(f"min(Nall) = {min(Nall)}")
        logging.warning(f"max(Nall) = {max(Nall)}")
        logging.warning(f"len(Nall) = {len(Nall)}")
        logging.warning("nodes are not continuous.")
        logging.warning("they could be re-numbered to make the matrix smaller.")
        logging.warning("however, this is not implemented yet.")
        pass
    if opts.equations:
        sk, nk = set(surfsets.keys()), set(setnodes.keys())
        sn = sk & nk
        # Nodes in the sn sets should not be in equations.
        logging.info("finding equations.")
        equations, nodes, Eall = make_eqns(nodes, Eall, setnodes, volsets, sn, nreverse)
    # Write output file
    write_output(
        opts.outfn, nodes, Eall, setnodes, volsets, surfaces, opts.reduced, equations
    )


def setup(args):
    """Check that we have received a input filename and an output filename.
    If not, exit the program."""

    class CustomFormatter(
        argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter
    ):
        pass

    parser = argparse.ArgumentParser(
        prog='gmsh-inp-filter', description=__doc__, formatter_class=CustomFormatter
    )
    parser.add_argument('-v', '--version', action='version', version=__version__)
    parser.add_argument(
        '-r',
        '--reduced',
        action='store_true',
        default=False,
        help='generate C3D20R elements instead of C3D20'
    )
    parser.add_argument(
        '-e',
        '--equations',
        action='store_true',
        default=False,
        help='replace shared nodes by equations'
    )
    parser.add_argument("infn", metavar='input', help="input file to process")
    parser.add_argument("outfn", metavar='output', help="output file to generate")
    opts = parser.parse_args(args)
    return opts


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
        A dict of (x,y,z)-tuples indexed by the node number.
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


def retrieve_C3D20(headings, lines):
    """
    Extract C3D20 element sets from the file contents.

    Arguments:
        headings (list): list of (name, start, end) tuples.
        lines (list): list of lines.

    Returns:
        1) A dict of lists of node numbers indexed by element number.
           Note that this is not a separately defined ELSET, but the built-in one.
        2) A dict of lists of element numbers indexed by volume name.
        3) A dict of lists of element numbers indexed by node number.
        4) A dict of sets of nodes indexed by element set name.
    """
    all_elements = {}
    element_sets = {}
    all_nreverse = {}
    all_setnodes = {}
    n = 1
    for h in headings:
        name = h[0]
        lname = name.lower()
        if not lname.startswith("element"):
            continue
        if "type=C3D20".lower() not in lname:
            continue
        setname = [s.strip()[6:] for s in name.split(",") if "elset=" in s.lower()]
        if not setname:
            setname = f"unknown{n}"
            n += 1
        else:
            setname = setname[0]
        elements, setnodes, nreverse, = read_elements(lines, h[1], h[2], setname)
        element_sets[setname] = elements
        all_elements.update(elements)
        for k, v in nreverse.items():
            if k in all_nreverse:
                all_nreverse[k] += v
            else:
                all_nreverse[k] = v
        all_setnodes[setname] = setnodes
    return all_elements, element_sets, all_nreverse, all_setnodes


def retrieve_CPS8(headings, lines):
    """
    Extract element sets from the file contents.

    Arguments:
        headings (list): list of (name, start, end) tuples.
        lines (list): list of lines.

    Returns:
        2) A dict of lists of element numbers indexed by volume name.
    """
    element_sets = {}
    n = 1
    for h in headings:
        name = h[0]
        lname = name.lower()
        if not lname.startswith("element"):
            continue
        if "type=CPS8".lower() not in lname:
            continue
        setname = [s.strip()[6:] for s in name.split(",") if "elset=" in s.lower()]
        if not setname:
            setname = f"unknown{n}"
            n += 1
        else:
            setname = setname[0]
        elements, _, _, = read_elements(lines, h[1], h[2], setname)
        element_sets[setname] = elements
    return element_sets


def read_elements(lines, start, end, setname):
    """
    Extract elements.

    Arguments:
        lines (list): A list of lines.
        start (int): first line to process.
        end (int): one past the last line to process.
        setname (str): name of the element set

    Returns:
        1) A dict of lists of node numbers, indexed by the element number.
        2) A set of all node numbers in this element set.
        3) A reverse-mapping dict of lists of element numbers indexed by node number.
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
    reverse = {}
    nodes = set()
    for ln in consol:
        elnum, *nodenums = [int(i) for i in ln.split(",")]
        elements[elnum] = nodenums
        nodes.update(nodenums)
        for n in nodenums:
            if n in reverse:
                reverse[n].append(elnum)
            else:
                reverse[n] = [elnum]
    return elements, nodes, reverse


def fix_volume_set_names(lines, headings, volsets, nodes):
    """
    Rename and merge the volume element sets to the name we chose.

    Arguments:
        lines (list): A list of lines.
        headings (list): list of (name, start, end) tuples.
        volsets (dict): A dict of lists of element numbers indexed by
            the volume set name.
        nodes (dict): A mapping of lists of volume set names indexed by node number.

    Returns:
        A dict of
    """
    newsets = {}
    newnodes = {}
    for h in headings:
        name = h[0]
        lname = name.lower()
        if not lname.startswith("elset"):
            continue
        try:
            setname = [s.strip()[6:] for s in name.split(",") if "elset=" in s.lower()][0]
        except IndexError:
            logging.error(f"volume set “{name}” without name")
            continue
        if setname == "all":
            continue
        elset = []
        for ln in lines[h[1]:h[2]]:
            elset += [int(j) for j in ln.strip().split(",") if j]
        for oname in volsets.keys():
            if set(volsets[oname].keys()).issubset(set(elset)):
                newnodes[setname] = nodes[oname]
                if setname not in newsets:
                    newsets[setname] = volsets[oname]
                    logging.info(f"renamed volume set “{oname}” to “{setname}”")
                else:
                    newsets[setname].update(volsets[oname])
                    logging.info(f"added “{oname}” to “{setname}”")
    for st in newsets:
        logging.info(f"volume set “{st}” has {len(newsets[st])} elements")
    return newsets, newnodes


def fix_surface_set_names(lines, headings, surfsets):
    """
    Rename and merge the surface element sets to the name we chose.

    Arguments:
        lines (list): A list of lines.
        headings (list): list of (name, start, end) tuples.
        surfsets (dict): A dict of lists of element numbers indexed by
            the surface set name.

    Returns:
        A dict of
    """
    newsets = {}
    for h in headings:
        name = h[0]
        lname = name.lower()
        if not lname.startswith("elset"):
            continue
        try:
            setname = [s.strip()[6:] for s in name.split(",") if "elset=" in s.lower()][0]
        except IndexError:
            logging.error(f"surface set “{name}” without name")
            continue
        if setname == "all":
            continue
        elset = []
        for ln in lines[h[1]:h[2]]:
            elset += [int(j) for j in ln.strip().split(",") if j]
        for oname in surfsets.keys():
            if set(surfsets[oname].keys()).issubset(set(elset)):
                if setname not in newsets:
                    newsets[setname] = surfsets[oname]
                    logging.info(f"renamed surface set “{oname}” to “{setname}”")
                else:
                    newsets[setname].update(surfsets[oname])
                    logging.info(f"added “{oname}” to “{setname}”")
    for st in newsets:
        logging.info(f"surface set “{st}” has {len(newsets[st])} elements")
    return newsets


# def read_element_numbers(lines, first, last):
#    rv = []
#    for ln in lines[first:last]:
#        rv += [int(j) for j in ln.strip().split(",")]
#    return rv


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
        (0, 1, 2, 3): "S1",
        (4, 7, 6, 5): "S2",
        (0, 4, 5, 1): "S3",
        (1, 5, 6, 2): "S4",
        (1, 6, 7, 3): "S5"
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


# def retrieve_nodesets(headings, lines):
#     nsets = {}
#     n = 1
#     for h in headings:
#         name = h[0]
#         lname = name.lower()
#         if not lname.startswith("nset"):
#             continue
#         setname = [s.strip()[5:] for s in name.split(",") if "nset=" in s.lower()]
#         if not setname:
#             setname = f"unknown{n}"
#             n += 1
#         else:
#             setname = setname[0]
#         nodes = []
#         for ln in lines[h[1]:h[2]]:
#             nodes += [int(i) for i in ln.split(",") if i != ""]
#         nsets[setname] = tuple(nodes)
#     return nsets


def make_eqns(nodes, Eall, nsets, volsets, exclude_from_eqns, nreverse):
    """Replace shared nodes between volume sets by equations.

    Arguments:
        nodes (dict): map of node numbers to (z,y,z)-tuples.
        Eall (dict): map of element numbers to lists of node numbers.
        nsets (dict): map of node set names to lists of node numbers.
        volsets (dict): map of volume set name to lists of element numbers.
        exclude_from_eqns (list): node set names for which no equation should
            be generated.
        nreverse (dict): map of node numbers to list of element numbers.

    """
    # For every node, gather the volumes it is in.
    nodectr = max(nodes.keys()) + 1
    byvolume = {}
    newnodes = {}
    # active_sets = set(nsets.keys()) - set(exclude_from_eqns)
    active_sets = volsets.keys()
    for n in nodes.keys():
        setnames = []
        for nn in active_sets:
            # There *is* a node set for every volume set.
            if n in nsets[nn]:
                setnames.append(nn)
        if len(setnames) > 1:
            byvolume[n] = setnames
            # Create new nodes and replace it in all but the first node sets.
            for otherset in setnames[1:]:
                # Create new node
                newnodes[nodectr] = nodes[n]
                # Replace in other node sets.
                nsets[otherset] = [j if j != n else nodectr for j in nsets[otherset]]
                logging.debug(f"replaced node {n} with {nodectr}")
                # Replace in elements.
                for elnum in nreverse[n]:
                    if elnum in volsets[otherset]:
                        enodes = Eall[elnum]
                        enodes[enodes.index(n)] = nodectr
                nodectr += 1

    nodes.update(newnodes)
    equations = []
    return equations, nodes, Eall


def write_output(outfn, nodes, elements, nsets, elsets, surfaces, reduced, equations):
    with open(outfn, "w") as outf:
        logging.info(f"opened output file “{outfn}”.")
        write_nodes(outf, nodes)
        write_elements(outf, elements, reduced)
        write_node_sets(outf, nsets)
        write_element_sets(outf, elsets)
        write_surfaces(outf, surfaces)
        write_equations(outf, equations)


def write_nodes(outf, nodes):
    outf.write("*NODE, NSET=Nall\n")
    for num, (x, y, z) in nodes.items():
        outf.write(f"{num:>8d},{x},{y},{z}\n")
    logging.info(f"wrote {len(nodes)} nodes to output file (node set “Nall”).")


def write_elements(outf, elements, reduced):
    extra = ""
    if reduced:
        logging.info("using reduced integration elements C3D20R")
        extra = "R"
    outf.write(f"*ELEMENT, TYPE=C3D20{extra}, ELSET=Eall\n")
    for elnum, nodenums in elements.items():
        first, second = [elnum] + nodenums[:10], nodenums[10:]
        line = ",".join(f"{i:>6d}" for i in first) + ",\n"
        outf.write(line)
        line = "     " + ",".join(f"{i:>6d}" for i in second) + "\n"
        outf.write(line)
    logging.info(f"wrote {len(elements)} elements to output file. (element set “Eall”)")


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


def write_equations(outf, equations):
    pass


def chunked(iterable, n):
    """
    Split an iterable up in chunks of length n.

    The second argument to the outer ``iter()`` is crucial to the way this works.
    See the documentation for ``iter()`` for details.
    """

    def take(n, iterable):
        return list(it.islice(iterable, n))

    return iter(ft.partial(take, n, iter(iterable)), [])


if __name__ == '__main__':
    main(sys.argv[1:])
