"""Hardware abstraction layer for the system on which process groups are run.

Classes:
ProcessGroup -- a group of processes started with mpirun
BGSystem -- Blue Gene system component
"""

import pwd
import grp
import logging
import sys
import os
import signal
import tempfile
import time
import thread
import ConfigParser
import subprocess
import Cobalt
import Cobalt.Data
import Cobalt.Util
from Cobalt.Components.base import exposed, automatic, query, locking
from Cobalt.Exceptions import ProcessGroupCreationError
from Cobalt.Components.cluster_base_system import ClusterBaseSystem
from Cobalt.DataTypes.ProcessGroup import ProcessGroup
from Cobalt.Proxy import ComponentProxy


__all__ = [
    "ClusterProcessGroup",
    "ClusterSystem"
]

logger = logging.getLogger(__name__)

class ClusterProcessGroup(ProcessGroup):
    _configfields = ['prologue', 'epilogue', 'epilogue_timeout', 'epi_epilogue', 'hostfile', 'prologue_timeout']
    _config = ConfigParser.ConfigParser()
    _config.read(Cobalt.CONFIG_FILES)
    if not _config._sections.has_key('cluster_system'):
        print '''"cluster_system" section missing from cobalt config file'''
        sys.exit(1)
    config = _config._sections['cluster_system']
    mfields = [field for field in _configfields if not config.has_key(field)]
    if mfields:
        print "Missing option(s) in cobalt config file [cluster_system] section: %s" % (" ".join(mfields))
        sys.exit(1)

    
    def __init__(self, spec):
        ProcessGroup.__init__(self, spec, logger)
        self.nodefile = ""
        self.start()
        
    
    def prefork (self):
        ret = {}
        
        # check for valid user/group
        try:
            userid, groupid = pwd.getpwnam(self.user)[2:4]
        except KeyError:
            raise ProcessGroupCreationError("error getting uid/gid")

        ret["userid"] = userid
        ret["primary_group"] = groupid
        
        self.nodefile = "/var/tmp/cobalt.%s" % self.jobid
        
        # get supplementary groups
        supplementary_group_ids = []
        for g in grp.getgrall():
            if self.user in g.gr_mem:
                supplementary_group_ids.append(g.gr_gid)
        
        ret["other_groups"] = supplementary_group_ids
        
        ret["umask"] = self.umask
        
        try:
            rank0 = self.location[0].split(":")[0]
        except IndexError:
            raise ProcessGroupCreationError("no location")

        kerneloptions = self.kerneloptions

        ret["postfork_env"] = self.env
        ret["stdin"] = self.stdin
        ret["stdout"] = self.stdout
        ret["stderr"] = self.stderr
        
        cmd_string = "/usr/bin/cobalt-launcher.py --nf %s --jobid %s --cwd %s --exe %s" % (self.nodefile, self.jobid, self.cwd, self.executable)
        cmd = ("/usr/bin/ssh", "/usr/bin/ssh", rank0, cmd_string)

        
        ret["id"] = self.id
        ret["jobid"] = self.jobid
        ret["cobalt_log_file"] = self.cobalt_log_file
        ret["cmd" ] = cmd

        return ret

    


class ClusterSystem (ClusterBaseSystem):
    
    """cluster system component.
    
    Methods:
    configure -- load partitions from the bridge API
    add_process_groups -- add (start) an mpirun process on the system (exposed, ~query)
    get_process_groups -- retrieve mpirun processes (exposed, query)
    wait_process_groups -- get process groups that have exited, and remove them from the system (exposed, query)
    signal_process_groups -- send a signal to the head process of the specified process groups (exposed, query)
    update_partition_state -- update partition state from the bridge API (runs as a thread)
    """
    
    name = "system"
    implementation = "cluster_system"
    
    logger = logger

    
    def __init__ (self, *args, **kwargs):
        ClusterBaseSystem.__init__(self, *args, **kwargs)
        self.process_groups.item_cls = ClusterProcessGroup

        
    def __setstate__(self, state):
        ClusterBaseSystem.__setstate__(self, state)
        self.process_groups.item_cls = ClusterProcessGroup

    
    def add_process_groups (self, specs):
        """Create a process group.
        
        Arguments:
        spec -- dictionary hash specifying a process group to start
        """

        self.logger.info("add_process_groups(%r)", specs)
        process_groups = self.process_groups.q_add(specs)
        for pgroup in process_groups:
            self.logger.info("job %s/%s: process group %s created to track script", 
                    pgroup.jobid, pgroup.user, pgroup.id)

        return process_groups
    add_process_groups = exposed(query(add_process_groups))
    
    def get_process_groups (self, specs):
        self._get_exit_status()
        return self.process_groups.q_get(specs)
    get_process_groups = exposed(query(get_process_groups))
    
    def _get_exit_status (self):
        try:
            running = ComponentProxy("forker").active_list()
        except:
            self.logger.error("failed to contact forker component for list of running jobs")
            return

        for each in self.process_groups.itervalues():
            if each.head_pid not in running and each.exit_status is None:
                # FIXME: i bet we should consider a retry thing here -- if we fail enough times, just
                # assume the process is dead?  or maybe just say there's no exit code the first time it happens?
                # maybe the second choice is better
                try:
                    dead_dict = ComponentProxy("forker").get_status(each.head_pid)
                except Queue.Empty:
                    self.logger.error("failed call for get_status from forker component for pg %s", each.head_pid)
                    return
                
                if dead_dict is None:
                    self.logger.info("process group %i: job %s/%s exited with unknown status", each.id, each.jobid, each.user)
                    each.exit_status = 1234567
                else:
                    each.exit_status = dead_dict["exit_status"]
                    if dead_dict["signum"] == 0:
                        self.logger.info("process group %i: job %s/%s exited with status %i", 
                            each.id, each.jobid, each.user, each.exit_status)
                    else:
                        if dead_dict["core_dump"]:
                            core_dump_str = ", core dumped"
                        else:
                            core_dump_str = ""
                        self.logger.info("process group %i: job %s/%s terminated with signal %s%s", 
                            each.id, each.jobid, each.user, dead_dict["signum"], core_dump_str)
    
    _get_exit_status = automatic(_get_exit_status)
    
    def wait_process_groups (self, specs):
        self._get_exit_status()
        process_groups = [pg for pg in self.process_groups.q_get(specs) if pg.exit_status is not None]
        for process_group in process_groups:
            thread.start_new_thread(self.clean_nodes, (process_group,))
        return process_groups
    wait_process_groups = locking(exposed(query(wait_process_groups)))
    
    def signal_process_groups (self, specs, signame="SIGINT"):
        my_process_groups = self.process_groups.q_get(specs)
        for pg in my_process_groups:
            if pg.exit_status is None:
                try:
                    ComponentProxy("forker").signal(pg.head_pid, signame)
                except:
                    self.logger.error("Failed to communicate with forker when signalling job")

        return my_process_groups
    signal_process_groups = exposed(query(signal_process_groups))

    def clean_nodes(self, pg):
        try:
            tmp_data = pwd.getpwnam(pg.user)
            groupid = tmp_data.pw_gid
            group_name = grp.getgrgid(groupid)[0]
        except KeyError:
            group_name = ""
            self.logger.error("Job %s/%s unable to determine group name for epilogue" % (pg.jobid, pg.user))
 
        processes = []
        for host in pg.location:
            h = host.split(":")[0]
            try:
                p = subprocess.Popen(["/usr/bin/ssh", h, pg.config.get("epilogue"), str(pg.jobid), pg.user, group_name], 
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                p.host = h
                processes.append(p)
            except:
                self.logger.error("Job %s/%s failed to run epilogue on host %s", pg.jobid, pg.user, h, exc_info=True)
        
        start = time.time()
        dirty_nodes = []
        while True:
            running = False
            for p in processes:
                if p.poll() is None:
                    running = True
                    break
            
            if not running:
                break
            
            if time.time() - start > float(pg.config.get("epilogue_timeout")):
                for p in processes:
                    if p.poll() is None:
                        try:
                            os.kill(p.pid, signal.SIGTERM)
                            dirty_nodes.append(p.host)
                            self.logger.error("Job %s/%s epilogue timed out on host %s" % (pg.jobid, pg.user, p.host))
                        except:
                            self.logger.error("epilogue for %s already terminated" %p.host)
                break
            else:
                time.sleep(5)

        for p in processes:
            if p.poll() > 0:
                self.logger.error("epilogue failed for host %s", p.host)
                self.logger.error("stderr from epilogue on host %s: [%s]", p.host, p.stderr.read().strip())
            
            
        self.lock.acquire()
        try:
            self.logger.info("job finished on %s", Cobalt.Util.merge_nodelist(pg.location))
            for host in pg.location:
                self.running_nodes.discard(host)
            
            if dirty_nodes:    
                for host in dirty_nodes:
                    self.down_nodes.add(host)
                    self.logger.info("epilogue timed out, marking host %s down" % host)
                p = subprocess.Popen([pg.config.get("epi_epilogue"), str(pg.jobid), pg.user, group_name] + dirty_nodes)
            
            del self.process_groups[pg.id]
        except:
            self.logger.error("error in clean_nodes", exc_info=True)
        self.lock.release()
        
