#!/usr/bin/env python3
import sys
from collections import defaultdict
from itertools import combinations, permutations
from math import comb

from ortools.sat.python import cp_model
from scipy.sparse import dok_matrix
from scipy.sparse.csgraph import connected_components

edges = []
for line in sys.stdin:
    words = line.split()
    if words:
        if len(words) == 2:
            a, b = words
            edges.append((a, b, 1))
        else:
            a, b, w = words
            edges.append((a, b, int(w)))

vertex_set = {a for a, b, w in edges} & {b for a, b, w in edges}
vertices = sorted(vertex_set)
scale = len(vertices) + 1
vertex_index = {a: i for i, a in enumerate(vertices)}
weight = {}
adjacent = dok_matrix((len(vertices), len(vertices)), dtype=bool)
for a, b, w in edges:
    if a in vertex_set and b in vertex_set:
        weight[a, b] = weight.get((a, b), 1) + w * scale
        adjacent[vertex_index[a], vertex_index[b]] = True

n_components, labels = connected_components(adjacent, connection="strong")
components = defaultdict(list)
for vertex, label in zip(vertices, labels):
    components[label].append(vertex)

total_score = 0

for label, members in components.items():
    if len(members) == 1:
        continue

    print(f"# component of {len(members)}:", *members, file=sys.stderr)

    model = cp_model.CpModel()

    after = {
        (a, b): model.NewBoolVar(f"after{a, b}") for a, b in combinations(members, 2)
    }
    for a, b in combinations(members, 2):
        after[b, a] = after[a, b].Not()

    score = sum(
        weight[a, b] * after[a, b]
        for a, b in permutations(members, 2)
        if adjacent[vertex_index[a], vertex_index[b]]
    )

    max_count = comb(len(members), 3)
    for count, (a, b, c) in enumerate(combinations(members, 3)):
        model.AddBoolOr([after[a, b], after[b, c], after[c, a]])
        model.AddBoolOr([after[a, c], after[c, b], after[b, a]])

    model.Minimize(score)

    solver = cp_model.CpSolver()

    class SolutionPrinter(cp_model.CpSolverSolutionCallback):
        def on_solution_callback(self):
            print(
                "# found",
                self.Value(score) // scale,
                self.Value(score) % scale,
                file=sys.stderr,
            )

    solver.parameters.num_search_workers = 6
    print("# solving", file=sys.stderr)
    print(
        "#",
        solver.StatusName(solver.SolveWithSolutionCallback(model, SolutionPrinter())),
        file=sys.stderr,
    )
    for a, b in permutations(members, 2):
        if adjacent[vertex_index[a], vertex_index[b]] and solver.Value(after[a, b]):
            print(a, b, weight[a, b] // scale)
    total_score += solver.Value(score)

print(total_score // scale, total_score % scale)
