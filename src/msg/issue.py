from pymtl import *
from enum import Enum
from msg.decode import RegSpec
from config.general import *


class IssuePacket(BitStructDefinition):
    def __init__(s):
        s.imm = BitField(DECODED_IMM_LEN)
        s.inst = BitField(RV64Inst.bits)
        s.rs1 = BitField(XLEN)
        s.rs1_valid = BitField(1)
        s.rs2 = BitField(XLEN)
        s.rs2_valid = BitField(1)
        s.rd = BitField(REG_TAG_LEN)
        s.rd_valid = BitField(1)
