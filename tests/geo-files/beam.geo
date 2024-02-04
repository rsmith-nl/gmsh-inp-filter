// file: beam.geo
// vim:fileencoding=utf-8:ft=gmsh
//
// Author: R.F. Smith <rsmith@xs4all.nl>
// Created: 2024-02-04T21:48:14+0100
// Last modified: 2024-02-04T21:49:06+0100
SetFactory("OpenCASCADE");

// Beam parameters. All dimensions in SI units.
W = 40/1000;
H = 70/1000;
t = 4/1000;
L = 0.8;

// Create beam
Rectangle(1) = {0,0,0, W, H};
Rectangle(2) = {t,t,0, W-2*t,H-2*t};
BooleanDifference{Surface{1}; Delete;}{Surface{2}; Delete;} // Result is surface 1
Extrude {0,0,L}{Surface{1};}
Physical Volume("beam") = {1};
Physical Surface("fix") = {1};
Physical Surface("load") = {10};
// Rigid body node.
Point(41) = {W/2,H/2,L};
Physical Point("rigid") = {41};

Mesh.CharacteristicLengthMin = 0.001;
Mesh.CharacteristicLengthMax = 0.02;
Mesh.Algorithm = 8;  // Frontal Delauney for quads.
Mesh.Algorithm3D = 1; // Delauney
Mesh.ElementOrder = 2; // Create second order elements.
Mesh.SubdivisionAlgorithm = 2; // All hex elements
Mesh.SecondOrderIncomplete = 1; // Use 20-node hex elements.
Mesh.Format = 39; // Save mesh as INP format.
Mesh.SaveGroupsOfNodes = 1;
Mesh.Optimize = 1;

// Create mesh
Mesh 3;
Coherence Mesh;
Save "beam-mesh.inp";
