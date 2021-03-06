from pymtl import *
from lizard.util.rtl.interface import Interface, UseInterface
from lizard.util.rtl.method import MethodSpec
from lizard.util.rtl.types import canonicalize_type
from lizard.util.rtl.case_mux import CaseMuxInterface, CaseMux


class LookupTableInterface(Interface):

  def __init__(s, in_type, out_type):
    s.In = canonicalize_type(in_type)
    s.Out = canonicalize_type(out_type)

    super(LookupTableInterface, s).__init__([
        MethodSpec(
            'lookup',
            args={
                'in_': s.In,
            },
            rets={
                'out': s.Out,
                'valid': Bits(1),
            },
            call=False,
            rdy=False,
        ),
    ])


class LookupTable(Model):

  def __init__(s, interface, mapping):
    UseInterface(s, interface)

    size = len(mapping)
    # Sort by key to ensure it is deterministic
    svalues, souts = zip(*[(key, mapping[key])
                           for key in sorted(mapping.keys())])
    s.mux = CaseMux(
        CaseMuxInterface(s.interface.Out, s.interface.In, size), svalues)
    s.connect(s.mux.mux_default, 0)
    s.connect(s.mux.mux_select, s.lookup_in_)
    for i, sout in enumerate(souts):
      s.connect(s.mux.mux_in_[i], int(sout))
    s.connect(s.lookup_out, s.mux.mux_out)
    s.connect(s.lookup_valid, s.mux.mux_matched)

  def line_trace(s):
    return "{} ->({}) {}".format(s.lookup_in_, s.lookup_valid, s.lookup_out)
