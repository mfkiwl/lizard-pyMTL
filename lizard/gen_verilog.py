#! /usr/bin/env python2
from util import pythonpath
from pymtl import *
from model.translate import translate
from mem.rtl.memory_bus import MemoryBusInterface
from core.rtl.proc import ProcInterface, Proc
import subprocess


def gen_verilog():
  mbi = MemoryBusInterface(2, 1, 2, 64, 8)
  proc = Proc(ProcInterface(), mbi.MemMsg)
  proc.explicit_modulename = 'proc'
  translate(proc)
  fname = '{}.v'.format(proc.class_name)
  svfname = '{}.sv'.format(proc.class_name)
  subprocess.check_call(['sed', '-i', 's/\\bwire\\b/logic/g', fname])
  subprocess.check_call(['sed', '-i', 's/\\breg\\b/logic/g', fname])
  subprocess.check_call(['sed', '-i', '/^`default_nettype/ d', fname])
  subprocess.check_call(['mv', fname, svfname])


if __name__ == '__main__':
  gen_verilog()
