from lizard.msg.data import *
from lizard.msg.codes import *

from lizard.util.rtl.interface import Interface, IncludeSome, UseInterface
from lizard.util.rtl.method import MethodSpec
from lizard.util.rtl.mux import Mux
from lizard.util.rtl.types import Array
from lizard.util.rtl.packers import Packer
from lizard.util.rtl.snapshotting_freelist import SnapshottingFreeList
from lizard.util.rtl.registerfile import RegisterFile
from lizard.util.rtl.async_ram import AsynchronousRAM, AsynchronousRAMInterface
from lizard.core.rtl.renametable import RenameTableInterface, RenameTable
from lizard.bitutil import clog2nz


class DataFlowManagerInterface(Interface):

  def __init__(s, dlen, naregs, npregs, nsnapshots, nstore_queue, num_src_ports,
               num_dst_ports, num_is_ready_ports, num_forward_ports):
    s.DataLen = dlen
    s.NumAregs = naregs
    s.NumPregs = npregs
    s.NumSnapshots = nsnapshots
    s.NumStoreQueue = nstore_queue
    s.StoreQueueIdxNbits = clog2nz(nstore_queue)
    s.NumSrcPorts = num_src_ports
    s.NumDstPorts = num_dst_ports
    s.NumIsReadyPorts = num_is_ready_ports
    s.NumForwardPorts = num_forward_ports
    rename_table_interface = RenameTableInterface(naregs, npregs, 0, 0,
                                                  nsnapshots)

    s.Areg = rename_table_interface.Areg
    s.Preg = rename_table_interface.Preg
    s.SnapshotId = rename_table_interface.SnapshotId

    super(DataFlowManagerInterface, s).__init__(
        [
            MethodSpec(
                'get_src',
                args={
                    'areg': s.Areg,
                },
                rets={
                    'preg': s.Preg,
                },
                call=False,
                rdy=False,
                count=num_src_ports,
            ),
            MethodSpec(
                'get_dst',
                args={
                    'areg': s.Areg,
                },
                rets={
                    'preg': s.Preg,
                },
                call=True,
                rdy=True,
                count=num_dst_ports,
            ),
            MethodSpec(
                'valid_store_mask',
                args=None,
                rets={
                    'mask': s.NumStoreQueue,
                },
                call=False,
                rdy=False,
            ),
            MethodSpec(
                'get_store_id',
                args=None,
                rets={
                    'store_id': s.StoreQueueIdxNbits,
                },
                call=True,
                rdy=True,
                count=num_dst_ports,
            ),
            MethodSpec(
                'is_ready',
                args={
                    'tag': s.Preg,
                },
                rets={
                    'ready': Bits(1),
                },
                call=False,
                rdy=False,
                count=num_is_ready_ports,
            ),
            MethodSpec(
                'read',
                args={
                    'tag': s.Preg,
                },
                rets={
                    'value': Bits(dlen),
                },
                call=False,
                rdy=False,
                count=num_is_ready_ports,
            ),
            MethodSpec(
                'write',
                args={
                    'tag': s.Preg,
                    'value': Bits(dlen),
                },
                rets=None,
                call=True,
                rdy=False,
                count=num_dst_ports,
            ),
            MethodSpec(
                'forward',
                args={
                    'tag': s.Preg,
                    'value': Bits(dlen),
                },
                rets=None,
                call=True,
                rdy=False,
                count=num_forward_ports,
            ),
            MethodSpec(
                'reset_cl_forwarded',
                args=None,
                rets=None,
                call=False,
                rdy=False,
            ),
            MethodSpec(
                'get_updated',
                args=None,
                rets={
                    'tags': Array(s.Preg, num_dst_ports + num_forward_ports),
                    'valid': Array(Bits(1), num_dst_ports + num_forward_ports),
                },
                call=False,
                rdy=False,
            ),
            MethodSpec(
                'free_store_id',
                args={
                    'id_': s.StoreQueueIdxNbits,
                },
                rets=None,
                call=True,
                rdy=False,
                count=num_dst_ports,
            ),
            MethodSpec(
                'commit',
                args={
                    'tag': s.Preg,
                    'areg': s.Areg,
                },
                rets=None,
                call=True,
                rdy=False,
                count=num_dst_ports,
            ),
            MethodSpec(
                'rollback',
                args=None,
                rets=None,
                call=True,
                rdy=False,
            ),
            MethodSpec(
                'snapshot',
                args=None,
                rets={
                    'id_': s.SnapshotId,
                },
                call=True,
                rdy=True,
            ),
            MethodSpec(
                'free_snapshot',
                args={
                    'id_': s.SnapshotId,
                },
                rets=None,
                call=True,
                rdy=False,
            ),
        ],
        bases=[
            IncludeSome(rename_table_interface, {'restore'}),
        ],
        ordering_chains=[
            [
                'is_ready', 'write', 'forward', 'get_updated', 'get_src',
                'get_dst', 'valid_store_mask', 'get_store_id', 'free_store_id',
                'commit', 'read', 'reset_cl_forwarded', 'snapshot',
                'free_snapshot', 'restore', 'rollback'
            ],
        ],
    )


class DataFlowManager(Model):

  def __init__(s, dflow_interface):
    UseInterface(s, dflow_interface)
    dlen = s.interface.DataLen
    naregs = s.interface.NumAregs
    npregs = s.interface.NumPregs
    nsnapshots = s.interface.NumSnapshots
    nstore_queue = s.interface.NumStoreQueue
    num_src_ports = s.interface.NumSrcPorts
    num_dst_ports = s.interface.NumDstPorts
    num_is_ready_ports = s.interface.NumIsReadyPorts
    num_forward_ports = s.interface.NumForwardPorts

    # used to allocate snapshot IDs
    s.snapshot_allocator = SnapshottingFreeList(nsnapshots, 1, 1, nsnapshots)

    # Reserve the highest tag for x0
    # Free list with 1 alloc ports, 1 free port, and AREG_COUNT - 1 used slots
    # initially
    s.free_regs = SnapshottingFreeList(
        npregs - 1,
        num_dst_ports,
        num_dst_ports,
        nsnapshots,
        used_slots_initial=naregs - 1)
    s.store_ids = SnapshottingFreeList(nstore_queue, num_dst_ports,
                                       num_dst_ports, nsnapshots)
    # arch_used_pregs tracks the physical registers used by the current architectural state
    # arch_used_pregs[i] is 1 if preg i is used by the arf, and 0 otherwise
    # on reset, the ARF is backed by pregs [0, naregs - 1]
    arch_used_pregs_reset = [Bits(1, 0) for _ in range(npregs - 1)]
    for i in range(naregs):
      arch_used_pregs_reset[i] = Bits(1, 1)

    s.arch_used_pregs = RegisterFile(
        Bits(1),
        npregs - 1,
        0,  # no read ports needed, only a dump port
        num_dst_ports *
        2,  # have to write twice for every instruction that commits
        False,  # no read ports, so we don't need a write-read bypass
        True,  # use a write-dump bypass to reset after commit
        reset_values=arch_used_pregs_reset)
    # Zero out the set
    s.connect(s.arch_used_pregs.set_call, 0)
    for i in range(npregs - 1):
      s.connect(s.arch_used_pregs.set_in_[i], 0)

    # Build the initial rename table.
    # x0 -> don't care (will use 0)
    # xn -> n-1
    initial_map = [0] + [x for x in range(naregs - 1)]
    s.rename_table = RenameTable(naregs, npregs, num_src_ports, num_dst_ports,
                                 nsnapshots, True, initial_map)
    s.ZERO_TAG = s.rename_table.ZERO_TAG

    # The physical register file, which stores the values
    # and ready states
    # Number of read ports is the same as number of source ports
    # Number of write ports is the same as number of dest ports
    # Writes are bypassed before reads, and the dump/set is not used
    s.preg_file = AsynchronousRAM(
        AsynchronousRAMInterface(
            Bits(dlen),
            npregs,
            num_is_ready_ports,
            num_dst_ports,
            True,
        ),
        reset_values=0,
    )
    # 2 write ports are needed for every dst port:
    # The second set to update all the destination states during issue,
    # (get_dst), and the first set to write the computed value
    # (write)
    # We give write the first set since it is sequenced before get_dst
    # In practice, there should be no conflicts (or the processor is doing
    # something dumb). But, we must adhere to the interface even if the
    # user does something dumb and tries to write to a bogus tag which
    # is currently free.
    # The ready table is not bypassed; is_ready comes before all the the writes
    # (which are in get_dst and write)
    s.ready_table = AsynchronousRAM(
        AsynchronousRAMInterface(
            Bits(1),
            npregs,
            num_is_ready_ports,
            num_dst_ports * 2,
            False,
        ),
        reset_values=1,
    )
    # The arhitectural areg -> preg mapping
    # Written and read only in commit
    # No write-read bypass
    # Yes write_dump bypass to allow restores to state after commits
    s.areg_file = RegisterFile(
        s.interface.Preg,
        naregs,
        num_dst_ports,
        num_dst_ports,
        False,
        True,
        reset_values=initial_map,
    )
    # Zero out the set
    s.connect(s.areg_file.set_call, 0)
    for i in range(naregs):
      s.connect(s.areg_file.set_in_[i], 0)

    # commit
    @s.combinational
    def compute_valid_store_mask():
      s.valid_store_mask_mask.v = ~s.store_ids.get_state_state

    s.is_commit_not_zero_tag = [Wire(1) for _ in range(num_dst_ports)]
    for i in range(num_dst_ports):
      # Determine if the commit is not the zero tag
      @s.combinational
      def check_commit(i=i):
        s.is_commit_not_zero_tag[i].v = (s.commit_tag[i] !=
                                         s.ZERO_TAG) and s.commit_call[i]

      # Read the preg currently associated with this areg
      s.connect(s.areg_file.read_addr[i], s.commit_areg[i])
      # Free the preg currently backing this areg
      s.connect(s.free_regs.free_index[i], s.areg_file.read_data[i])
      # Only free if not the zero tag
      s.connect(s.free_regs.free_call[i], s.is_commit_not_zero_tag[i])
      # Free the store ID from the committing instruction
      s.connect(s.store_ids.free_index[i], s.free_store_id_id_[i])
      # Only free if the commit is valid
      s.connect(s.store_ids.free_call[i], s.free_store_id_call[i])

      # Write into the ARF the new preg
      s.connect(s.areg_file.write_addr[i], s.commit_areg[i])
      s.connect(s.areg_file.write_data[i], s.commit_tag[i])
      # Only write if not the zero tag
      s.connect(s.areg_file.write_call[i], s.is_commit_not_zero_tag[i])

      # Mark the old preg used by the ARF as free
      s.connect(s.arch_used_pregs.write_addr[i], s.areg_file.read_data[i])
      s.connect(s.arch_used_pregs.write_data[i], 0)
      s.connect(s.arch_used_pregs.write_call[i], s.is_commit_not_zero_tag[i])
      # Mark the new preg used by the ARF as used
      s.connect(s.arch_used_pregs.write_addr[i + num_dst_ports],
                s.commit_tag[i])
      s.connect(s.arch_used_pregs.write_data[i + num_dst_ports], 1)
      s.connect(s.arch_used_pregs.write_call[i + num_dst_ports],
                s.is_commit_not_zero_tag[i])

    # write
    s.is_write_not_zero_tag = [Wire(1) for _ in range(num_dst_ports)]
    for i in range(num_dst_ports):
      # Determine if the write is not the zero tag
      @s.combinational
      def check_write(i=i):
        s.is_write_not_zero_tag[i].v = (s.write_tag[i] !=
                                        s.ZERO_TAG) and s.write_call[i]

      # All operations on the preg file are on the first set of write ports
      # at the offset 0
      # Write the value and ready into the preg file
      s.connect(s.preg_file.write_addr[i], s.write_tag[i])
      s.connect(s.preg_file.write_data[i], s.write_value[i])
      # Only write if not the zero tag
      s.connect(s.preg_file.write_call[i], s.is_write_not_zero_tag[i])

      s.connect(s.ready_table.write_addr[i], s.write_tag[i])
      s.connect(s.ready_table.write_data[i], 1)
      # Only write if not the zero tag
      s.connect(s.ready_table.write_call[i], s.is_write_not_zero_tag[i])

    # get_updated
    s.is_forward_not_zero_tag = [Wire(1) for _ in range(num_forward_ports)]
    for i in range(num_forward_ports):

      @s.combinational
      def check_forward(i=i):
        s.is_forward_not_zero_tag[i].v = (s.forward_tag[i] !=
                                          s.ZERO_TAG) and s.forward_call[i]

    # Unify the write and forward ports
    # Note that forward occurs after write
    for i in range(num_dst_ports):
      s.connect(s.get_updated_valid[i], s.is_write_not_zero_tag[i])
      s.connect(s.get_updated_tags[i], s.write_tag[i])
    for i in range(num_forward_ports):
      s.connect(s.get_updated_valid[num_dst_ports + i],
                s.is_forward_not_zero_tag[i])
      s.connect(s.get_updated_tags[num_dst_ports + i], s.forward_tag[i])

    # get_src
    s.connect_m(s.get_src, s.rename_table.lookup)

    # get_dst
    s.get_dst_need_writeback = [Wire(1) for _ in range(num_dst_ports)]
    for i in range(num_dst_ports):
      s.connect(s.get_dst_rdy[i], s.free_regs.alloc_rdy[i])
      s.connect(s.get_store_id_rdy[i], s.store_ids.alloc_rdy[i])
      s.connect(s.store_ids.alloc_call[i], s.get_store_id_call[i])
      s.connect(s.get_store_id_store_id[i], s.store_ids.alloc_index[i])

      @s.combinational
      def handle_get_dst_allocate(i=i):
        if s.get_dst_areg[i] == 0:
          # zero register
          s.free_regs.alloc_call[i].v = 0
          s.get_dst_preg[i].v = s.ZERO_TAG
          s.get_dst_need_writeback[i].v = 0
        elif s.free_regs.alloc_rdy[i]:
          # allocate a register from the freelist
          s.free_regs.alloc_call[i].v = s.get_dst_call[i]
          s.get_dst_preg[i].v = s.free_regs.alloc_index[i]
          s.get_dst_need_writeback[i].v = s.get_dst_call[i]
        else:
          # free list is full
          s.free_regs.alloc_call[i].v = 0
          s.get_dst_preg[i].v = s.ZERO_TAG
          s.get_dst_need_writeback[i].v = 0

      # Update the rename table
      s.connect(s.rename_table.update_areg[i], s.get_dst_areg[i])
      s.connect(s.rename_table.update_preg[i], s.get_dst_preg[i])
      s.connect(s.rename_table.update_call[i], s.get_dst_need_writeback[i])
      s.connect(s.ready_table.write_addr[i + num_dst_ports], s.get_dst_preg[i])
      s.connect(s.ready_table.write_data[i + num_dst_ports], 0)
      s.connect(s.ready_table.write_call[i + num_dst_ports],
                s.get_dst_need_writeback[i])

    # is_ready
    s.read_muxes_ready = [Mux(Bits(1), 2) for _ in range(num_is_ready_ports)]
    s.is_ready_is_zero_tag = [Wire(1) for _ in range(num_is_ready_ports)]
    for i in range(num_is_ready_ports):

      @s.combinational
      def handle_read(i=i):
        s.is_ready_is_zero_tag[i].v = s.is_ready_tag[i] == s.ZERO_TAG

      s.connect(s.is_ready_tag[i], s.ready_table.read_addr[i])
      s.connect(s.read_muxes_ready[i].mux_in_[0], s.ready_table.read_data[i])
      s.connect(s.read_muxes_ready[i].mux_in_[1], 1)
      s.connect(s.read_muxes_ready[i].mux_select, s.is_ready_is_zero_tag[i])
      s.connect(s.is_ready_ready[i], s.read_muxes_ready[i].mux_out)

    # read
    s.read_forwarded_data = [
        Wire(dlen) for _ in range(num_is_ready_ports * (num_forward_ports + 1))
    ]
    for i in range(num_is_ready_ports):

      @s.combinational
      def handle_read_forwarded_data_0(i=i):
        s.read_forwarded_data[i].v = s.preg_file.read_data[i]

      for j in range(num_forward_ports):

        @s.combinational
        def handle_read_forwarded_data(last=num_is_ready_ports * j + i,
                                       now=num_is_ready_ports * (j + 1) + i,
                                       i=i,
                                       j=j):
          if s.forward_call[j] and s.forward_tag[j] == s.read_tag[i]:
            s.read_forwarded_data[now].v = s.forward_value[j]
          else:
            s.read_forwarded_data[now].v = s.read_forwarded_data[last]

    s.read_muxes_value = [Mux(Bits(dlen), 2) for _ in range(num_is_ready_ports)]
    s.read_is_zero_tag = [Wire(1) for _ in range(num_is_ready_ports)]
    for i in range(num_is_ready_ports):

      @s.combinational
      def handle_read(i=i):
        s.read_is_zero_tag[i].v = s.read_tag[i] == s.ZERO_TAG

      s.connect(s.read_tag[i], s.preg_file.read_addr[i])
      # We take data after the forwarding has been handled
      s.connect(
          s.read_muxes_value[i].mux_in_[0],
          s.read_forwarded_data[num_is_ready_ports * num_forward_ports + i])
      s.connect(s.read_muxes_value[i].mux_in_[1], 0)
      s.connect(s.read_muxes_value[i].mux_select, s.read_is_zero_tag[i])
      s.connect(s.read_value[i], s.read_muxes_value[i].mux_out)

    # snapshot
    # ready if a snapshot ID is available
    s.connect(s.snapshot_rdy, s.snapshot_allocator.alloc_rdy[0])
    # snapshot ID is allocated by the allocator and returned
    s.connect(s.snapshot_id_, s.snapshot_allocator.alloc_index[0])
    s.connect(s.snapshot_call, s.snapshot_allocator.alloc_call[0])
    # snapshot the snapshot allocator into itself
    s.connect(s.snapshot_allocator.reset_alloc_tracking_target_id,
              s.snapshot_id_)
    s.connect(s.snapshot_allocator.reset_alloc_tracking_call, s.snapshot_call)
    # snapshot the freelist
    s.connect(s.free_regs.reset_alloc_tracking_target_id, s.snapshot_id_)
    s.connect(s.free_regs.reset_alloc_tracking_call, s.snapshot_call)
    s.connect(s.store_ids.reset_alloc_tracking_target_id, s.snapshot_id_)
    s.connect(s.store_ids.reset_alloc_tracking_call, s.snapshot_call)
    # snapshot the rename table
    s.connect(s.rename_table.snapshot_target_id, s.snapshot_id_)
    s.connect(s.rename_table.snapshot_call, s.snapshot_call)

    # free_snapshot
    # just free it in the snapshot allocator, all the various
    # snapshots will eventually be overwritten
    s.connect(s.snapshot_allocator.free_index[0], s.free_snapshot_id_)
    s.connect(s.snapshot_allocator.free_call[0], s.free_snapshot_call)

    # restore
    # restore the snapshot allocator
    s.connect(s.snapshot_allocator.revert_allocs_source_id, s.restore_source_id)
    s.connect(s.snapshot_allocator.revert_allocs_call, s.restore_call)
    # restore the free list
    s.connect(s.free_regs.revert_allocs_source_id, s.restore_source_id)
    s.connect(s.free_regs.revert_allocs_call, s.restore_call)
    s.connect(s.store_ids.revert_allocs_source_id, s.restore_source_id)
    s.connect(s.store_ids.revert_allocs_call, s.restore_call)
    # restore the rename table
    s.connect(s.rename_table.restore_source_id, s.restore_source_id)
    s.connect(s.rename_table.restore_call, s.restore_call)

    # rollback
    # set the snapshot allocator to the architectural state of no snapshots
    # meaning everything is free (all ones)
    s.connect(s.snapshot_allocator.set_state, (~Bits(nsnapshots, 0)).uint())
    s.connect(s.snapshot_allocator.set_call, s.rollback_call)
    # set the free list to arch_used_pregs (note that write_dump_bypass
    # is true)
    # use a packer to collect all the bits
    s.arch_used_pregs_packer = Packer(Bits(1), npregs - 1)
    for i in range(npregs - 1):
      s.connect(s.arch_used_pregs_packer.pack_in_[i],
                s.arch_used_pregs.dump_out[i])
    # set the free regs to the complement
    @s.combinational
    def handle_rollback_free_regs_set():
      s.free_regs.set_state.v = ~s.arch_used_pregs_packer.pack_packed

    s.connect(s.free_regs.set_call, s.rollback_call)
    s.connect(s.store_ids.set_state, (~Bits(nstore_queue, 0)).uint())
    s.connect(s.store_ids.set_call, s.rollback_call)
    # set the rename table to the areg_file (again write_dump_bypass is true)
    for i in range(naregs):
      s.connect(s.rename_table.set_in_[i], s.areg_file.dump_out[i])
    s.connect(s.rename_table.set_call, s.rollback_call)

  def line_trace(s):
    return "<dataflow>"
