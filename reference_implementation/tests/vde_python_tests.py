import io
import unittest
import sys
from pathlib import Path
from vde_io import VdeIO, VdeFileHeader, VdeBlockHeader, VdeBlockTrailer, VdeBlock


class TestVdeIntegration(unittest.TestCase):
    def make_vde_file(self, *blocks: VdeBlock) -> io.BytesIO:
        f = io.BytesIO()

        VdeFileHeader(version_major=1, version_minor=0).write(f)

        for block in blocks:
            block.write(f)

        f.seek(0)
        return f

    def test_read_one_block(self):
        header = VdeBlockHeader(element_value=100,
                                step_value=1,
                                delta_size=1,
                                num_deltas=3)
        block = VdeBlock(header=header,
                         deltas=[2, 3, 4],
                         trailer=VdeBlockTrailer(element_value=109))

        f = self.make_vde_file(block)
        
        self.assertEqual(list(VdeIO.iter_values(f)), [100, 102, 105, 109])

    def test_read_one_block_with_step_value(self):
        header = VdeBlockHeader(element_value=100,
                                step_value=10,
                                delta_size=1,
                                num_deltas=3)
        block = VdeBlock(header=header,
                         deltas=[1, 2, 3],
                         trailer=VdeBlockTrailer(element_value=160))

        f = self.make_vde_file(block)
        
        self.assertEqual(list(VdeIO.iter_values(f)), [100, 110, 130, 160])

    def test_read_multiple_blocks(self):
        header_1 = VdeBlockHeader(element_value=10,
                                  step_value=1,
                                  delta_size=1,
                                  num_deltas=2)
        block_1 = VdeBlock(header=header_1,
                           deltas=[1, 2],
                           trailer=VdeBlockTrailer(element_value=13))

        header_2 = VdeBlockHeader(element_value=100,
                                  step_value=5,
                                  delta_size=1,
                                  num_deltas=2)
        block_2 = VdeBlock(header=header_2,
                           deltas=[1, 3],
                           trailer=VdeBlockTrailer(element_value=120))

        f = self.make_vde_file(block_1, block_2)
        
        self.assertEqual(list(VdeIO.iter_values(f)), [10, 11, 13, 100, 105, 120])
    
    def test_iter_values_range_query(self):
        header_1 = VdeBlockHeader(element_value=10,
                                step_value=1,
                                delta_size=1,
                                num_deltas=4)
        block_1 = VdeBlock(header=header_1,
                        deltas=[2, 3, 4, 5],
                        trailer=VdeBlockTrailer(element_value=24))

        header_2 = VdeBlockHeader(element_value=100,
                                step_value=10,
                                delta_size=1,
                                num_deltas=4)
        block_2 = VdeBlock(header=header_2,
                        deltas=[1, 2, 3, 4],
                        trailer=VdeBlockTrailer(element_value=200))

        f = self.make_vde_file(block_1, block_2)
        
        self.assertEqual(list(VdeIO.iter_values(f, min_value=15, max_value=160)),
                         [15, 19, 24, 100, 110, 130])
    
    def test_size_empty_vde_file(self):
        f = self.make_vde_file()

        self.assertEqual(VdeIO.size(f), 0)
    
    def test_size(self):
        header = VdeBlockHeader(element_value=300,
                                step_value=653,
                                delta_size=2,
                                num_deltas=7)
        block = VdeBlock(header=header,
                         deltas=[13, 21, 1, 7, 982, 7, 2],
                         trailer=VdeBlockTrailer(element_value=674_849))
        
        f = self.make_vde_file(block)
        
        self.assertEqual(VdeIO.size(f), header.num_deltas + 1)
    
    def test_min(self):
        deltas = [4, 19, 83, 2, 11, 506, 7, 31]

        header = VdeBlockHeader(element_value=1_742,
                                step_value=317,
                                delta_size=2,
                                num_deltas=len(deltas))
        
        block = VdeBlock(header=header,
                         deltas=deltas,
                         trailer=VdeBlockTrailer(element_value=211_913))
        
        f = self.make_vde_file(block)

        self.assertEqual(VdeIO.min(f), header.element_value)
    
    def test_max(self):
        deltas = [12, 5, 144, 3, 27, 890, 41, 6, 73]

        header = VdeBlockHeader(element_value=9_805,
                                step_value=211,
                                delta_size=2,
                                num_deltas=len(deltas))
        
        trailer = VdeBlockTrailer(element_value=263_216)

        block = VdeBlock(header=header,
                         deltas=deltas,
                         trailer=trailer)
        
        f = self.make_vde_file(block)

        self.assertEqual(VdeIO.max(f), trailer.element_value)
    
    def test_min_rejects_empty_vde_file(self):
        f = self.make_vde_file()

        with self.assertRaises(ValueError):
            VdeIO.min(f)

    def test_max_rejects_empty_vde_file(self):
        f = self.make_vde_file()

        with self.assertRaises(ValueError):
            VdeIO.max(f)
    
    def test_rejects_non_vde_file_header(self):
        f = io.BytesIO(b"This is just a normal text file\n")

        with self.assertRaises(ValueError):
            list(VdeIO.iter_values(f))

    def test_rejects_truncated_file_header_magic(self):
        f = io.BytesIO(b"VD")

        with self.assertRaises(ValueError):
            list(VdeIO.iter_values(f))

    def test_rejects_truncated_file_header_version(self):
        f = io.BytesIO(b"VDE\x00\x01")

        with self.assertRaises(EOFError):
            list(VdeIO.iter_values(f))

    def test_rejects_unsupported_version(self):
        f = io.BytesIO()
        VdeFileHeader(version_major=2, version_minor=0).write(f)
        f.seek(0)

        with self.assertRaises(ValueError):
            list(VdeIO.iter_values(f))
    
    def test_rejects_bad_trailer_value(self):
        header = VdeBlockHeader(element_value=100,
                                step_value=1,
                                delta_size=1,
                                num_deltas=3)
        block = VdeBlock(header=header,
                         deltas=[2, 3, 4],
                         trailer=VdeBlockTrailer(element_value=999))

        f = self.make_vde_file(block)

        with self.assertRaises(ValueError):
            list(VdeIO.iter_values(f))


if __name__ == "__main__":
    unittest.main()