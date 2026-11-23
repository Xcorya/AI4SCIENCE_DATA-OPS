"""Small inspectable raw-file extractors. Unsupported binary modalities stay unparsed."""
import csv
import io
import math
import re


def extract(data, spec):
    if not isinstance(spec, dict):
        raise ValueError("Extraction settings must be an object")
    kind = spec.get("format")
    if kind in ("csv", "stl") and (
            not isinstance(spec.get("unit"), str) or not spec["unit"].strip()):
        raise ValueError("CSV and STL extraction require a non-empty unit")
    text = data.decode("utf-8-sig")
    if kind == "csv":
        reader = csv.DictReader(io.StringIO(text))
        column = spec.get("column")
        if not reader.fieldnames or column not in reader.fieldnames:
            raise ValueError("CSV measurement column not found")
        values = [float(row[column]) for row in reader]
        quantity, unit = column, spec["unit"]
    elif kind == "fasta":
        sequences, sequence = [], []
        for line in text.splitlines():
            line = line.strip()
            if line.startswith(">"):
                if sequence:
                    sequences.append("".join(sequence))
                sequence = []
            elif line:
                if not re.fullmatch("[A-Za-z*.-]+", line):
                    raise ValueError("Invalid FASTA sequence")
                sequence.append(line)
        if sequence:
            sequences.append("".join(sequence))
        values = [len(s) for s in sequences]
        quantity, unit = "sequence_length", "residue"
    elif kind == "xyz":
        lines = text.splitlines()
        if len(lines) < 2:
            raise ValueError("XYZ requires an atom count and a comment line")
        count = int(lines[0])
        if len(lines) < count + 2 or count < 3:
            raise ValueError("XYZ requires at least three atoms")
        atoms = []
        for line in lines[2:count + 2]:
            fields = line.split()
            if len(fields) != 4:
                raise ValueError("XYZ line must contain element and x y z")
            atoms.append(tuple(float(x) for x in fields[1:]))
        values = [math.sqrt(sum((b - a) ** 2 for a, b in zip(atoms[0], atom))) for atom in atoms[1:]]
        quantity, unit = "distance_from_first_atom", spec.get("unit", "angstrom")
    elif kind == "stl":
        vertices = []
        for line in text.splitlines():
            parts = line.split()
            if parts and parts[0].lower() == "vertex":
                if len(parts) != 4:
                    raise ValueError("Invalid ASCII STL vertex")
                vertices.append(tuple(float(v) for v in parts[1:]))
        if len(vertices) < 6 or len(vertices) % 3:
            raise ValueError("ASCII STL requires complete triangles and at least two facets")
        values = []
        for i in range(0, len(vertices), 3):
            a, b, c = vertices[i:i + 3]
            u, v = [b[j] - a[j] for j in range(3)], [c[j] - a[j] for j in range(3)]
            cross = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
            values.append(math.sqrt(sum(x*x for x in cross)) / 2)
        quantity, unit = "triangle_area", spec["unit"] + "^2"
    else:
        raise ValueError("Implemented extractors: csv, fasta, xyz, ASCII stl")
    if len(values) < 2 or not all(math.isfinite(v) for v in values):
        raise ValueError("Need at least two finite numeric observations")
    return {"quantity": quantity, "values": values, "unit": unit}
