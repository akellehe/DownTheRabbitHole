"""
This module writes a matrix of numbers of int and long types to a file in binary 
format. It mmaps that file, and allows efficient alters-in-place through the api.

"""

import mmap
import struct
import os


def format_to_size(fmt):
    if fmt == 'i':
        return 4
    elif fmt == 'l':
        return 8


def get_column_offset(col_index, row_format):
    offset = 0
    for idx, fmt in enumerate(row_format):
        if idx == col_index:
            return offset
        offset += format_to_size(fmt)


def get_row_length(row_format):
    return sum([format_to_size(fmt) for fmt in row_format])


def pack_row(row, row_format):
	packed = []
	for fmt, value in zip(row_format, row):
		packed.append(struct.pack(fmt, value))
	return "".join(packed)


def unpack_row(row, row_format):
    unpacked = []
    for idx, fmt in enumerate(row_format):
        offset = get_column_offset(idx, row_format)
        size = format_to_size(fmt)
        unpacked.append(struct.unpack(fmt, 
            row[offset:offset+size])[0])
    return unpacked


def write_block(blk, row_format):
    with open(FILENAME, 'w+') as fp:
		for row in blk:
			fp.write(pack_row(row, row_format))


def file_to_block(filename, row_format):
    packed, idx, row_length = [], 0, get_row_length(row_format)
    with open(filename, 'r+') as fp:
        mapped = mmap.mmap(fp.fileno(), 0)
        while True:
            row = mapped[idx*row_length:(idx+1)*row_length]
            if not row: break
            yield unpack_row(row, row_format)
            idx += 1


def print_file(filename, row_format):
    packed, idx, row_length = [], 0, get_row_length(row_format)
    with open(filename, 'r+') as fp:
        mapped = mmap.mmap(fp.fileno(), 0)
        while True:
            row = mapped[idx*row_length:(idx+1)*row_length]
            if not row: break
            print(unpack_row(row, row_format))
            idx += 1
        

def batch_increment_column(filename, row_format, column_id, incrby):
    idx = 0
    row_length = get_row_length(row_format)
    col_offset = get_column_offset(column_id, row_format)
    col_size = format_to_size(row_format[column_id])
    with open(filename, 'r+') as fp:
        mapped = mmap.mmap(fp.fileno(), 0)
        while True:
            row = mapped[idx*row_length:(idx+1)*row_length]
            if not row: break
            updated = unpack_row(row, row_format)[column_id] + incrby
            start = idx*row_length + col_offset
            stop = start + col_size
            idx += 1
            mapped[start:stop] = struct.pack('i', updated)
        mapped.flush()
        os.fsync(fp.fileno())


if __name__ == '__main__':
    ROW_FORMAT = 'liili'
    BIGINT, INT = 8, 4
    FILENAME = 'myfile.dat'


    block = [
        [10e12,  55, 74,   1234,  45376],
        [2.1e14, 62, 2462, 5678,  324],
        [4.3e10, 12, 24,   91011, 2346],
        [8e15,   15, 768,  12131, 23]
    ]

    write_block(block, ROW_FORMAT)
    print_file(FILENAME, ROW_FORMAT)
    batch_increment_column(FILENAME, ROW_FORMAT, 1, 2)

