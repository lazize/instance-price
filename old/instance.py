import os
import sys

# get parameter from command line
if len(sys.argv) > 1:
    memory = sys.argv[1]
memory = int(memory)
memory_lower = memory - 8

if len(sys.argv) > 1:
    cores = sys.argv[2]
cores = int(cores)

instances = [
    ("m7i.large", 2, 1, 8),
    ("r7i.large", 2, 1, 16),
    ("m7i.xlarge", 4, 2, 16),
    ("r7i.xlarge", 4, 2, 32),
    ("m7i.2xlarge", 8, 4, 32),
    ("r7i.2xlarge", 8, 4, 64),
    ("m7i.4xlarge", 16, 8, 64),
    ("r7i.4xlarge", 16, 8, 128),
    ("m7i.8xlarge", 32, 16, 128),
    ("r7i.8xlarge", 32, 16, 256),
    ("m7i.12xlarge", 48, 24, 192),
    ("r7i.12xlarge", 48, 24, 384),
    ("m7i.16xlarge", 64, 32, 256),
    ("r7i.16xlarge", 64, 32, 512),
    ("m7i.24xlarge", 96, 48, 384),
    ("m7i.metal-24xl", 96, 48, 384),
    ("r7i.24xlarge", 96, 48, 768),
    ("r7i.metal-24xl", 96, 48, 768),
    ("m7i.48xlarge", 192, 96, 768),
    ("m7i.metal-48xl", 192, 96, 768),
    ("r7i.48xlarge", 192, 96, 1536),
    ("r7i.metal-48xl", 192, 96, 1536),
]

def get_instance(memory, cores):
    exactly_match_memory = [ x for x in instances if x[3] == memory and x[2] >= cores ]
    if exactly_match_memory:
        return [exactly_match_memory[0]]

    match_lower_memory = [ x for x in instances if (x[3] >= memory_lower and x[3] <= memory) and x[2] >= cores ] 
    # if match_lower_memory:
    #     return match_lower_memory[0]

    match_high_memory = [ x for x in instances if x[3] > memory and x[2] >= cores ]
    # if match_high_memory:
    #     return [match_high_memory[0]]

    if match_lower_memory and match_high_memory:
        return [match_lower_memory[0], match_high_memory[0]]
    elif match_lower_memory:
        return [match_lower_memory[0]]
    elif match_high_memory:
        return [match_high_memory[0]]
    else:
        print("ERROR: This condition should never happens!!!")

instances = get_instance(memory, cores)

if not instances:
    print("-")
else:
    if len(instances) == 1:
        inst = instances[0]
        print(f"{inst[0]} {inst[2]} {inst[3]}")
    else:
        inst = instances[0]
        inst1 = instances[1]
        print(f"{inst[0]} {inst[2]} {inst[3]} {inst1[0]} {inst1[2]} {inst1[3]}")
