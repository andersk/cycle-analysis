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

component_weight = {}
for (a, b), w in weight.items():
    if labels[vertex_index[a]] == labels[vertex_index[b]]:
        component_weight.setdefault(labels[vertex_index[a]], {})[a, b] = w


class SolutionPrinter(cp_model.CpSolverSolutionCallback):
    def on_solution_callback(self):
        print(
            end=f"{self.Value(score) // scale} {self.Value(score) % scale}, ",
            file=sys.stderr,
            flush=True,
        )


def find_cycles(a, edges):
    if a in depth:
        if depth[a] is None:
            return 0
        model.AddBoolOr(edges[depth[a] :])
        return 1
    cycles = 0
    depth[a] = len(edges)
    for b in outgoing.get(a, []):
        if not solver.Value(cut[a, b]):
            edges.append(cut[a, b])
            cycles += find_cycles(b, edges)
            edges.pop()
    depth[a] = None
    return cycles


total_score = 0

for label, members in components.items():
    if len(members) == 1:
        continue

    print(f"# component of {len(members)}:", *members, file=sys.stderr)

    model = cp_model.CpModel()
    cut = {(a, b): model.NewBoolVar(f"cut{a, b}") for a, b in component_weight[label]}
    score = sum(weight[a, b] * cut[a, b] for a, b in component_weight[label])
    model.Minimize(score)

    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 6

    outgoing = {}
    for a, b in component_weight[label]:
        outgoing.setdefault(a, []).append(b)

    while True:
        print(end="# solving: ", file=sys.stderr, flush=True)
        status = solver.SolveWithSolutionCallback(model, SolutionPrinter())
        assert status == cp_model.OPTIMAL
        depth = {}
        cycles = sum(find_cycles(a, []) for a in members)
        print(f"{cycles=}", file=sys.stderr)
        if cycles == 0:
            break

    for (a, b), w in component_weight[label].items():
        if solver.Value(cut[a, b]):
            print(a, b, w // scale)
    total_score += solver.Value(score)

print(total_score // scale, total_score % scale)
