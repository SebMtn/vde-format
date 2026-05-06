# Variable Delta Encoding Specification 1.0

This document is the normative specification for Variable Delta Encoding
file format version 1.0.

Canonical source:
https://github.com/SebMtn/vde-format/blob/main/SPECIFICATION_VDE_1_0.md

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD",
"SHOULD NOT", "RECOMMENDED",  "MAY", and "OPTIONAL" in this document are to be interpreted
as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

## 1. Overview

Variable Delta Encoding (VDE) is an open source binary file format designed for efficiently
storing and range-querying long sequences of large, non-negative,
monotonically non-decreasing integers.

A VDE file stores values in blocks. Each block stores one full starting value,
a shared step value, a sequence of deltas of fixed binary widths, and a final value used
for block consistency checking.

## 2. File Extension

VDE files SHOULD use the extension:

```text
.vde
```

## 3. File Header

A VDE 1.0 file MUST begin with the following binary file header:

| Offset | Size | Field | Value |
|---:|---:|---|---|
| 0 | 4 bytes | Magic number | `56 44 45 00` |
| 4 | 2 bytes | Major version | `01 00` |
| 6 | 2 bytes | Minor version | `00 00` |

The magic number is:

```text
56 44 45 00
```

which corresponds to:

```text
VDE\0
```

The major and minor version fields are unsigned 2-byte little-endian integers.

For VDE 1.0, the complete file header is therefore:

```text
56 44 45 00 01 00 00 00
```

A VDE reader MUST reject files whose magic number is not exactly `56 44 45 00`.

A VDE reader MUST reject unsupported version fields.

## 4. Terminology and Notation

The following terms are used in this specification:

| Term | Meaning |
|---|---|
| Element | An integer in the sequence |
| Block | A self-contained group of encoded elements |
| Step | The shared multiplier of a block, stored in a block header, used to decode elements |
| Delta | An unsigned integer stored in a block, used to decode elements |
| Trailer element | The final value of a block, used for a consistency check |
| uvarint | Unsigned variable-length integer |

- $i$ index of the integer sequence to be encoded in the VDE file
- $N$ highest index of the integer sequence
- $(v_i)_{0 \le i \le N}$ : integer sequence, i.e. sequence of elements
- $j$: index of a block inside a VDE file
- $s_j$: step value of block $j$
- $k$ : index of a delta inside a block
- $\delta_{j,k}$: delta of block $j$, of index $k$



## 5. Value Domain

A VDE 1.0 file stores a sequence of non-negative, monotonically non-decreasing integers.

i.e. all values MUST satisfy:

$$
v_i \ge 0 
$$

and:

$$
v_i \le v_{i+1}
$$

VDE integers are arbitrary precision at the format level.

## 6. Byte Order

All fixed-width integers in VDE 1.0 are stored in little-endian byte order.

This applies to:

- file header version fields
- fixed-width deltas inside blocks

## 7. Unsigned Varint Encoding

VDE uses an unsigned LEB128-style variable-length integer encoding, referred
to in this specification as `uvarint`.

This specification defines the exact encoding below. References to LEB128 are
descriptive and are not required to implement VDE.

A `uvarint` encodes a non-negative integer using 7 payload bits per byte.

For each byte:

- bits `0..6` contain payload bits
- bit `7` is the continuation bit

If the continuation bit is `1`, another byte follows.

If the continuation bit is `0`, this byte is the final byte of the integer.

The least significant 7-bit group is stored first.

In pseudocode:

```text
while true:
    byte = value & 0x7f
    value = value >> 7

    if value != 0:
        write(byte | 0x80)
    else:
        write(byte)
        stop
```

Examples:

| Integer | Encoded bytes |
|---:|---|
| `0` | `00` |
| `1` | `01` |
| `127` | `7f` |
| `128` | `80 01` |
| `300` | `ac 02` |

VDE 1.0 uvarints MUST NOT encode negative integers.

## 8. File Layout

A VDE file consists of:

```text
[file header]
[zero or more blocks]
```

A file with no blocks is valid and represents an empty sequence.

## 9. Block Layout

Each block has the following layout:
```text
[block header]
[deltas]
[block trailer]
```

The block prefix is exactly:

```text
56 44 45 01
```

which corresponds to:

```text
VDE\x01
```

A block header has the following layout:
```text
[block prefix]
uvarint(element_value)
uvarint(step_value)
uvarint(delta_size)
uvarint(num_deltas)
```


| Field | Encoding | Meaning |
|---|---|---|
| `element_value` | `uvarint` | First element of the block |
| `step_value` | `uvarint` | Step value |
| `delta_size` | `uvarint` | Number of bytes used for each delta |
| `num_deltas` | `uvarint` | Number of deltas in the block |

After the block header, the block stores exactly `num_deltas * delta_size` bytes of delta data.

Each delta is an unsigned integer stored in exactly `delta_size` bytes, little-endian.

A block trailer has the following layout:

```text
uvarint(element_value)
```

The trailer's element value is the final element of the block.

## 10. Block Validity Rules

A VDE 1.0 block MUST satisfy:

- `step_value >= 1`
- `delta_size >= 1`
- `num_deltas >= 0`
- all deltas are unsigned integers
- the fully decoded final value equals the trailer's element value

A block with `num_deltas = 0` contains exactly one decoded value,
equal to both the header's element value and the trailer's element value.


## 11. Decoding a Block

Let $M_j$ be `num_deltas` for block $j$.

For all $k$ such that $0 \le k \le M_j$, let $v_{j,k}$ be element $k$ of block $j$.

Let:
- $h_j$ be `element_value` in header of block $j$
- $s_j$ be `step_value` in header of block $j$
- $t_j$ be `element_value` in trailer of block $j$


$$
v_{j,0} = h_j
$$

For each delta $\delta_{j, k}$, decode:

$$
v_{j, k+1} = v_{j, k} + \delta_{j, k}  \times s_j
$$

Therefore, a block containing `num_deltas` deltas decodes to `num_deltas + 1` elements.

After decoding all deltas, a reader MUST verify:

$$
v_{j,M_j} = t_j
$$

If this check fails, the file MUST be considered invalid.

## 12. Encoding a Block

Given a non-empty sequence of values:

```text
x_0, x_1, ..., x_n
```

the encoder computes adjacent differences:

$$
\Delta_k = x_{k+1} - x_k
$$

Each difference MUST be non-negative.

A valid encoder MUST choose a positive `step_value` such that every difference
is divisible by `step_value`.

A valid encoder MAY choose this `step_value`:

```text
step_value = gcd(Δ_0, Δ_1, ..., Δ_{n-1})
```

with the special case:

```text
step_value = 1
```

if all differences are zero or if the block contains only one value.

Deltas are then computed as:

$$
\delta_k = \Delta_k / s
$$

where $s$ is the chosen `step_value`.

The encoder MUST choose the smallest positive `delta_size` such that every $\delta_k$
fits in `delta_size` bytes.

The block trailer's element value is equal to $x_n$.

## 13. Range Queries

VDE is designed to support efficient range iteration over sorted values.

Range queries SHOULD use half-open intervals:

```text
min_value <= value < max_value
```

Because blocks store both their first value and final value, readers MAY skip
or stop reading blocks:

- If the trailer's element value is less than `min_value`, the entire block is below the range.
- If `element_value >= max_value`, the block and all following blocks are outside
  the range, assuming the file sequence is globally non-decreasing.

A reader performing partial range iteration MAY stop decoding a block before
reaching its trailer value.

Full block decoding MUST perform the trailer consistency check.

## 14. Error Handling

A reader MUST reject a VDE file if:

- the file header magic is invalid
- the VDE version is unsupported
- a block prefix is invalid
- a uvarint is truncated
- delta bytes are truncated
- `delta_size` is zero
- `step_value` is zero
- the decoded sequence decreases

Implementations MAY impose additional limits, such as maximum block size,
maximum integer size, or maximum decoded value count.
Should they choose to do so, they MUST document them in their own documentation.

## 15. Consistency Checking

Each block stores its expected final decoded value in the trailer's element value.

When a reader fully decodes a block, it MUST verify that the final decoded value
matches the trailer's element value.

This check is intended to catch some classes of errors and corruption in transit or at rest.
It is part of the VDE 1.0 block format.

## 16. Versioning

This specification defines VDE version 1.0.

The file header contains:

```text
major version: 1
minor version: 0
```

A change to the major version indicates a potentially incompatible format
change.

A change to the minor version indicates an extension or compatible revision,
provided the major version remains unchanged.

A VDE 1.0 reader MUST support version `1.0`.

A VDE 1.0 reader MAY reject any version other than `1.0`.


## 17. Example

Consider the sequence:

```text
1000, 1010, 1020, 1050
```

The first differences are:

```text
10, 10, 30
```

The greatest common divisor is:

```text
10
```

So the block can be encoded as:

```text
[header]
  element_value = 1000
  step_value = 10
  delta_size = 1
  num_deltas = 3
[deltas]
  1
  1
  3
[trailer]
  element_value = 1050
```

Decoded values are reconstructed as:

```text
v_0 = 1000
v_1 = 1000 + 1 * 10 = 1010
v_2 = 1010 + 1 * 10 = 1020
v_3 = 1020 + 3 * 10 = 1050
```

The final value matches the trailer value, so the block is valid.

## 18. Conformance

A conforming VDE 1.0 writer MUST produce files that satisfy this specification.

A conforming VDE 1.0 reader MUST correctly decode any valid VDE 1.0 file,
subject to its documented implementation limits.

A conforming reader MUST reject invalid files as described in this specification.