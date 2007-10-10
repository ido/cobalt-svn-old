import bgl_rm_api, Cobalt.Util
from ctypes import *

bridge = cdll.LoadLibrary('libbglbridge.so.1')

bridge.rm_get_serial.restype = bgl_rm_api.status_t
bridge.rm_set_serial.restype = bgl_rm_api.status_t
bridge.rm_get_BGL.restype = bgl_rm_api.status_t
bridge.rm_get_data.restype = bgl_rm_api.status_t

getvalue = lambda x:x.value
passthru = lambda x:x
boolean = lambda x:x.value != 0

class BGStub(object):
    __attrinfo__ = []
    nocache = []
    hidden = []
    def __init__(self, debug=4):
        self.setDebug(debug)
        s = bridge.rm_set_serial(c_char_p("BGL"))
        self.attrcache = {}

    def setDebug(self, level):
        pass

    def fetchattr(self, attr):
        (field, _, dtype, massage) = self.__attrinfo__[attr]
        data = dtype()
        s = bridge.rm_get_data(self.ptr, field, byref(data))
        if attr not in self.nocache:
            self.attrcache[attr] = massage(data)
        return massage(data)

    def __getattr__(self, attr):
        if attr in self.__attrinfo__:
            # use local cache
            if attr not in self.attrcache:
#                 print 'not using local cache', self.id, attr
                return self.fetchattr(attr)
#             print 'using cache for:', self.id, attr
            return self.attrcache[attr]
        else:
            return object.__getattribute__(self, attr)

    def setattribute(self, attr, value):
        (field, mfield, dtype, massage) = self.__attrinfo__[attr]
        if mfield == None:
            raise Exception, 'attr %s not settable' % attr
        data = dtype(value)
        s = apply(self.__modify__, (self.id, mfield, data))
        if s:
            raise Exception, 'problem setting %s' % attr
#         s = bridge.rm_set_data(self.ptr, field, byref(data))
#         if attr not in self.nocache:
#             self.attrcache[attr] = massage(data)
#        return massage(data)
        if attr in self.attrcache:
            del self.attrcache[attr]
        return

    def __setattr__(self, attr, value):
        if attr in object.__getattribute__(self, '__attrinfo__'):
            #try setting the attr
            return self.setattribute(attr, value)
        return object.__setattr__(self, attr, value)

    def Visible(self):
        return [item for item in self.__attrinfo__ \
                if item not in self.hidden]

    def reload(self):
        '''reloads self from bridge data'''
        pass

class LazyRMSet(object):
    def __init__(self, object, sname, hname, tname, cclass):
        self.nocache = [tname]
        self.object = object  #usually self
        self.sname = sname    #size attribute
        self.hname = hname    #head attribute
        self.tname = tname    #tail attribute
        self.cclass = cclass  #class for list members
        self.data = []
        if len(self) > 0:
            head = self.cclass(getattr(self.object, self.hname))
            self.data = [head]
            while len(self.data) < getattr(self.object, self.sname):
                tail = self.cclass(getattr(self.object, self.tname))
                self.data.append(tail)
            
    def __len__(self):
        return getattr(self.object, self.sname)

    def __iter__(self):
        return self.data.__iter__()

    def __getitem__(self, num):
        return self.data.__getitem__(num)

class PreStub(BGStub):
    def __init__(self, mypointer):
        self.attrcache = {}
        self.ptr = mypointer

class BasePartition(PreStub):
    __attrinfo__ = {'id': \
                    (bgl_rm_api.RM_BPID, None, bgl_rm_api.rm_bp_id_t, getvalue),
                    'state': \
                    (bgl_rm_api.RM_BPState, None, bgl_rm_api.rm_BP_state_t,
                     bgl_rm_api.RM_BPStateEnum),
                    'location': \
                    (bgl_rm_api.RM_BPLoc, None, bgl_rm_api.rm_location_t,
                     lambda data:{'X':data.X, 'Y':data.Y, 'Z':data.Z}),
                    'partid': \
                    (bgl_rm_api.RM_BPPartID, None, bgl_rm_api.pm_partition_id_t,
                     getvalue),
                    'partstate': \
                    (bgl_rm_api.RM_BPPartState, None,
                     bgl_rm_api.rm_partition_state_t,
                     bgl_rm_api.RM_PartitionStateEnum),
                     #used by smaller partition
                    'sdb': \
                    (bgl_rm_api.RM_BPSDB, None,
                     c_int, boolean),
                     #divided into a small (free) partition
                    'sd': \
                    (bgl_rm_api.RM_BPSD, None,
                     c_int, boolean),
                    'computenodememory': \
                    (bgl_rm_api.RM_BPComputeNodeMemory, None,
                     bgl_rm_api.rm_BP_computenode_memory_t,
                     bgl_rm_api.RM_ComputenodeMemoryEnum),
                    }
    def __init__(self, mypointer):
        self.attrcache = {}
        self.ptr = mypointer
        self.nodecards = NodeCardList(basepart=self.id)

class NodeCard(PreStub):
    __attrinfo__ = {'id': \
                    (bgl_rm_api.RM_NodeCardID, None,
                     bgl_rm_api.rm_nodecard_id_t, getvalue),
                    'quarter': \
                    (bgl_rm_api.RM_NodeCardQuarter, None,
                     bgl_rm_api.rm_quarter_t,
                     bgl_rm_api.RM_QuarterEnum),
                    'cardstate': \
                    (bgl_rm_api.RM_NodeCardState, None,
                     bgl_rm_api.rm_nodecard_state_t,
                     bgl_rm_api.RM_NodeCardStateEnum),
                    'cardionodes': \
                    (bgl_rm_api.RM_NodeCardIONodes, None,
                     c_int, getvalue),
                    'cardpartid': \
                    (bgl_rm_api.RM_NodeCardPartID, None,
                     bgl_rm_api.pm_partition_id_t, getvalue),
                    'cardpartstate': \
                    (bgl_rm_api.RM_NodeCardPartState, None,
                     bgl_rm_api.rm_partition_state_t, getvalue),
                    }

    def reload(self):
        '''reload nodecard from bridge
        does not do anything because nodecards are not modified'''
        pass
                    
class Port(PreStub):
    __attrinfo__ = {'component': \
                    (bgl_rm_api.RM_PortComponentID, None,
                     bgl_rm_api.rm_component_id_t, getvalue),
                    'id': \
                    (bgl_rm_api.RM_PortID, bgl_rm_api.rm_port_id_t,
                     getvalue),
                    }

class Wire(PreStub):
    __attrinfo__ = {'id': \
                    (bgl_rm_api.RM_WireID, None, bgl_rm_api.rm_wire_id_t,
                     getvalue),
                    'state': \
                    (bgl_rm_api.RM_WireState, None, bgl_rm_api.rm_wire_state_t,
                     getvalue),
                    'src': \
                    (bgl_rm_api.RM_WireFromPort, None, bgl_rm_api.rm_element_t,
                     Port),
                    'dst': \
                    (bgl_rm_api.RM_WireToPort, None, bgl_rm_api.rm_element_t,
                     Port),
                    'partition': \
                    (bgl_rm_api.RM_WirePartID, None, bgl_rm_api.pm_partition_id_t,
                     getvalue)
                    }

class Job(PreStub):
    __attrinfo__ = \
                 {'id': \
                  (bgl_rm_api.RM_JobDBJobID, None,
                   bgl_rm_api.db_job_id_t, getvalue),
                  'pid': \
                  (bgl_rm_api.RM_JobID, None, bgl_rm_api.jm_job_id_t, getvalue),
                  'partition': \
                  (bgl_rm_api.RM_JobPartitionID, None,
                   bgl_rm_api.pm_partition_id_t, getvalue),
                  'state': \
                  (bgl_rm_api.RM_JobState, None, bgl_rm_api.rm_job_state_t,
                   bgl_rm_api.RM_JobStateEnum),
                  'executable': \
                  (bgl_rm_api.RM_JobExecutable, None, c_char_p, getvalue),
                  'user': \
                  (bgl_rm_api.RM_JobUserName, None, c_char_p, getvalue),
                  'outfile': \
                  (bgl_rm_api.RM_JobOutFile, None, c_char_p, getvalue),
                  'infile': \
                  (bgl_rm_api.RM_JobInFile, None, c_char_p, getvalue),
                  'errfile': \
                  (bgl_rm_api.RM_JobErrFile, None, c_char_p, getvalue),
                  'outdir': \
                  (bgl_rm_api.RM_JobOutDir, None, c_char_p, getvalue),
                  'errtext': \
                  (bgl_rm_api.RM_JobErrText, None, c_char_p, getvalue),
                  'args': \
                  (bgl_rm_api.RM_JobArgs, None, c_char_p, getvalue),
                  'envs': \
                  (bgl_rm_api.RM_JobEnvs, None, c_char_p, getvalue),
                  'inhist': \
                  (bgl_rm_api.RM_JobInHist, None, c_int, boolean),
                  'mode': \
                  (bgl_rm_api.RM_JobMode, None, 
                   bgl_rm_api.rm_job_mode_t, getvalue),
                  'strace': \
                  (bgl_rm_api.RM_JobStrace, None,
                   bgl_rm_api.rm_job_strace_t, getvalue),
                  'stdin': \
                  (bgl_rm_api.RM_JobStdinInfo, None,
                   bgl_rm_api.rm_job_stdin_info_t, getvalue),
                  'stdout': \
                  (bgl_rm_api.RM_JobStdoutInfo, None,
                   bgl_rm_api.rm_job_stdout_info_t, getvalue),
                  'stderr': \
                  (bgl_rm_api.RM_JobStderrInfo, None,
                   bgl_rm_api.rm_job_stderr_info_t, getvalue),
                  'starttime': \
                  (bgl_rm_api.RM_JobStartTime, None, c_char_p, getvalue),
                  'endtime': \
                  (bgl_rm_api.RM_JobEndTime, None, c_char_p, getvalue),
                  'runtime': \
                  (bgl_rm_api.RM_JobRunTime, None,
                   bgl_rm_api.rm_job_runtime_t, getvalue),
                  'computenodesused': \
                  (bgl_rm_api.RM_JobComputeNodesUsed, None,
                   bgl_rm_api.rm_job_computenodes_used_t, getvalue),
                  'exitstatus': \
                  (bgl_rm_api.RM_JobExitStatus, None,
                   bgl_rm_api.rm_job_exitstatus_t, getvalue),
                  }

class Switch(PreStub):
    __attrinfo__ = \
                 {'id': \
                  (bgl_rm_api.RM_SwitchID, None,
                   bgl_rm_api.rm_switch_id_t, getvalue),
                  }

class PSet(PreStub):
    pass

class PartitionUsers(PreStub):
    __attrinfo__ = \
                 {'name': \
                  (bgl_rm_api.RM_PartitionUserName, None,
                   c_char_p, getvalue)}

class Partition(PreStub):
    nocache = ['Switchtail', 'BPtail', 'psetNext', 'NCtail', 'Userstail']
    __modify__ = bridge.rm_modify_partition
    hidden = ['id', 'BPnum', 'BPhead', 'BPtail', 'Switchnum', 'Switchhead',
              'Switchtail']
    __attrinfo__ = \
                 {'id': \
                  (bgl_rm_api.RM_PartitionID, None,
                   bgl_rm_api.pm_partition_id_t, getvalue),
                  'state': \
                  (bgl_rm_api.RM_PartitionState, None,
                   bgl_rm_api.rm_partition_state_t,
                   bgl_rm_api.RM_PartitionStateEnum),
                  'BPnum': \
                  (bgl_rm_api.RM_PartitionBPNum, None, c_int, getvalue),
                  'BPhead': \
                  (bgl_rm_api.RM_PartitionFirstBP, None, bgl_rm_api.rm_element_t,
                   passthru),
                  'BPtail': \
                  (bgl_rm_api.RM_PartitionNextBP, None, bgl_rm_api.rm_element_t,
                   passthru),
                  'Switchnum': \
                  (bgl_rm_api.RM_PartitionSwitchNum, None, c_int, getvalue),
                  'Switchhead': \
                  (bgl_rm_api.RM_PartitionFirstSwitch, None,
                   bgl_rm_api.rm_element_t, passthru),
                  'Switchtail': \
                  (bgl_rm_api.RM_PartitionNextSwitch, None,
                   bgl_rm_api.rm_element_t, passthru),
                  'connection': \
                  (bgl_rm_api.RM_PartitionConnection, None,
                   bgl_rm_api.rm_connection_type_t,
                   bgl_rm_api.RM_ConnectionTypeEnum),
                  'user': \
                  (bgl_rm_api.RM_PartitionUserName, bgl_rm_api.RM_MODIFY_Owner,
                   c_char_p, getvalue),
                  'mloader': \
                  (bgl_rm_api.RM_PartitionMloaderImg,
                   bgl_rm_api.RM_MODIFY_MloaderImg, c_char_p, getvalue),
                  'blrts': \
                  (bgl_rm_api.RM_PartitionBlrtsImg,
                   bgl_rm_api.RM_MODIFY_BlrtsImg, c_char_p, getvalue),
                  'linux': \
                  (bgl_rm_api.RM_PartitionLinuxImg,
                   bgl_rm_api.RM_MODIFY_LinuxImg, c_char_p, getvalue),
                  'ramdisk': \
                  (bgl_rm_api.RM_PartitionRamdiskImg,
                   bgl_rm_api.RM_MODIFY_RamdiskImg, c_char_p, getvalue),
                  'mode': \
                  (bgl_rm_api.RM_PartitionMode, None,
                   bgl_rm_api.rm_partition_mode_t,
                   bgl_rm_api.RM_PartitionModeEnum),
                  'description': \
                  (bgl_rm_api.RM_PartitionDescription,
                   bgl_rm_api.RM_MODIFY_Description, c_char_p, getvalue),
                  'small': \
                  (bgl_rm_api.RM_PartitionSmall, None, c_int, boolean),
                  'psetsPerBP': \
                  (bgl_rm_api.RM_PartitionPsetsPerBP, None, c_int, getvalue),
                  'Usersnum': \
                  (bgl_rm_api.RM_PartitionUsersNum, None, c_int, getvalue),
                  'Usershead': \
                  (bgl_rm_api.RM_PartitionFirstUser, None, c_char_p, passthru),
                  'Userstail': \
                  (bgl_rm_api.RM_PartitionNextUser, None, c_char_p, passthru),
                  'NCnum': \
                  (bgl_rm_api.RM_PartitionNodeCardNum, None, c_int, getvalue),
                  'NChead': \
                  (bgl_rm_api.RM_PartitionFirstNodeCard, None,
                   bgl_rm_api.rm_element_t, passthru),
                  'NCtail': \
                  (bgl_rm_api.RM_PartitionNextNodeCard, None,
                   bgl_rm_api.rm_element_t, passthru),
                  }

    def __init__(self, mypointer):
        PreStub.__init__(self, mypointer)
        self.basePartitions = LazyRMSet(self, 'BPnum', 'BPhead',
                                        'BPtail', BasePartition)
        self.switches = LazyRMSet(self, 'Switchnum', 'Switchhead',
                                        'Switchtail', Switch)
        self.users = LazyRMSet(self, 'Usersnum', 'Usershead',
                               'Userstail', PartitionUsers)

        if self.small:
            assert len(self.basePartitions) == 1
            [bpid] = [bp.id for bp in self.basePartitions]
            self.nodecards = LazyRMSet(self, 'NCnum', 'NChead',
                                       'NCtail', NodeCard)
            for nc in self.nodecards:
                nc.basepart = bpid
        else:
            self.nodecards = []
            for bp in self.basePartitions:
                newnclist = NodeCardList(basepart=bp.id)
                self.nodecards.extend([nc for nc in newnclist])
                del newnclist  #is this necessary?

    def reload(self):
        '''clears the lookup cache, frees the pointer, and reloads the
        bridge pointer using rm_get_partition() individually
        '''
        saveid = self.id
        self.attrcache.clear()
#         bridge.rm_free_partition(self.ptr)
#         self.ptr = pointer(bgl_rm_api.rm_element_t())
        bridge.rm_get_partition(c_char_p(saveid), byref(self.ptr))

class BG(BGStub):
    __attrinfo__ = {'BPsize': \
                    (bgl_rm_api.RM_BPsize, None, bgl_rm_api.rm_size3D_t, \
                     lambda data:{'X':data.X, 'Y':data.Y, 'Z':data.Z}),
                    'BPnum': \
                    (bgl_rm_api.RM_BPNum, None, c_int, getvalue),
                    'BPhead': \
                    (bgl_rm_api.RM_FirstBP, None, bgl_rm_api.rm_element_t,
                     passthru),
                    'BPtail': \
                    (bgl_rm_api.RM_NextBP, None, bgl_rm_api.rm_element_t,
                     passthru),
                    'SwitchNum': \
                    (bgl_rm_api.RM_SwitchNum, None, c_int, getvalue),
                    'WireNum': \
                    (bgl_rm_api.RM_WireNum, None, c_int, getvalue),
                    'FirstWire': \
                    (bgl_rm_api.RM_FirstWire, None, bgl_rm_api.rm_element_t,
                     passthru),
                    'NextWire': \
                    (bgl_rm_api.RM_NextWire, None, bgl_rm_api.rm_element_t,
                     passthru),
                    }
    def __init__(self, debug=1):
        self.ptr = pointer(bgl_rm_api.rm_BGL_t())
        BGStub.__init__(self, debug)
        bridge.rm_get_BGL(byref(self.ptr))
        self.basePartitions = LazyRMSet(self, 'BPnum', 'BPhead',
                                        'BPtail', BasePartition)
        self.wires = LazyRMSet(self, 'WireNum', 'FirstWire', 'NextWire',
                               Wire)

class JobList(BGStub, LazyRMSet):
    __attrinfo__ = \
                 {'size': \
                  (bgl_rm_api.RM_JobListSize, None, c_int, lambda data:data.value),
                  'head': \
                  (bgl_rm_api.RM_JobListFirstJob, None, bgl_rm_api.rm_element_t, \
                   lambda data:data),
                  'tail': \
                  (bgl_rm_api.RM_JobListNextJob, None, bgl_rm_api.rm_element_t, \
                   lambda data:data)}
    nocache = ['tail']

    def __init__(self, flags=4095, debug=1):
        self.ptr = pointer(bgl_rm_api.rm_job_list_t())
        BGStub.__init__(self, debug)
        bridge.rm_get_jobs(c_int(flags), byref(self.ptr))
        LazyRMSet.__init__(self, self, 'size', 'head', 'tail', Job)

class PartList(BGStub,LazyRMSet):
    __attrinfo__ = \
                 {'size': \
                  (bgl_rm_api.RM_PartListSize, None, c_int, lambda data:data.value),
                  'head': \
                  (bgl_rm_api.RM_PartListFirstPart, None, bgl_rm_api.rm_element_t, \
                   lambda data:data),
                  'tail': \
                  (bgl_rm_api.RM_PartListNextPart, None, bgl_rm_api.rm_element_t, \
                   lambda data:data)}
    nocache = ['tail']

    def __init__(self, filter=bgl_rm_api.PARTITION_ALL_FLAG, debug=1):
        self.ptr = pointer(bgl_rm_api.rm_partition_list_t())
        BGStub.__init__(self, debug)
        bridge.rm_get_partitions(c_int(filter), byref(self.ptr))
        LazyRMSet.__init__(self, self, 'size', 'head', 'tail', Partition)

    def __del__(self):
        '''frees the partition_list_t pointer on delete'''
        bridge.rm_free_partition_list(self.ptr)

#     def refresh(self):
#         '''refreshes the bridge pointers using part.reload() individually'''
#         for part in self:
#             print 'reloading part', part.id
#             part.reload()

    def reload(self):
        '''loads the entire list again, updating pointers and clearing
        attrcaches along the way
        '''
        # clear the lookup cache so the head pointer isn't cached
        self.attrcache.clear()
        
        local_bridge = {}
        for bridgepart in self:
            local_bridge.update({bridgepart.id:bridgepart})
#         print "reloading", type(self.ptr)
        bridge.rm_free_partition_list(self.ptr)
        self.ptr = pointer(bgl_rm_api.rm_partition_list_t())
        bridge.rm_get_partitions(c_int(bgl_rm_api.PARTITION_ALL_FLAG),
                                 byref(self.ptr))

        # the class way
        head_ptr = getattr(self.object, self.hname)
        head = self.cclass(head_ptr)
        if head.id in local_bridge.keys():
            print 'updating ptr', local_bridge[head.id].ptr, head.ptr
            local_bridge[head.id].attrcache.clear()
            local_bridge[head.id].ptr = head.ptr
        else:
            self.data.append(head)

        for x in range(getattr(self.object, self.sname) - 1):
            # the class way
            tail = self.cclass(getattr(self.object, self.tname))
            print 'checking', tail.id
            if tail.id in local_bridge.keys():
                print 'updating ptr', local_bridge[tail.id].ptr, tail.ptr
                local_bridge[tail.id].attrcache.clear()
                local_bridge[tail.id].ptr = tail.ptr
            else:
                self.data.append(tail)

class NodeCardList(BGStub,LazyRMSet):
    """Builds a list of NodeCards given a basepartition.

    Uses the rm_get_nodecards function. Tags each NodeCard with it's
    basepartition id (.basepart)
    """
    __attrinfo__ = \
                 {'size': \
                  (bgl_rm_api.RM_NodeCardListSize, None, c_int, getvalue),
                  'head': \
                  (bgl_rm_api.RM_NodeCardListFirst, None,
                   bgl_rm_api.rm_element_t, passthru),
                  'tail': \
                  (bgl_rm_api.RM_NodeCardListNext, None,
                   bgl_rm_api.rm_element_t, passthru)}
    nocache = ['tail']

    def __init__(self, basepart=None, debug=1):
        if not basepart:
            raise Exception, "Must specify a base partition"

        BGStub.__init__(self, debug)
        self.ptr = pointer(bgl_rm_api.rm_nodecard_list_t())
        rc = bridge.rm_get_nodecards(basepart, byref(self.ptr))
        LazyRMSet.__init__(self, self, 'size', 'head', 'tail', NodeCard)
        #tag the nodecard with it's base partition id
        for nc in self:
            nc.basepart = basepart

if __name__ == '__main__':
    bg = BG()
    print 'base partition size %dx%dx%d' % (bg.BPsize['X'], bg.BPsize['Y'], bg.BPsize['Z'])
    print 'base partition num', bg.BPnum
#     ncsize = c_int()
#     bridge.rm_get_data(bg.ptr, bgl_rm_api.RM_NodeCardListSize, byref(ncsize))
#     print 'got ncsize of', ncsize.value

    joblist = JobList(debug=4)
    partlist = PartList(debug=4)
    #for wire in bg.wires:
    #    print wire.src.component, wire.src.id, "=>", wire.dst.component, wire.dst.id
    #for job in joblist:
    #    print job.id, job.user, job.partition, job.state

#     for bp in bg.basePartitions:
#         output = [getattr(bp, name) for name in bp.__attrinfo__]
#         Cobalt.Util.print_tabular([tuple(x) for x in \
#                                    [BasePartition.__attrinfo__.keys()] + \
#                                    [output]])

#         header = [x for x in ('id', 'bpid', 'cardionodes', 'cardpartid', 'quarter',
#                               'cardstate')]
#         output = [(nc.id, nc.basepart, nc.cardionodes, nc.cardpartid, nc.quarter,
#                    nc.cardstate) for nc in bp.nodecards]
#         Cobalt.Util.print_tabular([tuple(x) for x in [header] + output])

    header = ['basepart', 'id']
    output = []
    for part in partlist:
#         print [getattr(part, name) for name in \
#                ['id', 'description', 'small', 'connection', 'ramdisk']]
#         print part.psetsPerBP, part.Usersnum
#         for u in part.users:
#             print u.name

#         print part.id, part.NCnum, len(part.nodecards)
#         print part.id
#         for nc in part.nodecards:
#             output.append([getattr(nc, name) for name in header])
#         Cobalt.Util.print_tabular([tuple(x) for x in [header] + output])
#         output = []
#         print

#         for bp in part.basePartitions:
#             print [getattr(bp, name) for name in bp.__attrinfo__]
        if part.id == 'test32_R000_J102':
            print 'before modification', part.user, part.description
            if part.user == 'nobody':
                part.user = 'voran'
            else:
                part.user = 'nobody'
            if part.description == 'changed by pyBridge':
                part.description = 'modified by pyBridge'
            else:
                part.description = 'changed by pyBridge'
            print 'user' in part.attrcache
            print part.attrcache
            partlist.__freepartlist__()
            print 'after modification and inline flush "%s" "%s"' % (part.user, part.description)
#             part.user = 'nobody'
#             break

#     partlist.__freepartlist__()
#     for part in partlist:
#         if part.id == 'test32_R000_J102':
#             if 'description' in part.attrcache:
#                 print 'description in attrcache'
#                 del part.attrcache['description']
#             print 'after flush: checking if description cached', part.description
#             print 'user says', part.user

    header = ['id', 'pid', 'user', 'partition', 'state']
    output = []
    for job in joblist:
        output.append([getattr(job, name) for name in header])

    print "\nJobs\n"
    Cobalt.Util.print_tabular([tuple(x) for x in [header] + output])
    
