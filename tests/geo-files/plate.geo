// vim:fileencoding=utf-8:ft=gmsh
// Use “gmsh <filename> -” to run non-interactively.

SetFactory("OpenCASCADE");
// Convert coordinates to meters
Geometry.OCCTargetUnit = "M";
Merge "plate.stp";

// Describe all physical groups to be saved.
Physical Surface("Nload") = {7};
Physical Surface("Nfix") = {9};
Physical Volume("ignore",1) = {1};

Mesh.Algorithm = 2; // Automatic
Mesh.ElementOrder = 2; // Create second order elements.
Mesh.SecondOrderIncomplete = 1;

Mesh.MeshSizeFromCurvature = 10;
Mesh.MeshSizeMax = 0.10;
Mesh.Smoothing = 10;

Mesh.FirstNodeTag = 2; // Keep node 1 free for ref node.
Mesh.Format = 39; // Save mesh as INP format.
Mesh.SaveGroupsOfNodes = 1;
Mesh.SaveGroupsOfElements = 1; // Save volume and surface elements.
Mesh.Optimize = 1;

Mesh 3;
OptimizeMesh "Gmsh";
Coherence Mesh;

Save "plate-mesh.inp";
