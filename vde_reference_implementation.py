'''
Date: 2026-03-04
Author: Sebastien Mouton

VDE file format: Variable Delta Encoding
VDE is a file format designed for efficiently storing and range-querying
    long sequences of large, non-negative, monotonically non-decreasing integers.

This is a reference implementation,
    i.e. this is unoptimized code targeting correctness and simplicity.
'''

import math
import struct
from dataclasses import dataclass
from functools import reduce
from itertools import islice
from typing import ClassVar, Iterator, Iterable, Self, BinaryIO


ENDIANNESS = 'little'

class VdeIO:
    '''
    Read, write and manipulate Variable Delta Encoding file format (vde)

    VDE is a file format designed for efficiently storing and range-querying
        long sequences of large, non-negative, monotonically non-decreasing integers.
    '''
    def __init__(self):
        pass
    
    @classmethod
    def write(cls, ints: Iterable[int], f: BinaryIO, block_size=10_000):
        file_header = VdeFileHeader(version_major=1, version_minor=0)
        file_header.write(f)

        it = iter(ints)
        
        while True:
            block_elements = list(islice(it, block_size))
            if len(block_elements) == 0:
                break
            block = VdeBlock.generate(block_elements)
            block.write(f)
    
    @classmethod
    def iter_values(cls, f : BinaryIO, min_value=None, max_value=None) -> Iterator[int]:
        '''
        iterate over all the values between min_value (included) and max_value (excluded)
        '''
        file_header = VdeFileHeader.read(f)
        if not( file_header.version_major == 1 and file_header.version_minor == 0):
            raise ValueError(f'Unsupported VDE version: {file_header.version_major}.{file_header.version_minor}')
        
        while True:
            block = VdeBlock.read(f)
            if block is None:
                break

            if max_value is not None and block.header.element_value >= max_value:
                break

            yield from block.iter_values(min_value, max_value)

            if max_value is not None and block.trailer.element_value >= max_value:
                break
                    

@dataclass
class VdeBlockHeader:
    element_value: int
    step_value: int
    delta_size: int
    num_deltas: int

    prefix: ClassVar[bytes] = b'VDE\x01'

    def write(self, f: BinaryIO):
        f.write(self.prefix)
        f.write(uvarint_encode(self.element_value))
        f.write(uvarint_encode(self.step_value))
        f.write(uvarint_encode(self.delta_size))
        f.write(uvarint_encode(self.num_deltas))
    
    @classmethod
    def read(cls, f: BinaryIO) -> Self | None:
        '''
        returns None at clean EOF
        '''
        prefix = f.read(len(cls.prefix))

        if prefix == b'':
            return None
        
        if len(prefix) < len(cls.prefix):
            raise EOFError("Unexpected EOF while reading VDE block prefix")

        if prefix != cls.prefix:
            raise ValueError("Not a VDE block header")

        element_value = uvarint_read(f)
        step_value = uvarint_read(f)
        delta_size = uvarint_read(f)
        num_deltas = uvarint_read(f)

        return cls(element_value=element_value,
                   step_value=step_value,
                   delta_size=delta_size,
                   num_deltas=num_deltas)


@dataclass
class VdeBlockTrailer:
    element_value: int

    def write(self, f: BinaryIO):
        f.write(uvarint_encode(self.element_value))
    
    @classmethod
    def read(cls, f: BinaryIO) -> Self:
        element_value = uvarint_read(f)
        return cls(element_value=element_value)

@dataclass
class VdeBlock:
    header: VdeBlockHeader
    deltas: list[int]
    trailer: VdeBlockTrailer

    def write(self, f: BinaryIO):
        self.header.write(f)
        for d in self.deltas:
            f.write(d.to_bytes(self.header.delta_size, byteorder=ENDIANNESS))
        self.trailer.write(f)

    @classmethod
    def read(cls, f: BinaryIO) -> Self | None:
        header = VdeBlockHeader.read(f)

        if header is None:
            return None
        
        if header.delta_size <= 0:
            raise ValueError("Invalid VDE delta_size")

        num_delta_bytes = header.num_deltas * header.delta_size
        raw = f.read(num_delta_bytes)

        if len(raw) != num_delta_bytes:
            raise EOFError("Unexpected EOF while reading deltas")

        deltas = cls.decode_deltas(raw, delta_size=header.delta_size)

        trailer = VdeBlockTrailer.read(f)

        return cls(header=header, deltas=deltas, trailer=trailer)
    
    @classmethod
    def decode_deltas(cls, data: bytes, delta_size: int) -> list[int]:
        if delta_size == 1:
            return list(data)

        if delta_size == 2:
            fmt = "<H"
        elif delta_size == 4:
            fmt = "<I"
        elif delta_size == 8:
            fmt = "<Q"
        else:
            return [int.from_bytes(data[i:i + delta_size], byteorder=ENDIANNESS)
                for i in range(0, len(data), delta_size)]

        return [x[0] for x in struct.iter_unpack(fmt, data)]
    
    def iter_values(self, min_value=None, max_value=None) -> Iterator[int]:
        '''
        Iterate over all the values of the block
            between min_value (included) and max_value (excluded)
        
        Perform a consistency check when the iterator is fully consumed
        '''
        element_value = self.header.element_value
        if max_value is not None and element_value >= max_value:
            return
        
        if min_value is not None and self.trailer.element_value < min_value:
            return
        
        if min_value is None or min_value <= element_value:
            yield element_value

        for delta in self.deltas:
            element_value += delta * self.header.step_value
            if max_value is not None and element_value >= max_value:
                return
            if min_value is None or min_value <= element_value:
                yield element_value
        
        if element_value != self.trailer.element_value:
            raise ValueError(f"Error in block: {element_value} != {self.trailer.element_value}")
    
    @classmethod
    def generate(cls, ints: list[int]) -> Self:
        if len(ints) == 0:
            raise ValueError("Cannot generate a VDE block from an empty list")
        if len(ints) == 1:
            step_value = 1
            deltas = []
            delta_size = 1
        else:
            diffs = [ints[i+1] - ints[i] for i in range(len(ints)-1)]
            if any(d < 0 for d in diffs):
                raise ValueError("VDE is a file format for monotonically non-decreasing integers")
            step_value = max(1, reduce(math.gcd, diffs))
            deltas = [d // step_value for d in diffs]
            delta_size = max(1, (max(deltas).bit_length() + 7) // 8)

        header = VdeBlockHeader(element_value=ints[0],
                                step_value=step_value,
                                delta_size=delta_size,
                                num_deltas=len(deltas))
        trailer = VdeBlockTrailer(element_value=ints[-1])

        return cls(header=header, deltas=deltas, trailer=trailer)
    

@dataclass
class VdeFileHeader:
    version_major: int
    version_minor: int
    magic_bytes: ClassVar[bytes] = b'VDE\x00'
    version_size: ClassVar[int] = 2

    def write(self, f: BinaryIO):
        f.write(self.magic_bytes)
        f.write(self.version_major.to_bytes(self.version_size, byteorder=ENDIANNESS))
        f.write(self.version_minor.to_bytes(self.version_size, byteorder=ENDIANNESS))

    @classmethod
    def read(cls, f: BinaryIO) -> Self:
        magic_bytes = f.read(len(cls.magic_bytes))
        if magic_bytes != cls.magic_bytes:
            raise ValueError('This is not a VDE file')
        raw_major = f.read(cls.version_size)
        raw_minor = f.read(cls.version_size)

        if not (len(raw_major) == len(raw_minor) == cls.version_size):
            raise EOFError("Unexpected EOF while reading VDE file header")

        version_major = int.from_bytes(raw_major, byteorder=ENDIANNESS)
        version_minor = int.from_bytes(raw_minor, byteorder=ENDIANNESS)
    
        return cls(version_major=version_major, version_minor=version_minor)
    

def uvarint_encode(value: int) -> bytes:
    if value < 0:
        raise ValueError("uvarint cannot encode negative values")

    res = bytearray()

    while True:
        byte = value & 0x7F
        value >>= 7

        if value:
            res.append(byte | 0x80)
        else:
            res.append(byte)
            break

    return bytes(res)


def uvarint_read(f: BinaryIO) -> int:
    result = 0
    shift = 0

    while True:
        raw = f.read(1)

        if raw == b"":
            raise EOFError("Unexpected end of file while reading varint")

        byte = raw[0]

        result |= (byte & 0x7F) << shift

        if byte & 0x80 == 0:
            return result

        shift += 7
