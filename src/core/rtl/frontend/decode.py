from pymtl import *
from util.rtl.interface import Interface, IncludeSome, UseInterface
from util.rtl.method import MethodSpec
from util.rtl.types import Array, canonicalize_type
from core.rtl.controlflow import ControlFlowManagerInterface
from bitutil import clog2, clog2nz
from pclib.rtl import RegEn, RegEnRst, RegRst
from core.rtl.frontend.fetch import FetchInterface
from core.rtl.messages import FetchMsg, DecodeMsg, PipelineMsg
from msg.codes import RVInstMask, Opcode, ExceptionCode


class DecodeInterface(Interface):

  def __init__(s):
    super(DecodeInterface, s).__init__(
        [
            MethodSpec(
                'get',
                args={},
                rets={
                    'msg': DecodeMsg(),
                },
                call=True,
                rdy=True,
            ),
        ],
        ordering_chains=[
            [],
        ],
    )


class Decode(Model):

  def __init__(s, xlen, ilen, areg_tag_nbits, imm_len):
    UseInterface(s, DecodeInterface())

    s.fetch = FetchInterface(ilen)
    s.fetch.require(s, 'fetch', 'get')

    # Outgoing pipeline register
    s.decmsg_val_ = RegRst(Bits(1), reset_value=0)
    s.decmsg_ = Wire(DecodeMsg())

    s.dec_ = Wire(DecodeMsg())
    s.rdy_ = Wire(1)
    s.accepted_ = Wire(1)
    s.msg_ = Wire(FetchMsg())
    s.inst_ = Wire(Bits(ilen))

    # TODO: remove this once this connects to the next stage
    s.connect(s.get_call, s.get_rdy)
    s.connect_wire(s.inst_, s.msg_.inst)

    s.opcode_ = Wire(s.inst_[RVInstMask.OPCODE].nbits)
    s.connect_wire(s.opcode_, s.inst_[RVInstMask.OPCODE])
    s.func3_ = Wire(s.inst_[RVInstMask.FUNCT3].nbits)
    s.connect_wire(s.func3_, s.inst_[RVInstMask.FUNCT3])
    s.func7_ = Wire(s.inst_[RVInstMask.FUNCT7].nbits)
    s.connect_wire(s.func7_, s.inst_[RVInstMask.FUNCT7])

    s.connect(s.msg_, s.fetch_get_msg)
    s.connect(s.get_rdy, s.decmsg_val_.out)
    s.connect(s.fetch_get_call, s.accepted_)

    # All the IMMs
    s.imm_i_ = Wire(imm_len)
    s.imm_s_ = Wire(imm_len)
    s.imm_b_ = Wire(imm_len)
    s.imm_u_ = Wire(imm_len)
    s.imm_j_ = Wire(imm_len)
    @s.combinational
    def handle_imm():
      s.imm_i_.v = sext(s.inst_[RVInstMask.I_IMM], imm_len)
      s.imm_s_.v = sext(concat(s.inst_[RVInstMask.S_IMM1], s.inst_[RVInstMask.S_IMM0]), imm_len)
      s.imm_b_.v = sext(concat(s.inst_[RVInstMask.B_IMM3], s.inst_[RVInstMask.B_IMM2], s.inst_[RVInstMask.B_IMM1], s.inst_[RVInstMask.B_IMM0]) << 1, imm_len)
      s.imm_u_.v = sext(s.inst_[RVInstMask.U_IMM], imm_len)
      s.imm_j_.v = sext(concat(s.inst_[RVInstMask.J_IMM3], s.inst_[RVInstMask.J_IMM2], s.inst_[RVInstMask.J_IMM1], s.inst_[RVInstMask.J_IMM0]) << 1, imm_len)

    @s.combinational
    def handle_flags():
      # Ready when pipeline register is invalid or being read from this cycle
      s.rdy_.v = not s.decmsg_val_.out or s.get_call
      s.accepted_.v = s.rdy_ and s.fetch_get_rdy

    @s.combinational
    def set_valreg():
      s.decmsg_val_.in_.v = s.accepted_ or (s.decmsg_val_.out and
                                              not s.get_call)

    @s.combinational
    def decode():
      s.dec_.rs1.v = s.msg_.inst[RVInstMask.RS1]
      s.dec_.rs2.v = s.msg_.inst[RVInstMask.RS2]
      s.dec_.rd.v = s.msg_.inst[RVInstMask.RD]
      s.dec_.rs1_val.v = 0
      s.dec_.rs2_val.v = 0
      s.dec_.rd_val.v = 0
      s.dec_.imm_val.v = 0
      s.dec_.op_32.v = 0
      s.dec_.trap.v = 0
      if s.msg_.trap != 0:
        s.dec_.trap.v = s.msg_.trap
        s.dec_.mcause.v = s.msg_.mcause
        s.dec_.mtval.v = s.msg_.mtval
      if s.opcode_ == Opcode.LOAD:
        s.dec_.rs1_val.v = 1
        s.dec_.rd_val.v = 1
        s.dec_.imm_val.v = 1
        # I-type imm
        s.dec_.imm.v = s.imm_i_
#     elif s.opcode_ == Opcode.LOAD_FP:
      elif s.opcode_ == Opcode.MISC_MEM:
        s.dec_.rs1_val.v = 1
        s.dec_.rd_val.v = 1
        s.dec_.imm_val.v = 1
        # I-type imm
        s.dec_.imm.v = s.imm_i_
      elif s.opcode_ == Opcode.OP_IMM:
        s.dec_.rs1_val.v = 1
        s.dec_.rd_val.v = 1
        s.dec_.imm_val.v = 1
        # I-type imm
        s.dec_.imm.v = s.imm_i_
      elif s.opcode_ == Opcode.AUIPC:
        s.dec_.rd_val.v = 1
        # U-type imm
        s.dec_.imm.v = s.imm_u_
      elif s.opcode_ == Opcode.OP_IMM_32:
        s.dec_.op_32 = 1
      elif s.opcode_ == Opcode.STORE:
        s.dec_.rs1_val.v = 1
        s.dec_.rs2_val.v = 1
        s.dec_.imm_val.v = 1
        # S-type imm
        s.dec_.imm.v = s.imm_s_
#     elif s.opcode_ == Opcode.STORE_FP:
      elif s.opcode_ == Opcode.AMO:
        s.dec_.rs1_val.v = 1
        s.dec_.rs2_val.v = 1
        s.dec_.rd_val.v = 1
      elif s.opcode_ == Opcode.OP:
        s.dec_.rs1_val.v = 1
        s.dec_.rs2_val.v = 1
        s.dec_.rd_val.v = 1
      elif s.opcode_ == Opcode.LUI:
        s.dec_.rd_val.v = 1
        # U-type imm
        s.dec_.imm.v = s.imm_u_
      elif s.opcode_ == Opcode.OP_32:
        s.dec_.rs1_val.v = 1
        s.dec_.rs2_val.v = 1
        s.dec_.rd_val.v = 1
        s.dec_.op_32 = 1
#     elif s.opcode_ == Opcode.MADD:
#     elif s.opcode_ == Opcode.MSUB:
#     elif s.opcode_ == Opcode.NMSUB:
#     elif s.opcode_ == Opcode.NMADD:
#     elif s.opcode_ == Opcode.OP_FP:
      elif s.opcode_ == Opcode.BRANCH:
        s.dec_.rs1_val.v = 1
        s.dec_.rs2_val.v = 1
        s.dec_.imm_val.v = 1
        # B-type imm
        s.dec_.imm.v = s.imm_b_
      elif s.opcode_ == Opcode.JALR:
        s.dec_.rs1_val.v = 1
        s.dec_.rd_val.v = 1
        s.dec_.imm_val.v = 1
        # J-type imm
        s.dec_.imm.v = s.imm_j_
      elif s.opcode_ == Opcode.JAL:
        s.dec_.rd_val.v = 1
        s.dec_.imm_val.v = 1
        # J-type imm
        s.dec_.imm.v = s.imm_j_
      elif s.opcode_ == Opcode.SYSTEM:
        s.dec_.rs1_val.v = 1
        s.dec_.rd_val.v = 1
        s.dec_.imm_val.v = 1
        # I-type imm
        s.dec_.imm.v = s.imm_i_
      else:  # Error decoding
        s.dec_.trap.v = 1
        s.dec_.mcause.v = ExceptionCode.ILLEGAL_INSTRUCTION
        s.dec_.mtval.v = zext(s.inst_, xlen)

    @s.tick_rtl
    def update_out():
      if s.accepted_:
        s.decmsg_.n = s.dec_

  def line_trace(s):
    return str(s.decmsg_)