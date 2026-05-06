# Variable Delta Encoding (VDE)
This repository hosts the specification and reference implementation for the Variable Delta Encoding (VDE) file format.

VDE is a specialized file format designed for efficiently storing and range-querying long sequences of large, non-negative, non-decreasing integers.

VDE is a simple file format with very low overhead and built-in error checking. It provides file-size reduction very close to the theoretical maximum for appropriate datasets, with no intermediate compression/decompression step.

## Motivation
In researching certain subsets of integers, I needed to generate and manipulate sorted vectors of billions of large integers. Traditional file formats generate unwieldy files. Traditional compression methods add an extra step, slowing down and complicating manipulation, and still yielding large file sizes.

So I designed a file format for the type of problems we are facing: a sequence of large, non-decreasing integers whose first-difference sequence has a regular structure. This file format reduces file sizes over 95% compared to naive methods, with no separate compression/decompression step, while keeping retrieval fast.

## Metrics
We generate 2 million integers of sizes up to an order of magnitude of $10^{65}$ as a toy example, with the python function:

```
noisy_plateau_sequence(num_plateaus=20,
                       plateau_size=100_000,
                       start=10**12,
                       max_delta=255,
                       step_multiplier=1_000)
```

Storing these numbers in a CSV results in a 76 MB file.
Storing them as raw binary, with the smallest possible constant byte size, results in a 56 MB file.
In comparison, VDE uses only 2.01 MB.
The theoretical lower bound being 2.00 MB for a byte-aligned file format, this showcases the very low overhead of the file format.

If we pay the cost of a compression step, with the gzip algorithm, uncompressed VDE still showcases over 70% reduction in file size.

In this tailored example, gzip adds almost no benefit to VDE.


We see the following numbers:

| Metric | Value |
|---|---:|
| Number of ints | 2,000,000 |
| CSV size | 75,945,911 bytes |
| CSV.gz size | 6,901,488 bytes |
| RawBinary size | 56,000,000 bytes |
| RawBinary.gz size | 23,368,709 bytes |
| VDE size | 2,011,029 bytes |
| VDE.gz size | 2,010,477 bytes |

| Comparison | Reduction |
|---|---:|
| VDE vs RawBinary | 96.4% |
| VDE vs RawBinary.gz | 91.4% |
| VDE vs CSV | 97.4% |
| VDE vs CSV.gz | 70.9% |
| VDE.gz vs RawBinary | 96.4% |
| VDE.gz vs CSV.gz | 70.9% |
