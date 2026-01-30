import json
import sys
import ast
from util import benchmarks as all_benchmarks
from util import ev_modules, get_weight


if len(sys.argv) != 3:
    print("Usage: python compare.py <summary1.json> <summary2.json>")
    sys.exit(1)

file1_path = sys.argv[1]
file2_path = sys.argv[2]

with open(file1_path, 'r') as f:
    result1 = json.load(f)
with open(file2_path, 'r') as f:
    result2 = json.load(f)

# Parse unsolved benchmarks from JSON (they are stored as string tuples like "(0, 1)")
unsolved1 = set(ast.literal_eval(item) for item in result1.get("unsolved", []))
unsolved2 = set(ast.literal_eval(item) for item in result2.get("unsolved", []))

only_hammer1 = set(ast.literal_eval(item) for item in result1.get("hammer_only", []))
only_hammer2 = set(ast.literal_eval(item) for item in result2.get("hammer_only", []))

print(only_hammer1 - only_hammer2)
print(only_hammer2 - only_hammer1)

all_benchmark1 = set(ast.literal_eval(item) for item in result1["detailed_results"].keys())
all_benchmark2 = set(ast.literal_eval(item) for item in result2["detailed_results"].keys())

# Calculate solved benchmarks as all benchmarks minus unsolved
solved1 = all_benchmark1 - unsolved1
solved2 = all_benchmark2 - unsolved2

solved_both = solved1 & solved2
solved_only1 = solved1 & unsolved2
solved_only2 = solved2 & unsolved1

name1 = file1_path.split('/')[-1][len('summary-'):-len('.json')]
name2 = file2_path.split('/')[-1][len('summary-'):-len('.json')]

sum1 = 0
sum2 = 0
print(f"Number of benchmarks solved by both: {len(solved_both)}")
for benchmark in solved_both:
    s, i = benchmark#benchmarksolved1benchmark.strip("()").split(',')
    sum1 += result1["detailed_results"][str(benchmark)]["num_tokens"] + sum([
        result1["detailed_results"][str(benchmark)]["ev_num_tokens"][module] * get_weight(name1, module)
        for module in ev_modules
    ])
    sum2 += result2["detailed_results"][str(benchmark)]["num_tokens"] + sum([
        result2["detailed_results"][str(benchmark)]["ev_num_tokens"][module] * get_weight(name2, module)
        for module in ev_modules
    ])

print(f"Total tokens in file1 ({file1_path}): {sum1}")
print(f"Total tokens in file2 ({file2_path}): {sum2}")
print((sum1 - sum2) / sum1)

print(f"benchmarks solved by only file1: {sorted(list(solved_only1))}")
print(f"benchmarks solved by only file2: {sorted(list(solved_only2))}")