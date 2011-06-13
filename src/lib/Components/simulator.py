"""Hardware abstraction layer for the system on which process groups are run.

Classes:
BGSimProcessGroup -- virtual process group running on the system
Simulator -- simulated system component
"""

import pwd
import logging
import sys
import os
import operator
import random
import time
import thread
import threading
import xmlrpclib
from datetime import datetime
from ConfigParser import ConfigParser

try:
    from elementtree import ElementTree
except ImportError:
    from xml.etree import ElementTree

import Cobalt
import Cobalt.Data
import Cobalt.Util
from Cobalt.Components import bg_base_system
from Cobalt.Data import Data, DataDict, IncrID
from Cobalt.Components.base import Component, exposed, automatic, query
from Cobalt.Components.bg_base_system import NodeCard, Partition, PartitionDict, BGProcessGroupDict, BGBaseSystem
from Cobalt.Exceptions import ProcessGroupCreationError, ComponentLookupError
from Cobalt.Proxy import ComponentProxy
from Cobalt.Statistics import Statistics
from Cobalt.DataTypes.ProcessGroup import ProcessGroup

__all__ = [
    "BGSimProcessGroup", 
    "Simulator",
]

logger = logging.getLogger(__name__)


class BGSimProcessGroup(ProcessGroup):
    """Process Group modified for Blue Gene Simulator"""

    def __init__(self, spec):
        ProcessGroup.__init__(self, spec)
        self.nodect = spec.get("nodect",None)



class Simulator (BGBaseSystem):
    
    """Generic system simulator.
    
    Methods:
    configure -- load partitions from an xml file
    reserve_partition -- lock a partition for use by a process_group (exposed)
    release_partition -- release a locked (busy) partition (exposed)
    add_process_groups -- add (start) a process group on the system (exposed, query)
    get_process_groups -- retrieve process groups (exposed, query)
    wait_process_groups -- get process groups that have exited, and remove them from the system (exposed, query)
    signal_process_groups -- send a signal to the head process of the specified process groups (exposed, query)
    update_partition_state -- simulates updating partition state from the bridge API (automatic)
    """
    
    name = "system"
    implementation = "simulator"
    
    logger = logger

    MIN_RUN_TIME = 60
    MAX_RUN_TIME = 180

    def __init__ (self, *args, **kwargs):
        BGBaseSystem.__init__(self, *args, **kwargs)
        sys.setrecursionlimit(5000) #why this magic number?
        self.process_groups.item_cls = BGSimProcessGroup
        self.config_file = kwargs.get("config_file", None)
        self.failed_components = set()
        if self.config_file is not None:
            self.configure(self.config_file)
    
    def __getstate__(self):
        flags = {}
        for part in self._partitions.values():
            sched = None
            func = None
            queue = None
            if hasattr(part, 'scheduled'):
                sched = part.scheduled
            if hasattr(part, 'functional'):
                func = part.functional
            if hasattr(part, 'queue'):
                queue = part.queue
            flags[part.name] =  (sched, func, queue)
        return {'managed_partitions':self._managed_partitions, 'version':2, 'config_file':self.config_file, 'partition_flags': flags}
    
    def __setstate__(self, state):
        Cobalt.Util.fix_set(state)
        sys.setrecursionlimit(5000)
        self._managed_partitions = state['managed_partitions']
        self.config_file = state['config_file']
        self._partitions = PartitionDict()
        self.process_groups = BGProcessGroupDict()
        self.process_groups.item_cls = BGSimProcessGroup
        self.node_card_cache = dict()
        self._partitions_lock = thread.allocate_lock()
        self.failed_components = set()
        self.pending_diags = dict()
        self.failed_diags = list()
        self.bridge_in_error = False
        self.cached_partitions = None
        self.offline_partitions = []
        if self.config_file is not None:
            self.configure(self.config_file)

        if 'partition_flags' in state:
            for pname, flags in state['partition_flags'].items():
                if pname in self._partitions:
                    self._partitions[pname].scheduled = flags[0]
                    self._partitions[pname].functional = flags[1]
                    self._partitions[pname].queue = flags[2]
                else:
                    logger.info("Partition %s is no longer defined" % pname)

        self.update_relatives()
        self.lock = threading.Lock()
        self.statistics = Statistics()
        
    def save_me(self):
        Component.save(self)
    save_me = automatic(save_me)


    def configure (self, config_file):
        
        """Configure simulated partitions.
        
        Arguments:
        config_file -- xml configuration file
        """
        
        def _get_node_card(name):
            if not self.node_card_cache.has_key(name):
                self.node_card_cache[name] = NodeCard(name)
                
            return self.node_card_cache[name]
            
            
        self.logger.info("configure()")
        try:
            system_doc = ElementTree.parse(config_file)
        except IOError:
            self.logger.error("unable to open file: %r" % config_file)
            self.logger.error("exiting...")
            sys.exit(1)
        except:
            self.logger.error("problem loading data from file: %r" % config_file)
            self.logger.error("exiting...")
            sys.exit(1)
            
        system_def = system_doc.getroot()
        if system_def.tag != "BG":
            self.logger.error("unexpected root element in %r: %r" % (config_file, system_def.tag))
            self.logger.error("exiting...")
            sys.exit(1)
        
        # that 32 is not really constant -- it needs to either be read from cobalt.conf or from the bridge API
        NODES_PER_NODECARD = 32
                
        # initialize a new partition dict with all partitions
        #
        partitions = PartitionDict()
        
        tmp_list = []

        # this is going to hold partition objects from the bridge (not our own Partition)
        wiring_cache = {}
        bp_cache = {}
        
        for partition_def in system_def.getiterator("Partition"):
            node_list = []
            switch_list = []
            
            for nc in partition_def.getiterator("NodeCard"): 
                node_list.append(_get_node_card(nc.get("id")))

            nc_count = len(node_list)
            
            if not wiring_cache.has_key(nc_count):
                wiring_cache[nc_count] = []
            wiring_cache[nc_count].append(partition_def.get("name"))

            for s in partition_def.getiterator("Switch"):
                switch_list.append(s.get("id"))

            tmp_list.append( dict(
                name = partition_def.get("name"),
                queue = partition_def.get("queue", "default"),
                size = NODES_PER_NODECARD * nc_count,
                node_cards = node_list,
                switches = switch_list,
                state = "idle",
            ))
        
        partitions.q_add(tmp_list)
        
        # find the wiring deps
        for size in wiring_cache:
            for p in wiring_cache[size]:
                p = partitions[p]
                s1 = set( p.switches )
                for other in wiring_cache[size]:
                    other = partitions[other]
                    if (p.name == other.name):
                        continue

                    s2 = set( other.switches )
                    
                    if s1.intersection(s2):
                        self.logger.info("found a wiring dep between %s and %s", p.name, other.name)
                        partitions[p.name]._wiring_conflicts.add(other.name)
        
            
        # update object state
        self._partitions.clear()
        self._partitions.update(partitions)

    
    def reserve_partition (self, name, size=None):
        """Reserve a partition and block all related partitions.
        
        Arguments:
        name -- name of the partition to reserve
        size -- size of the process group reserving the partition (optional)
        """
        
        try:
            partition = self.partitions[name]
        except KeyError:
            self.logger.error("reserve_partition(%r, %r) [does not exist]" % (name, size))
            return False
        if partition.state != "allocated":
            self.logger.error("reserve_partition(%r, %r) [%s]" % (name, size, partition.state))
            return False
        if not partition.functional:
            self.logger.error("reserve_partition(%r, %r) [not functional]" % (name, size))
        if size is not None and size > partition.size:
            self.logger.error("reserve_partition(%r, %r) [size mismatch]" % (name, size))
            return False

        self._partitions_lock.acquire()
        try:
            partition.state = "busy"
            partition.reserved_until = False
        except:
            self.logger.error("error in reserve_partition", exc_info=True)
        self._partitions_lock.release()
        # explicitly call this, since the above "busy" is instantaneously available
        self.update_partition_state()
        
        self.logger.info("reserve_partition(%r, %r)" % (name, size))
        return True
    reserve_partition = exposed(reserve_partition)
    
    def release_partition (self, name):
        """Release a reserved partition.
        
        Arguments:
        name -- name of the partition to release
        """
        try:
            partition = self.partitions[name]
        except KeyError:
            self.logger.error("release_partition(%r) [already free]" % (name))
            return False
        if not partition.state == "busy":
            self.logger.info("release_partition(%r) [not busy]" % (name))
            return False
                
        self._partitions_lock.acquire()
        try:
            partition.state = "idle"
        except:
            self.logger.error("error in release_partition", exc_info=True)
        self._partitions_lock.release()
        
        # explicitly unblock the blocked partitions
        self.update_partition_state()

        self.logger.info("release_partition(%r)" % (name))
        return True
    release_partition = exposed(release_partition)
    
    def add_process_groups (self, specs):
        
        """Create a simulated process group.
        
        Arguments:
        spec -- dictionary hash specifying a process group to start
        """
        
        self.logger.info("add_process_groups(%r)" % (specs))

        # FIXME: setting exit_status to signal the job has failed isn't really the right thing to do.  another flag should be
        # added to the process group that wait_process_group uses to determine when a process group is no longer active.  an
        # error message should also be attached to the process group so that cqm can report the problem to the user.
        process_groups = self.process_groups.q_add(specs)
        for pgroup in process_groups:
            pgroup.label = "Job %s/%s/%s" % (pgroup.jobid, pgroup.user, pgroup.id)
            pgroup.nodect = self._partitions[pgroup.location[0]].size
            self.logger.info("%s: process group %s created to track job status", pgroup.label, pgroup.id)
            try:
                #TODO: allow the kernel set step to work in the simulator.  For now this doesn't fly.
                pass
                #self._set_kernel(pgroup.location[0], pgroup.kernel)
            except Exception, e:
                self.logger.error("%s: failed to set the kernel; %s", pgroup.label, e)
                pgroup.exit_status = 255
            else:
                if pgroup.kernel != "default":
                    self.logger.info("%s: now using kernel %s", pgroup.label, pgroup.kernel)
                if pgroup.mode == "script":
                    pgroup.forker = 'user_script_forker'
                else:
                    pgroup.forker = 'bg_mpirun_forker'
                if self.reserve_resources_until(pgroup.location, float(pgroup.starttime) + 60*float(pgroup.walltime), pgroup.jobid):
                    try:
                        pgroup.start()
                        if pgroup.head_pid == None:
                            self.logger.error("%s: process group failed to start using the %s component; releasing resources",
                                pgroup.label, pgroup.forker)
                            self.reserve_resources_until(pgroup.location, None, pgroup.jobid)
                            pgroup.exit_status = 255
                    except (ComponentLookupError, xmlrpclib.Fault), e:
                        self.logger.error("%s: failed to contact the %s component", pgroup.label, pgroup.forker)
                        # do not release the resources; instead re-raise the exception and allow cqm to the opportunity to retry
                        # until the job has exhausted its maximum alloted time
                        del self.process_groups[pgroup.id]
                        raise
                    except (ComponentLookupError, xmlrpclib.Fault), e:
                        self.logger.error("%s: a fault occurred while attempting to start the process group using the %s "
                            "component", pgroup.label, pgroup.forker)
                        # do not release the resources; instead re-raise the exception and allow cqm to the opportunity to retry
                        # until the job has exhausted its maximum alloted time
                        del self.process_groups[process_group.id]
                        raise
                    except:
                        self.logger.error("%s: an unexpected exception occurred while attempting to start the process group "
                            "using the %s component; releasing resources", pgroup.label, pgroup.forker, exc_info=True)
                        self.reserve_resources_until(pgroup.location, None, pgroup.jobid)
                        pgroup.exit_status = 255
                else:
                    self.logger.error("%s: the internal reservation on %s expired; job has been terminated", pgroup.label,
                        pgroup.location)
                    pgroup.exit_status = 255
        return process_groups

        
    add_process_groups = exposed(query(all_fields=True)(add_process_groups))
    
    def get_process_groups (self, specs):
        """Query process_groups from the simulator."""
        self._get_exit_status()
        return self.process_groups.q_get(specs)
    
    get_process_groups = exposed(query(get_process_groups))


    def _get_exit_status (self):

        #common to bgsystem

        running = []
        active_forker_components = []
        for forker_component in ['bg_mpirun_forker', 'user_script_forker']:
            try:
                running.extend(ComponentProxy(forker_component).active_list("process group"))
                active_forker_components.append(forker_component)
            except:
                self.logger.error("failed to contact %s component for list of running jobs", forker_component)

        for each in self.process_groups.itervalues():
            if each.head_pid not in running and each.exit_status is None and each.forker in active_forker_components:
                # FIXME: i bet we should consider a retry thing here -- if we fail enough times, just
                # assume the process is dead?  or maybe just say there's no exit code the first time it happens?
                # maybe the second choice is better
                try:
                    if each.head_pid != None:
                        dead_dict = ComponentProxy(each.forker).get_status(each.head_pid)
                    else:
                        dead_dict = None
                except:
                    self.logger.error("%s: RPC to get_status method in %s component failed", each.label, each.forker)
                    return
                
                if dead_dict is None:
                    self.logger.info("%s: job exited with unknown status", each.label)
                    # FIXME: should we use a negative number instead to indicate internal errors? --brt
                    each.exit_status = 1234567
                else:
                    each.exit_status = dead_dict["exit_status"]
                    if dead_dict["signum"] == 0:
                        self.logger.info("%s: job exited with status %i", each.label, each.exit_status)
                    else:
                        if dead_dict["core_dump"]:
                            core_dump_str = ", core dumped"
                        else:
                            core_dump_str = ""
                        self.logger.info("%s: terminated with signal %s%s", each.label, dead_dict["signum"], core_dump_str)
                    self.reserve_resources_until(each.location, None, each.jobid)
            
    _get_exit_status = automatic(_get_exit_status)

    
    def wait_process_groups (self, specs):
        """get process groups that have finished running."""
        
            
        #self.logger.info("wait_process_groups(%r)" % (specs))
        self._get_exit_status()
        process_groups = [pg for pg in self.process_groups.q_get(specs) if pg.exit_status is not None]
        for process_group in process_groups:
            self.reserve_resources_until(process_group.location, None, process_group.jobid)
            del self.process_groups[process_group.id]
        return process_groups
    
    wait_process_groups = exposed(query(wait_process_groups))
    
    def signal_process_groups (self, specs, signame="SIGINT"):
        """Simulate the signaling of a process_group."""
        
        my_process_groups = self.process_groups.q_get(specs)
        for pg in my_process_groups:
            if pg.exit_status is None:
                try:
                    if pg.head_pid != None:
                        self.logger.warning("%s: sending signal %s via %s", pg.label, signame, pg.forker)
                        ComponentProxy(pg.forker).signal(pg.head_pid, signame)
                    else:
                        self.logger.warning("%s: attempted to send a signal to job that never started", pg.label)
                except:
                    self.logger.error("%s: failed to communicate with %s when signaling job", pg.label, pg.forker)

                if signame == "SIGKILL":
                    self._mark_partition_for_cleaning(pg.location[0], pg.jobid)

        return my_process_groups
        
        #self.logger.info("signal_process_groups(%r, %r)" % (specs, signame))
        #process_groups = self.process_groups.q_get(specs)
        #for process_group in process_groups:
        #    if process_group.mode == "script":
        #        try:
        #            pgroup = ComponentProxy("script-manager").signal_jobs([{'id':process_group.script_id}], "SIGTERM")
        #        except (ComponentLookupError, xmlrpclib.Fault):
        #            logger.error("Failed to communicate with script manager when killing job")
        #    else:
        #        process_group.signals.append(signame)
        #return process_groups
    signal_process_groups = exposed(query(signal_process_groups))
    
    
    
    def update_partition_state(self):
        # first, set all of the nodecards to not busy
        for nc in self.node_card_cache.values():
            nc.used_by = ''

        self._partitions_lock.acquire()
        try:
            for p in self._partitions.values():
                p._update_node_cards()
                
            now = time.time()
            
            # since we don't have the bridge, a partition which isn't busy
            # should be set to idle and then blocked states can be derived
            for p in self._partitions.values():
                if p.state != "busy":
                    p.state = "idle"
                if p.reserved_until and now > p.reserved_until:
                    p.reserved_until = None
                    p.reserved_by = None
                    
            for p in self._partitions.values():
                if p.state == "busy":
                    # when the partition becomes busy, if a script job isn't reserving it, then release the reservation
                    if not p.reserved_by:
                        p.reserved_until = False
                else:
                    if p.reserved_until:
                        p.state = "allocated"
                        for part in p._parents:
                            if part.state == "idle":
                                part.state = "blocked (%s)" % (p.name,)
                        for part in p._children:
                            if part.state == "idle":
                                part.state = "blocked (%s)" % (p.name,)
                    for diag_part in self.pending_diags:
                        if p.name == diag_part.name or p.name in diag_part.parents or p.name in diag_part.children:
                            p.state = "blocked by pending diags"
                    for nc in p.node_cards:
                        if nc.used_by:
                            p.state = "blocked (%s)" % nc.used_by
                            break
                    for dep_name in p._wiring_conflicts:
                        if self._partitions[dep_name].state in ["allocated", "busy"]:
                            p.state = "blocked-wiring (%s)" % dep_name
                            break
                    for part_name in self.failed_diags:
                        part = self._partitions[part_name]
                        if p.name == part.name:
                            p.state = "failed diags"
                        elif p.name in part.parents or p.name in part.children:
                            p.state = "blocked by failed diags"
        except:
            self.logger.error("error in update_partition_state", exc_info=True)
        
        self._partitions_lock.release()
    update_partition_state = automatic(update_partition_state)

    def add_failed_components(self, component_names):
        success = []
        for name in component_names:
            if self.node_card_cache.has_key(name):
                self.failed_components.add(name)
                success.append(name)
            else:
                for p in self._partitions.values():
                    if name in p.switches:
                        self.failed_components.add(name)
                        success.append(name)
                        break
        return success
    add_failed_component = exposed(add_failed_components)
    
    def del_failed_components(self, component_names):
        success = []
        for name in component_names:
            try:
                self.failed_components.remove(name)
                success.append(name)
            except KeyError:
                pass
            
        return success
    del_failed_components = exposed(del_failed_components)
    
    def list_failed_components(self, component_names):
        return list(self.failed_components)
    list_failed_components = exposed(list_failed_components)
    
    def launch_diags(self, partition, test_name):
        exit_value = 0
        for nc in partition.node_cards:
            if nc.id in self.failed_components:
                exit_value = 1
        for switch in partition.switches:
            if switch in self.failed_components:
                exit_value = 2

        self.finish_diags(partition, test_name, exit_value)
