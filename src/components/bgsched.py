#!/usr/bin/env python

'''Super-Simple Scheduler for BG/L'''
__revision__ = '$Revision$'

from datetime import datetime
import copy, logging, sys, time, xmlrpclib, ConfigParser
import Cobalt.Component, Cobalt.Data, Cobalt.Logging, Cobalt.Proxy, Cobalt.Util

if '--nodb2' not in sys.argv:
    import DB2

logger = logging.getLogger('bgsched')

comm = Cobalt.Proxy.CommDict()

def fifocmp(job1, job2):
    '''Compare 2 jobs for fifo mode'''
    if job1.get('index', False):
        j1 = int(job1.get('index'))
    else:
        j1 = int(job1.get('jobid'))
    if job2.get('index', False):
        j2 = int(job2.get('index'))
    else:
        j2 = int(job2.get('jobid'))
    return cmp(j1, j2)

class FailureMode(object):
    '''FailureModes are used to report (and supress) errors appropriately
    call Pass() on success and Fail() on error'''
    def __init__(self, name):
        self.name = name
        self.status = True

    def Pass(self):
        '''Check if status was previously failure and report OK status if needed'''
        if not self.status:
            logger.error("Failure %s cleared" % (self.name))
            self.status = True

    def Fail(self):
        '''Check if status was previously success and report failed status if needed'''
        if self.status:
            logger.error("Failure %s occured" % (self.name))
            self.status = False

def filterByTopology(placements, depinfo, potential):
    '''Filter out all potential placements that overlap with already allocated partitions'''
    used = []
    for loc in [loc for (_, loc) in placements]:
        used.append(loc)
        used += [part for part in depinfo[loc][0] + depinfo[loc][1]]
        for block in used:
            for job, places in potential.iteritems():
                if block in [p.get('name') for p in places]:
                    potential[job].remove([b for b in potential[job] \
                                           if b.get('name')==block][0])
        for job in [job for job in potential if not potential[job]]:
            del potential[job]

def filterByLength(potential, length):
    '''Filter out all potential placements for jobs longer than length'''
    if length == -1:
        return
    for job in potential.keys():
        if float(job.get('walltime')) > float(length):
            del potential[job]
            
class Partition(Cobalt.Data.Data):
    '''Partitions are allocatable chunks of the machine'''
    _config = ConfigParser.ConfigParser()
    _config.read(['/etc/cobalt.conf'])
    try:
        min_psize = int(_config.get('system', 'minpsize'))
    except:
        min_psize = 32

    def __init__(self, element):
        Cobalt.Data.Data.__init__(self, element)
        if 'state' not in element.keys():
            self.set('state', 'idle')
        if 'reservations' not in element.keys():
            self.set('reservations', [])
        self.job = 'none'
        self.rcounter = 1
        if 'db2' not in element.keys():
            self.set('db2', 'XX')

    def isIdle(self):
        '''Return True if partition is idle'''
        if '--nodb2' not in sys.argv:
            return self.get('state') == 'idle' and self.get('db2') == 'F'
        else:
            return self.get('state') == 'idle'

    def CanRun(self, job):
        '''Check that job can run on partition with reservation constraints'''
        basic = self.get('scheduled') and self.get('functional')
        queue = job.get('queue') in self.get('queue').split(':')
        jqueue = job.get('queue')
        jsize = int(job.get('nodes')) # should this be 'size' instead?
        psize = int(self.get('size'))
        size = ((psize >= jsize) and \
                ((psize == self.min_psize) or (jsize > psize/2)))
        if not (basic and size):
            return False
        # add a slack for job cleanup with reservation calculations
        wall = float(job.get('walltime')) + 5.0
        jdur = 60 * wall
        # all times are in seconds
        current = time.time()
        rstates = []
        for (rname, ruser, start, rdur) in self.get('reservations'):
            if current < start:
                # reservation has not started
                if start < (current + jdur):
                    return False
            elif current > (start + rdur):
                # reservation has finished
                continue
            else:
                # reservation is active
                rstates.append(jqueue == ('R.%s' % (rname))
                               and job.get('user') in ruser.split(':'))
        if rstates:
            return False not in rstates
        else:
            return queue
        return True

    def PlaceJob(self, job):
        '''Allocate this partition for Job'''
        logger.info("Job %s/%s: Scheduling job %s on partition %s" % (
            job.get('jobid'), job.get('user'), job.get('jobid'),
            self.get('name')))
        self.job = job.get('jobid')
        self.set('state', 'busy')

    def Free(self):
        '''DeAllocate partition for current job'''
        logger.info("Job %s: Freeing partition %s" % (self.job, self.get('name')))
        self.job = 'none'
        self.set('state', 'idle')

class Job(Cobalt.Data.Data):
    '''This class represents User Jobs'''
    def __init__(self, element):
        Cobalt.Data.Data.__init__(self, element)
        self.partition = 'none'
        logger.info("Job %s/%s: Found new job" % (self.get('jobid'),
                                                       self.get('user')))

    def Place(self, partition):
        '''Build linkage to execution partition'''
        self.partition = partition.get('name')
        self.set('state', 'running')

    def Sync(self, data):
        upd = [(k, v) for (k, v) in data.iteritems() \
               if k != 'tag' and self.get(k) != v]
        if upd:
            logger.info("Resetting job %s parameters %s" % \
                        (self.get('jobid'), ':'.join([u[0] for u in upd])))
            for (k, v) in upd:
                self.set(k, v)

class PartitionSet(Cobalt.Data.DataSet):
    __object__ = Partition

    _configfields = ['db2uid', 'db2dsn', 'db2pwd']
    _config = ConfigParser.ConfigParser()
    if '-C' in sys.argv:
        _config.read(sys.argv[sys.argv.index('-C') + 1])
    else:
        _config.read('/etc/cobalt.conf')
    if not _config._sections.has_key('bgsched'):
        print '''"bgsched" section missing from cobalt config file'''
        raise SystemExit, 1
    config = _config._sections['bgsched']
    mfields = [field for field in _configfields if not config.has_key(field)]
    if mfields:
        print "Missing option(s) in cobalt config file: %s" % (" ".join(mfields))
        raise SystemExit, 1

    qpolicy = {'default':'PlaceFIFO', 'scavenger':'PlaceScavenger',
               'high-prio':'PlaceSpruce'}

    def __init__(self):
        Cobalt.Data.DataSet.__init__(self)
        if '--nodb2' not in sys.argv:
            try:
                import DB2
                conn = DB2.connect(uid=self.config.get('db2uid'), pwd=self.config.get('db2pwd'),
                                   dsn=self.config.get('db2dsn'))
                self.db2 = conn.cursor()
            except:
                print "Failed to connect to DB2"
                raise SystemExit, 1
        self.jobs = []
        self.qmconnect = FailureMode("QM Connection")

    def __getstate__(self):
        return {'data':copy.deepcopy(self.data), 'jobs':copy.deepcopy(self.jobs)}

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.qmconnect = FailureMode("QM Connection")
        if '--nodb2' not in sys.argv:
            import DB2
            self.db2 = DB2.connect(uid=self.config.get('db2uid'), pwd=self.config.get('db2pwd'),
                                   dsn=self.config.get('db2dsn')).cursor()

    def Schedule(self, jobs):
        '''Find new jobs, fit them on a partitions'''
        knownjobs = [job.get('jobid') for job in self.jobs]
        logger.debug('Schedule: knownjobs %s' % knownjobs)
        activejobs = [job.get('jobid') for job in jobs]
        finished = [jobid for jobid in knownjobs if jobid not in activejobs]
        #print "known", knownjobs, "active", activejobs,
        # "finished", finished
        # add new jobs
        #print jobs
        [self.jobs.append(Job(jobdata)) for jobdata in jobs \
         if jobdata.get('jobid') not in knownjobs]
        # delete finished jobs
        [self.jobs.remove(job) for job in self.jobs \
         if job.get('jobid') in finished]
        # sync existing parameters
        for jdata in jobs:
            try:
                [currjob] = [j for j in self.jobs
                             if j.get('jobid') == jdata.get('jobid')]
            except:
                continue
            currjob.Sync(jdata)
        # free partitions with nonexistant jobs
        [partition.Free() for partition in self.data \
         if partition.job not in activejobs + ['none']]
        # find idle partitions for new jobs
        # (idle, functional, and scheduled)
        candidates = [part for part in self.data \
                      if part.get('state') == 'idle' and
                      part.get('functional') and part.get('scheduled')]
        # find idle jobs
        idlejobs = [job for job in self.jobs if job.get('state') == 'queued']
        # filter for stopped and dead queues
        try:
            stopped_queues = comm['qm'].GetQueues([{'tag':'queue', 'name':'*', 'smartstate':'stopped'}])
            dead_queues = comm['qm'].GetQueues([{'tag':'queue', 'name':'*', 'state':'dead'}])
        except xmlrpclib.Fault:
            self.qmconnect.Fail()
            return 0
        self.qmconnect.Pass()
        logger.debug('stopped queues %s' % stopped_queues)
        idlejobs = [job for job in idlejobs if job.get('queue') not \
                    in [q.get('name') for q in stopped_queues + dead_queues]]

        #print "jobs:", self.jobs
        if candidates and idlejobs:
            logger.debug("initial candidates: %s" % ([cand.get('name') for cand in candidates]))
            #print "Actively checking"
            if '--nodb2' not in sys.argv:
                try:
                    sys_type = self._config.get('system', 'bgtype')
                except:
                    sys_type = 'bgl'
                if sys_type == 'bgp':
                    self.db2.execute("select blockid, status from bgpblock;")
                else:
                    self.db2.execute("select blockid, status from bglblock;")
                results = self.db2.fetchall()
                for (pname, state) in results:
                    partname = pname.strip()
                    partinfo = [part for part in self.data if part.get('name') == partname]
                    if partinfo:
                        partinfo[0].set('db2', state)

                for partition in [part for part in self.data if part.get('db2', 'XXX') == 'XXX']:
                    logger.error("DB2 has no state for partition %s" % (partition.get('name')))

                # check for discrepancies between candidates and db2
                for part in [part for part in candidates if part.get('db2') != 'F']:
                    foundlocation = [job for job in jobs if job.get('location') == part.get('name')]
                    if foundlocation:
                        part.job = foundlocation[0].get('jobid')
                        part.set('state', 'busy')
                        logger.error("Found job %s on Partition %s. Manually setting state." % \
                                     (foundlocation[0].get('jobid'), part.get('name')))
                    else:
                        logger.error('Partition %s in inconsistent state' % (part.get('name')))
                    candidates.remove(part)
            #print "after db2 check"

            # now we get dependency info
            depsrc = [part.to_rx({'tag':'partition', 'name':'*', 'deps':'*'}) for part in self.data]
            depinfo = Cobalt.Util.buildRackTopology(depsrc)

            # kill for deps already in use
            # deps must be idle, and functional

            # first, get busy partition names
            busy_part_names = [part.get('name') for part in self.data if not part.isIdle() and
                               part.get('functional')]
            candidates = [part for part in candidates
                          if not [item for item in depinfo[part.get('name')][1] if item in busy_part_names]]

            logger.debug("cand1 %s" % ([part.get('name') for part in candidates]))
            # need to filter out contained partitions
            candidates = [part for part in candidates
                          if not [block for block in depinfo[part.get('name')][0]
                                  if block in busy_part_names]]

            logger.debug("cand2 %s" % ([part.get('name') for part in candidates]))
            # now candidates are only completely free blocks
            potential = {}
            for job in idlejobs:
                potential[job] = [part for part in candidates if part.CanRun(job)]
                if not potential[job]:
                    del potential[job]
            return self.ImplementPolicy(potential, depinfo)
        else:
            return []

    def QueueCMP(self, q1, q2):
        if self.qpol.get(q1, 'default') == 'high-prio':
            return -1
        if self.qpol.get(q2, 'default') == 'high-prio':
            return 1
        return 0

    def ImplementPolicy(self, potential, depinfo):
        '''Switch between queue policies'''
        qpotential = {}
        placements = []
        for job in potential:
            if qpotential.has_key(job.get('queue')):
                qpotential[job.get('queue')][job] = potential[job]
            else:
                qpotential[job.get('queue')] = {job:potential[job]}
        self.qpol = {}
        # get queue policies
        try:
            qps = comm['qm'].GetQueues([{'tag':'queue',
                                         'name':'*', 'policy':'*'}])
            self.qmconnect.Pass()
        except:
            self.qmconnect.Fail()
            return []
        # if None, set default
        for qinfo in qps:
            if qinfo.get('policy', None) != None:
                self.qpol[qinfo['name']] = qinfo['policy']
            else:
                self.qpol[qinfo['name']] = 'default'
        queues = self.qpol.keys()
        queues.sort(self.QueueCMP)
        for queue in queues:
            if queue not in qpotential:
                qpotential[queue] = {}
            qp = self.qpolicy.get(self.qpol[queue], 'default')
            qfunc = getattr(self, qp, 'default')
                            
            # need to remove partitions, included and containing,
            # for newly used partitions
            # for all jobs in qpotential
            filterByTopology(placements, depinfo, qpotential[queue])
            newplace = qfunc(qpotential, queue, depinfo)
            placements += newplace
        return placements

    def PlaceFIFO(self, qpotential, queue, depinfo):
        '''Return a set of placements that patch a basic FIFO+backfill policy'''
        placements = []
        potential = qpotential[queue]
        # update queuestate from cqm once per Schedule cycle
        try:
            queuestate = comm['qm'].GetJobs([{'tag':'job', 'jobid':'*', 'index':'*',
                                              'state':'*', 'nodes':'*',
                                              'queue':'*', 'user':'*'}])
        except xmlrpclib.Fault:
            self.qmconnect.Fail()
            return 0
        self.qmconnect.Pass()
        while potential:
            # get lowest jobid and place on first available partition
            jobs = potential.keys()
            jobs.sort(fifocmp)
            newjob = jobs[0]
            
            # filter here for runtime restrictions
            try:
                comm['qm'].CanRun(queuestate, newjob._attrib)
            except xmlrpclib.Fault, flt:
                if flt.faultCode == 30:
                    logger.debug('Job %s/%s cannot run in queue because %s' %
                                 (newjob.get('jobid'), newjob.get('user'), flt.faultString))
                    del potential[newjob]
                    continue
                else:
                    self.qmconnect.Fail()
                    return 0
            self.qmconnect.Pass()
            logger.debug('Job %s/%s accepted to run' % (newjob.get('jobid'), newjob.get('user')))
            location = potential[newjob][0]
            location.PlaceJob(newjob)
            newjob.Place(location)
            # update local state of job for use in this schedule cycle
            for j in queuestate:
                if j.get('jobid') == newjob.get('jobid') and j.get('queue') == newjob.get('queue'):
                    j.update({'state':'running'})
            placements.append((newjob.get('jobid'), location.get('name')))
            del potential[newjob]

            # now we need to remove location (and dependencies and all
            # partitions containing it) from potential lists
            filterByTopology(placements, depinfo, potential)
        return placements

    def PlaceScavenger(self, qpotential, queue, depinfo):
        '''A really stupid priority queueing mechanism that starves lo queue jobs if the high-queue has idle jobs'''
        live = [job.get('queue') for job in self.jobs if job.get('state') == 'queued']
        if live.count(queue) != len(live):
            return []
        return self.PlaceFIFO(qpotential[queue], depinfo)

    def PlaceSpruce(self, qpotential, queue, depinfo):
        '''Defer other jobs which spruce queue has idle jobs'''
        idle = [job for job in self.jobs if job.get('queue') == queue \
                  and job.get('state') == 'queued']
        p = self.PlaceFIFO(qpotential, queue, depinfo)
        if len(p) != len(idle):
            # we have idle jobs, so defer others
            for q in qpotential:
                qpotential[q] = {}
        return p
                
class BGSched(Cobalt.Component.Component):
    '''This scheduler implements a fifo policy'''
    __implementation__ = 'bgsched'
    __name__ = 'scheduler'
    #__statefields__ = ['partitions', 'jobs']
    __statefields__ = ['partitions', 'log_state']
    __schedcycle__ = 10
    async_funcs = ['assert_location', 'RunQueue',
                   'RemoveOldReservations', 'ResQueueSync', 'CheckReservations']

    def __init__(self, setup):
        self.partitions = PartitionSet()
        self.jobs = []
        Cobalt.Component.Component.__init__(self, setup)
        self.executed = []
        self.qmconnect = FailureMode("QM Connection")
        self.lastrun = 0
        self.pbslog = Cobalt.Util.PBSLog()
        self.log_state = dict(
            reservation_begun = dict(),
        )
        self.register_function(lambda  address,
                               data:self.partitions.Get(data),
                               "GetPartition")
        self.register_function(lambda  address,
                               data:self.partitions.Add(data),
                               "AddPartition")
        self.register_function(lambda  address,
                               data:self.partitions.Del(data),
                               "DelPartition")
        self.register_function(lambda address, data, updates:
                               self.partitions.Get(data, lambda part, newattr:part.update(newattr), updates),
                               'Set')  
        self.register_function(self.AddReservation, "AddReservation")
        self.register_function(self.ReleaseReservation, "DelReservation")
        self.register_function(self.SetReservation, "SetReservation")
    
    def GetReservations(self):
        '''build a list of reservation names in use'''
        reservs = []
        names = []
        for partition in self.partitions:
            rinfo = partition.get('reservations')
            if rinfo:
                for res in rinfo:
                    if res[0] not in names:
                        names.append(res[0])
                        reservs.append(res)
        return reservs
    
    def CheckReservations (self):
        current_time = time.time()
        for reservation in self.GetReservations():
            name, user, start, duration = reservation
            if start <= current_time and ((name, start) not in self.log_state['reservation_begun'].keys() or not self.log_state['reservation_begun'][(name, start)]):
                self.log_state['reservation_begun'][(name, start)] = True
                self.pbslog.log("B", name, datetime=datetime.fromtimestamp(start),
                    owner = user or "N/A", # name of party who submitted the resource reservation request
                    name = name, # optional reservation name
                    #account = , # optional accounting string
                    #queue = , # name of the instantiated reservation queue or the name of the queue of the reservation-job
                    #ctime = , # time at which the resource reservation was created
                    start = int(start), # time at which the reservation period is to start
                    end = int(start + duration), # time at which the reservation period is to end
                    duration = int(duration), # duration specified or computed for the resource reservation
                    #exec_host = , #nodes and node-associated resources
                    #authorized_users = , #the list of acl_users on the queue that is instantiated to service the reservation
                    #authorized_groups = , if specified, the list of acl_groups on the queue that is instantiated to service the reservation
                    #authorized_hosts = , if specified, the list of acl_hosts on the queue that is instantiated to service the reservation
                    #Resource_List__dot__RES, # list of resources requested by the reservation
                )

    def SetReservation(self,  _, spec, name, user, start, duration):
        '''updates reservations'''
        for s in spec:
            s.update({'reservations':'*'})
        affected_partitions = self.partitions.Get(spec)
        resv_updates = []
        for ap in affected_partitions:
            for res in ap['reservations']:
                if res[0] == name:
                    datetime = datetime.now()
                    ap['reservations'].remove(res)
                    self.pbslog.log("K", res[0], datetime=datetime,
                        requester = user or "N/A", # who deleted the resource reservation
                    )
                    self.pbslog.log("U", name, datetime=datetime,
                        requester = user or "N/A", # who requested the resources reservation
                    )
                    ap['reservations'].append((name, user, start, duration))
                    self.pbslog.log("Y", name, datetime=datetime,
                        requester = user or "N/A", # who requested the resource reservation
                    )
                    resv_updates.append((name, user, start, duration))
        #now update queues
        self.ResQueueSync(updates=resv_updates)
        return affected_partitions

    def ResQueueSync(self, updates=[]):
        '''Create any needed rqueues, update attributes, and kill
        unneeded rqueues'''
        queues = comm['qm'].GetQueues([{'tag':'queue', 'name':'*'}])
        qnames = [q['name'] for q in queues]
        update_names = [r[0] for r in updates]
        
        for reserv in self.GetReservations():
            #adding reservation queue
            if "R.%s" % (reserv[0]) not in qnames:
                logger.info("Adding reservation queue R.%s" % (reserv[0]))
                spec = [{'tag':'queue', 'name': 'R.%s' % (reserv[0])}]
                attrs = {'state':'running', 'users': reserv[1]}
                try:
                    comm['qm'].AddQueue(spec)
                    comm['qm'].SetQueues(spec, attrs)
                except Exception, e:
                    logger.error("Queue setup for %s failed: %s" \
                                 % ("R.%s" % reserv[0], e))
            #updating reservation queue
            elif reserv[0] in update_names:
                logger.info("Updating reservation queue R.%s" % (reserv[0]))
                spec = [{'tag':'queue', 'name': 'R.%s' % (reserv[0])}]
                attrs = {'users': reserv[1]}
                try:
                    comm['qm'].SetQueues(spec, attrs)
                except Exception, e:
                    logger.error("Queue setup for %s failed: %s" \
                                 % ("R.%s" % reserv[0], e))

        rnames = [r[0] for r in self.GetReservations()]
        for qn in qnames:
            if qn.startswith("R.") and qn[2:] not in rnames:
                logger.info("Disabling Rqueue %s" % (qn))
                try:
                    response = comm['qm'].SetQueues([{'tag':'queue', 'name':qn}],
                                                    {'state':'dead'})
                except Exception, e:
                    logger.error("Disable request failed: %s" % e)

    def AddReservation(self, _, spec, name, user, start, duration):
        '''Add a reservation to matching partitions'''
        self.pbslog.log("U", name,
            requester = user or "N/A", # who requested the resources reservation
        )
        reservation = (name, user, start, duration)
        data = self.partitions.Get(spec, callback=lambda x,
                                   y:x.get('reservations').append(reservation))
        self.ResQueueSync()
        self.pbslog.log("Y", name,
            requester = user or "N/A", # who requested the resources reservation
        )
        return data
    
    def ReleaseReservation(self, _, spec, name, user=None):
        '''Release specified reservation'''
        def cb (x, y):
            reservations = x.get('reservations')
            for rsv in reservations:
                if rsv[0] == name:
                    reservations.remove(rsv)
                    self.pbslog.log("k", name,
                        requester = user or rsv[1] or "N/A",
                    )
        data = self.partitions.Get(spec, cb)
        self.ResQueueSync()
        return data

    def RemoveOldReservations(self):
        '''Release all reservations that have expired'''
        for partition in self.partitions:
            for reservation in partition.get('reservations'):
                current_time = time.time()
                if (reservation[2] + reservation[3]) < current_time:
                    partition.get('reservations').remove(reservation)
                    self.pbslog.log("F", reservation[0], datetime=datetime.fromtimestamp(current_time),
                        # no attributes
                    )
        self.ResQueueSync()

    def SupressDuplicates(self, provisional):
        '''Prevent duplicate job start requests from being generated'''
        locations = [pro[1] for pro in provisional]
        for (jobid, location) in provisional:
            if jobid in self.executed:
                logger.error("Tried to execute job %s multiple times" % (jobid))
                provisional.remove((jobid, location))
                [partition.Free() for partition in self.partitions if partition.get('name') == location]
            elif locations.count(location) > 1:
                logger.error("Tried to use the same partition multiple times")
                provisional.remove((jobid, location))
                locations.remove(location)
            else:
                self.executed.append(jobid)
            
    def RunQueue(self):
        '''Process changes to the cqm queue'''
        since = time.time() - self.lastrun
        if since < self.__schedcycle__:
            return
        try:
            jobs = comm['qm'].GetJobs([{'tag':'job', 'nodes':'*', 'location':'*',
                                        'jobid':'*', 'state':'*', 'index':'*',
                                        'walltime':'*', 'queue':'*', 'user':'*'}])
        except xmlrpclib.Fault:
            self.qmconnect.Fail()
            return 0
        except:
            self.logger.error("Unexpected fault during queue fetch", exc_info=1)
            return 0
        self.qmconnect.Pass()
        active = [job.get('jobid') for job in jobs]
        logger.debug("RunQueue: active jobs %s" % active)
        for job in [j for j in self.jobs if j.get('jobid') not in active]:
            logger.info("Job %s/%s: gone from qm" % (job.get('jobid'), job.get('user')))
            self.jobs.remove(job)
        # known is jobs that are already registered
        known = [job.get('jobid') for job in self.jobs]
        [partition.Free() for partition in self.partitions if partition.job not in known + ['none']]
        newjobs = [job for job in jobs if job.get('jobid') not in known]
        logger.debug('RunQueue: newjobs %s' % newjobs)
        self.jobs.extend([Job(job) for job in newjobs])
        logger.debug('RunQueue: after extend to Job %s' % self.jobs)
        placements = self.partitions.Schedule(jobs)
        if '-t' not in sys.argv:
            self.SupressDuplicates(placements)
            for (jobid, part) in placements:
                try:
                    comm['qm'].RunJobs([{'tag':'job', 'jobid':jobid}], [part])
                    pass
                except:
                    logger.error("failed to connect to the queue manager to run job %s" % (jobid))
        else:
            print "Jobs would be placed on:", placements
        self.lastrun = time.time()

if __name__ == '__main__':
    from getopt import getopt, GetoptError
    try:
        (opts, arguments) = getopt(sys.argv[1:], 'C:dD:t', ['nodb2'])
    except GetoptError, msg:
        print "%s\nUsage:\nbgsched.py [-t] [-C configfile] [-d] [-D <pidfile>] [--nodb2]" % (msg)
        raise SystemExit, 1
    try:
        daemon = [x[1] for x in opts if x[0] == '-D'][0]
    except:
        daemon = False
    if len([x for x in opts if x[0] == '-d']):
        dlevel = logging.DEBUG
    else:
        dlevel = logging.INFO
    Cobalt.Logging.setup_logging('bgsched', level=dlevel)
    server = BGSched({'configfile':'/etc/cobalt.conf', 'daemon':daemon})
    server.serve_forever()
    

