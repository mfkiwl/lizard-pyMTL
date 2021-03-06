#=========================================================================
# lwu
#=========================================================================

import random

from pymtl import *
from tests.context import lizard
from tests.core.inst_utils import *

#-------------------------------------------------------------------------
# gen_basic_test
#-------------------------------------------------------------------------


def gen_basic_test():
  return """
    csrr x1, mngr2proc < 0x00002000
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    lwu   x2, 0(x1)
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    csrw proc2mngr, x2 > 0x01020304

    .data
    .word 0x01020304
  """


#-------------------------------------------------------------------------
# gen_dest_dep_test
#-------------------------------------------------------------------------


def gen_dest_dep_test():
  return [
      gen_ld_dest_dep_test(5, "lwu", 0x2000, 0x00010203),
      gen_ld_dest_dep_test(4, "lwu", 0x2004, 0x04050607),
      gen_ld_dest_dep_test(3, "lwu", 0x2008, 0x08090a0b),
      gen_ld_dest_dep_test(2, "lwu", 0x200c, 0x0c0d0e0f),
      gen_ld_dest_dep_test(1, "lwu", 0x2010, 0x10111213),
      gen_ld_dest_dep_test(0, "lwu", 0x2014, 0x14151617),
      gen_word_data([
          0x00010203,
          0x04050607,
          0x08090a0b,
          0x0c0d0e0f,
          0x10111213,
          0x14151617,
      ])
  ]


#-------------------------------------------------------------------------
# gen_base_dep_test
#-------------------------------------------------------------------------


def gen_base_dep_test():
  return [
      gen_ld_base_dep_test(5, "lwu", 0x2000, 0x00010203),
      gen_ld_base_dep_test(4, "lwu", 0x2004, 0x04050607),
      gen_ld_base_dep_test(3, "lwu", 0x2008, 0x08090a0b),
      gen_ld_base_dep_test(2, "lwu", 0x200c, 0x0c0d0e0f),
      gen_ld_base_dep_test(1, "lwu", 0x2010, 0x10111213),
      gen_ld_base_dep_test(0, "lwu", 0x2014, 0x14151617),
      gen_word_data([
          0x00010203,
          0x04050607,
          0x08090a0b,
          0x0c0d0e0f,
          0x10111213,
          0x14151617,
      ])
  ]


#-------------------------------------------------------------------------
# gen_srcs_dest_test
#-------------------------------------------------------------------------


def gen_srcs_dest_test():
  return [
      gen_ld_base_eq_dest_test("lwu", 0x2000, 0x01020304),
      gen_word_data([0x01020304])
  ]


#-------------------------------------------------------------------------
# gen_value_test
#-------------------------------------------------------------------------


def gen_value_test():
  return [

      # Test positive offsets
      gen_ld_value_test("lwu", 0, 0x00002000, 0xdeadbeef),
      gen_ld_value_test("lwu", 4, 0x00002000, 0x00010203),
      gen_ld_value_test("lwu", 8, 0x00002000, 0x04050607),
      gen_ld_value_test("lwu", 12, 0x00002000, 0x08090a0b),
      gen_ld_value_test("lwu", 16, 0x00002000, 0x0c0d0e0f),
      gen_ld_value_test("lwu", 20, 0x00002000, 0xcafecafe),

      # Test negative offsets
      gen_ld_value_test("lwu", -20, 0x00002014, 0xdeadbeef),
      gen_ld_value_test("lwu", -16, 0x00002014, 0x00010203),
      gen_ld_value_test("lwu", -12, 0x00002014, 0x04050607),
      gen_ld_value_test("lwu", -8, 0x00002014, 0x08090a0b),
      gen_ld_value_test("lwu", -4, 0x00002014, 0x0c0d0e0f),
      gen_ld_value_test("lwu", 0, 0x00002014, 0xcafecafe),

      # Test positive offset with unaligned base
      gen_ld_value_test("lwu", 1, 0x00001fff, 0xdeadbeef),
      gen_ld_value_test("lwu", 5, 0x00001fff, 0x00010203),
      gen_ld_value_test("lwu", 9, 0x00001fff, 0x04050607),
      gen_ld_value_test("lwu", 13, 0x00001fff, 0x08090a0b),
      gen_ld_value_test("lwu", 17, 0x00001fff, 0x0c0d0e0f),
      gen_ld_value_test("lwu", 21, 0x00001fff, 0xcafecafe),

      # Test negative offset with unaligned base
      gen_ld_value_test("lwu", -21, 0x00002015, 0xdeadbeef),
      gen_ld_value_test("lwu", -17, 0x00002015, 0x00010203),
      gen_ld_value_test("lwu", -13, 0x00002015, 0x04050607),
      gen_ld_value_test("lwu", -9, 0x00002015, 0x08090a0b),
      gen_ld_value_test("lwu", -5, 0x00002015, 0x0c0d0e0f),
      gen_ld_value_test("lwu", -1, 0x00002015, 0xcafecafe),
      gen_word_data([
          0xdeadbeef,
          0x00010203,
          0x04050607,
          0x08090a0b,
          0x0c0d0e0f,
          0xcafecafe,
      ])
  ]


#-------------------------------------------------------------------------
# gen_random_test
#-------------------------------------------------------------------------


def gen_random_test():

  # Generate some random data

  data = []
  for i in xrange(128):
    data.append(random.randint(0, 0xffffffff))

  # Generate random accesses to this data

  asm_code = []
  for i in xrange(100):

    a = random.randint(0, 127)
    b = random.randint(0, 127)

    base = Bits(32, 0x2000 + (4 * b))
    offset = Bits(16, (4 * (a - b)))
    result = data[a]

    asm_code.append(gen_ld_value_test("lwu", offset.int(), base.uint(), result))

  # Add the data to the end of the assembly code

  asm_code.append(gen_word_data(data))
  return asm_code


# specific test
def gen_stall_add_test():
  return """
    csrr x1, mngr2proc < 0x00002000
    csrr x2, mngr2proc < 0x00002004
    lwu x6, 0(x1)
    lwu x7, 0(x2)
    add x8, x6, x7
    csrw proc2mngr, x8 > 0x00000009

    .data
    .word 0x00000004
    .word 0x00000005
  """


# specific test
# def gen_stall_mul_test():
#   return """
#     csrr x1, mngr2proc < 0x00002000
#     csrr x2, mngr2proc < 0x00002004
#     lwu x6, 0(x1)
#     lwu x7, 0(x2)
#     mul x8, x6, x7
#     csrw proc2mngr, x8 > 0x00000014
#
#     .data
#     .word 0x00000004
#     .word 0x00000005
#   """
