benchmarks = [(0, x) for x in range(173)] + [(1, x) for x in range(40)]
invalid_benchmarks = [
    (0, 9),
    (0, 15),
    (0, 25),
    (0, 38),
    (0, 50),
    (0, 143),
    (0, 163),
    (1, 12),
    (1, 20),
    (1, 25),
    (1, 27),
    (1, 35),
    (0, 172)
]
benchmarks = [x for x in benchmarks if x not in invalid_benchmarks]
