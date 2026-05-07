import io
import unittest
import os
import tempfile
import gzip
import random
import sys
from pathlib import Path
from vde_io import VdeIO


def noisy_plateau_sequence(num_plateaus: int,
                        plateau_size: int,
                        start: int,
                        step_multiplier: int,
                        max_delta: int = 255,
                        seed: int = 0) -> list[int]:
    rng = random.Random(seed)

    values = []
    current = start
    step = 10

    for _ in range(num_plateaus):
        for _ in range(plateau_size):
            values.append(current)
            current += rng.randint(1, max_delta) * step

        step *= step_multiplier

    return values


def run():
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "ints.csv")
        csv_gz_path = os.path.join(tmpdir, "ints.csv.gz")
        rawbinary_path = os.path.join(tmpdir, "ints-rawbinary.bin")
        rawbinary_gz_path = os.path.join(tmpdir, "ints-rawbinary.bin.gz")
        vde_path = os.path.join(tmpdir, "ints.vde")
        vde_gz_path = os.path.join(tmpdir, "ints.vde.gz")

        ints = noisy_plateau_sequence(num_plateaus=20,
                                        plateau_size=100_000,
                                        start=10**12,
                                        max_delta=255,
                                        step_multiplier=1_000)

        num_bytes = (ints[-1].bit_length() + 7) // 8

        with open(rawbinary_path, "wb") as f:
            for x in ints:
                f.write(int(x).to_bytes(num_bytes,
                                        byteorder="little",
                                        signed=False))

        with gzip.open(rawbinary_gz_path, "wb") as f_gz:
            with open(rawbinary_path, "rb") as f:
                f_gz.write(f.read())

        with open(csv_path, "w", encoding="ascii") as f:
            for x in ints:
                f.write(f"{x}\n")

        with gzip.open(csv_gz_path, "wt", encoding="ascii") as f:
            for x in ints:
                f.write(f"{x}\n")

        with open(vde_path, "wb") as f:
            VdeIO.write(ints, f)

        with gzip.open(vde_gz_path, "wb") as f_gz:
            with open(vde_path, "rb") as f:
                f_gz.write(f.read())

        def percent(old_size: int, new_size: int) -> float:
            return 100 * (1 - new_size / old_size)

        rawbinary_size = os.path.getsize(rawbinary_path)
        rawbinary_gz_size = os.path.getsize(rawbinary_gz_path)
        csv_size = os.path.getsize(csv_path)
        csv_gz_size = os.path.getsize(csv_gz_path)
        vde_size = os.path.getsize(vde_path)
        vde_gz_size = os.path.getsize(vde_gz_path)

        print()
        print(f"Number of ints:      {len(ints):,}")
        print(f"CSV size:            {csv_size:,} bytes")
        print(f"CSV.gz size:         {csv_gz_size:,} bytes")
        print(f"RawBinary size:      {rawbinary_size:,} bytes")
        print(f"RawBinary.gz size:   {rawbinary_gz_size:,} bytes")
        print(f"VDE size:            {vde_size:,} bytes")
        print(f"VDE.gz size:         {vde_gz_size:,} bytes")
        print(f"VDE vs RawBinary:    {percent(rawbinary_size, vde_size):.1f}% reduction")
        print(f"VDE vs RawBinary.gz: {percent(rawbinary_gz_size, vde_size):.1f}% reduction")
        print(f"VDE vs CSV:          {percent(csv_size, vde_size):.1f}% reduction")
        print(f"VDE vs CSV.gz:       {percent(csv_gz_size, vde_size):.1f}% reduction")
        print(f"VDE.gz vs RawBinary: {percent(rawbinary_size, vde_gz_size):.1f}% reduction")
        print(f"VDE.gz vs CSV.gz:    {percent(csv_gz_size, vde_gz_size):.1f}% reduction")


if __name__ == "__main__":
    run()