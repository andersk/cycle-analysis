#!/usr/bin/env python3
import sys
from dataclasses import dataclass
from math import comb

import highspy
from scipy.sparse import dok_matrix
from scipy.sparse.csgraph import connected_components


@dataclass
class Component:
    vertices: list[str]
    index: dict[str, int]
    edges: list[tuple[int, int, float]]


edges: list[tuple[str, str, float]] = []
for line in sys.stdin:
    words = line.split()
    if words:
        if len(words) == 2:
            vertex_a, vertex_b = words
            edges.append((vertex_a, vertex_b, 1))
        else:
            vertex_a, vertex_b, w_str = words
            edges.append((vertex_a, vertex_b, int(w_str)))

vertex_set = {vertex_a for vertex_a, vertex_b, w in edges} & {
    vertex_b for vertex_a, vertex_b, w in edges
}
vertices = sorted(vertex_set)
scale = len(vertices) + 1
vertex_index = {vertex: i for i, vertex in enumerate(vertices)}
weight: dict[tuple[str, str], float] = {}
adjacent = dok_matrix((len(vertices), len(vertices)), dtype=bool)
for vertex_a, vertex_b, w in edges:
    if vertex_a in vertex_set and vertex_b in vertex_set:
        weight[vertex_a, vertex_b] = weight.get((vertex_a, vertex_b), 1) + w * scale
        adjacent[vertex_index[vertex_a], vertex_index[vertex_b]] = True

n_components: int
n_components, labels = connected_components(adjacent, connection="strong")
components = [
    Component(vertices=[], index={}, edges=[]) for label in range(n_components)
]
for vertex, label in zip(vertices, labels):
    component = components[int(label)]
    component.index[vertex] = len(component.vertices)
    component.vertices.append(vertex)

total_score = 0.0
total_cut = 0.0

output_edges = {}

for (vertex_a, vertex_b), w in weight.items():
    if (vertex_b, vertex_a) in weight:
        output_edges[vertex_a, vertex_b] = 0.0
    label = labels[vertex_index[vertex_a]]
    if label == labels[vertex_index[vertex_b]]:
        if vertex_a == vertex_b:
            total_score += w
            total_cut += 1.0
            print(vertex_a, vertex_a, w, 1.0, file=sys.stderr)
            output_edges[vertex_a, vertex_a] = 1.0
        else:
            component = components[label]
            component.edges.append(
                (component.index[vertex_a], component.index[vertex_b], w)
            )

for label, component in enumerate(components):
    n = len(component.vertices)
    if n == 1:
        continue

    m = len(component.edges)

    print(
        f"// component of {n} vertices and {m} edges:",
        *component.vertices,
        file=sys.stderr,
    )

    triangles = sorted(
        {
            min((a, b, c), (b, c, a), (c, a, b))
            for a in range(n)
            for b, c, w in component.edges
            if a not in (b, c)
        }
    )

    lp = highspy.HighsLp()
    lp.num_col_ = comb(n, 2)
    lp.num_row_ = len(triangles)
    col_cost = [0.0] * comb(n, 2)
    for a, b, w in component.edges:
        if a < b:
            col_cost[a + comb(b, 2)] += w
        else:
            col_cost[b + comb(a, 2)] -= w
    lp.col_cost_ = col_cost
    lp.col_lower_ = [0.0] * comb(n, 2)
    lp.col_upper_ = [1.0] * comb(n, 2)
    lp.row_lower_ = [0.0 if b < c else -1.0 for a, b, c in triangles]
    lp.row_upper_ = [highspy.kHighsInf] * len(triangles)
    lp.a_matrix_.format_ = highspy.MatrixFormat.kRowwise
    lp.a_matrix_.num_col_ = comb(n, 2)
    lp.a_matrix_.num_row_ = len(triangles)
    lp.a_matrix_.start_ = range(0, len(triangles) * 3 + 1, 3)
    lp.a_matrix_.index_ = [
        index
        for a, b, c in triangles
        for index in [a + comb(b, 2), min(b, c) + comb(max(b, c), 2), a + comb(c, 2)]
    ]
    lp.a_matrix_.value_ = [
        value for a, b, c in triangles for value in [1.0, 1.0 if b < c else -1.0, -1.0]
    ]
    h = highspy.Highs()
    h.setOptionValue("log_to_console", False)
    h.passModel(lp)
    h.run()
    d = h.getSolution().col_value

    for a, b, w in component.edges:
        cut = d[a + comb(b, 2)] if a < b else 1.0 - d[b + comb(a, 2)]
        total_score += cut * (w - 1) / scale
        total_cut += cut
        if cut >= 1e-8:
            print(component.vertices[a], component.vertices[b], w, cut)
            output_edges[component.vertices[a], component.vertices[b]] = cut

    for (a, b, c), x in zip(triangles, h.getSolution().row_dual):
        if x < 1e-8:
            continue
        if d[a + comb(b, 2)] < 1e-8:
            output_edges.setdefault((component.vertices[a], component.vertices[b]), 0)
        if (d[b + comb(c, 2)] if b < c else 1.0 - d[c + comb(b, 2)]) < 1e-8:
            output_edges.setdefault((component.vertices[b], component.vertices[c]), 0)
        if 1.0 - d[a + comb(c, 2)] < 1e-8:
            output_edges.setdefault((component.vertices[c], component.vertices[a]), 0)

print("digraph {")
print("  newrank=true")
for (vertex_a, vertex_b), cut in sorted(output_edges.items()):
    if cut > 0:
        extra = (
            ""
            if cut > 1 - 1e-8
            else f',style="dashed",fontcolor="red",label="{round(cut, 3)}"'
        )
        print(f'  "{vertex_b}" -> "{vertex_a}" [color="red",dir=back{extra}]')
    else:
        print(f'  "{vertex_a}" -> "{vertex_b}"')
print("}")
print(f"{total_score} {total_cut}", file=sys.stderr)
