#!/usr/bin/env python

import random
import argparse

desc = """
Generate random access pattern.
Each address in range [base, base+length) will be accessed only once,
but in random order. This ensures that no data will be overwritten.
"""
parser = argparse.ArgumentParser(description=desc)
parser.add_argument('base',       help='Base address')
parser.add_argument('length',     help='Number of (address, data) pairs')
parser.add_argument('data_width', help='Width of data (used to determine max value)')
parser.add_argument('--seed',     help='Use given random seed (int)')
args = parser.parse_args()

if args.seed:
    random.seed(int(args.seed, 0))

base = int(args.base, 0)
length = int(args.length, 0)
data_width = int(args.data_width, 0)

address = list(range(length))
random.shuffle(address)
data = [random.randrange(0, 2**data_width) for _ in range(length)]

for a, d in zip(address, data):
    print('0x{:08x},0x{:08x}'.format(a, d))
