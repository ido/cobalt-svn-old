#!/usr/bin/env python

'''Super-Simple Scheduler for BG/L'''
__revision__ = '$Revision$'

import logging, math, sys, time
import Cobalt.Component, Cobalt.Data, Cobalt.Logging, Cobalt.Proxy, Cobalt.Util

import Cobalt.SchedulerPolicies

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

class Reservation(Cobalt.Data.Data):
    '''Reservation\nHas attributes:\nname, start, stop, cycle, users, resources'''
    def Overlaps(self, location, start, duration):
        '''check job overlap with reservations'''
        if location not in self.locations:
            return False
        if self.start <= start <= self.stop:
            return True
        elif self.start <= (start + duration) <= self.stop:
            return True
        if self.cycle == 0:
            return False
        # 3 cases, front, back and complete coverage of a cycle
        cstart = math.floor((start - self.start) / self.cycle)
        if cstart <= start <= (cstart + self.duration):
            return True
        cend = math.floor(((start + duration) - self.start) / self.cycle)
        if cend <= (start + duration) <= (cend + self.duration):
            return True
        if duration >= self.cycle:
            return True
        return False

    def IsActive(self, stime=False):
        if not stime:
            stime = time.time()
        if self.start <= stime <= self.stop:
            return True

    def FilterPlacements(self, placements, resources):
        '''Filter placements not allowed by reservation'''
        overlaps = resources.GetOverlaps(self.location)
        now = time.time()
        # filter overlapping jobs not in reservation
        for job in placements:
            if job.queue.startswith("R.%s" % self.name):
                if job.user not in self.users:
                    del placements[job]
                    continue
                placements[job] = [location for location in \
                                   placements[job] if location in \
                                   self.location]
            for location in placements[job][:]:
                if location in overlaps:
                    if self.Overlaps(location, now, job.duration):
                        placements[job].remove(location)
        if not self.IsActive():
            # filter jobs in Rqueue if not active
            if "R.%s" % self.name in placements.keys():
                del placements["R.%" % self.name]

class ReservationSet(Cobalt.Data.DataSet):
    __object__ = Reservation

    def CreateRQueue(self, reserv):
        queues = comm['qm'].GetQueues([{'tag':'queue', 'name':'*'}])
        qnames = [q['name'] for q in queues]
        if "R.%s" % reserv.name not in qnames:
            logger.info("Adding reservation queue R.%s" % (reserv.name))
            spec = [{'tag':'queue', 'name': 'R.%s' % (reserv.name)}]
            attrs = {'state':'running', 'users': reserv.users}
            try:
                comm['qm'].AddQueue(spec)
                comm['qm'].SetQueues(spec, attrs)
            except Exception, e:
                logger.error("Queue setup for %s failed: %s" \
                             % ("R.%s" % reserv.name, e))

    def DeleteRQueue(self, reserv):
        queues = comm['qm'].GetQueues([{'tag':'queue', 'name':'*'}])
        qnames = [q['name'] for q in queues]
        rqn = "R.%s" % reserv.name
        if rqn in qnames:
            logger.info("Disabling Rqueue %s" % (rqn))
            try:
                response = comm['qm'].SetQueues([{'tag':'queue',
                                                  'name':rqn}],
                                                {'state':'dead'})
            except Exception, e:
                logger.error("Disable request failed: %s" % e)

    def Add(self, cdata, callback=None, cargs={}):
        Cobalt.Data.DataSet.Add(self, cdata, self.CreateRQueue, cargs)
        
    def Del(self, cdata, callback=None, cargs={}):
        Cobalt.Data.DataSet.Del(self, cdata, self.DeleteRQueue, cargs)

class Partition(Cobalt.Data.ForeignData):
    '''Partitions are allocatable chunks of the machine'''
    def CanRun(self, job):
        '''Check that job can run on partition with reservation constraints'''
        basic = self.scheduled and self.functional
        queue = job.queue.startswith('R.') or \
                job.queue in self.queue.split(':')
        jsize = int(job.nodes) 
        psize = int(self.size)
        size = (psize >= jsize) and ((psize == 32) or (jsize > psize/2))
        if not (basic and size):
            return False
        return queue

class PartitionSet(Cobalt.Data.DataSet):
    __object__ = Partition
    __failname__ = 'System Connection'
    __function__ = comm['system'].GetPartitions
    __fields__ = ['name', 'queue', 'nodecards']
    __unique__ = 'name'

    def GetOverlaps(self, partnames):
        ncs = []
        for part in partnames:
            [ncs.append(nc) for nc in part.nodecards if nc not in ncs]
        ret = []
        for part in self:
            if [nc for nc in part.nodecards if nc in ncs]:
                ret.append(part)
        return ret

class Job(Cobalt.Data.ForeignData):
    '''This class represents User Jobs'''
    def __init__(self, element):
        Cobalt.Data.ForeignData.__init__(self, element)
        self.partition = 'none'
        logger.info("Job %s/%s: Found new job" % (self.jobid, self.user))

class JobSet(Cobalt.Data.ForeignDataSet):
    __object__ = Job
    __unique__ = 'jobid'
    __oserror__ = Cobalt.Util.FailureMode("QM Connection")
    __function__ = comm['qm'].GetJobs
    __fields__ = ['nodes', 'location', 'jobid', 'state', 'index',
                  'walltime', 'queue', 'user']

class Queue(Cobalt.Data.ForeignData):
    def LoadPolicy(self):
        '''Instantiate queue policy modules upon demand'''
        if self.policy not in Cobalt.SchedulerPolicies.names:
            logger.error("Cannot load policy %s for queue %s" % \
                         (self.policy, self.name))
        else:
            pclass = Cobalt.SchedulerPolicies.names[self.policy]
            self.pcls = pclass()

class QueueSet(Cobalt.Data.ForeignDataSet):
    __object__ = Queue
    __unique__ = 'name'
    __function__ = comm['qm'].GetQueues
    __fields__ = ['name', 'status', 'policy']

    def Sync(self):
        qp = [(q.name, q.policy) for q in self]
        Cobalt.Data.ForeignDataSet.Sync()
        [q.LoadPolicy() for q in self if (q.name, q.policy) not in qp]

class BGSched(Cobalt.Component.Component):
    '''This scheduler implements a fifo policy'''
    __implementation__ = 'bgsched'
    __name__ = 'scheduler'
    __statefields__ = ['reservations']
    __schedcycle__ = 10
    async_funcs = ['assert_location', 'RunQueue',
                   'RemoveOldReservations', 'ResQueueSync']

    def __init__(self, setup):
        self.jobs = JobSet()
        self.queues = QueueSet()
        self.reservations = ReservationSet()
        self.resources = PartitionSet()
        Cobalt.Component.Component.__init__(self, setup)
        self.executed = []
        self.lastrun = 0
        self.register_function(self.reservations.Add, "AddReservation")
        self.register_function(self.reservations.Del, "DelReservation")
        self.register_function(
            lambda a,d,u: \
            self.reservations.Get(d, lambda r, na:r.update(na), u), 
            "SetReservation")

    def SyncData(self):
        for item in [self.resources, self.queues, self.jobs]:
            item.Sync()

    def Schedule(self):
        # self queues contains queues
        activeq = []
        for q in self.queues:
            if q.name.startswith('R.'):
                if True in \
                       [rm.Active() for rm in \
                        self.reservations.Match({'name':q.name[2:]})]:
                    activeq.append(q.name)
            else:
                if q.state == 'running':
                    activeq.append(q.name)
        print "activeq:", activeq
        # self.jobs contains jobs
        activej = [j for j in self.jobs if j.queue in activeq \
                   and j.state == 'queued']
        print "activej:", activej
        potential = {}
        for job in activej:
            potential[job] = []
            for part in [part for part in self.resources if part.CanRun(job)]:
                potential[job].append(part)
        # FIXME need to check reservation conflict
        viable = []
        [viable.extend(queue.keys()) for queue in potential.values()]
        viable.sort(fifocmp)
        potential = {}
        for job in viable:
            potential[job] = []
            [potential[job].append(partition) for partition \
             in self.resources if partition.CanRun(job)]
        placements = []
        # call all queue policies
        [q.policy.Prepare(viable, potential) for q in self.queues]
        # place all viable jobs
        for job in viable:
            QP = self.queues[job.queue].policy
            place = QP.PlaceJob(job, potential)
            if place:
                # clean up that job placement
                del potential[job.queue][job.jobid]
                # tidy other placements
                self.TidyPlacements(potential, place[1])
                placements.append(place)
        self.RunJobs(placements)

    def TidyPlacements(self, potential, newlocation):
        '''Remove any potential spots that overlap with newlocation'''
        nodecards = [res for res in self.resources \
                     if res.name in newlocation[0].nodecards]
        overlap = [res.name for res in self.resources \
                   if [nc for nc in res.nodecards if nc in nodecards]]
        for queue in potential:
            for job, locations in queue.iteritems():
                [locations.remove(location) for location in locations \
                 if location in overlap]
                if not locations:
                    del queue[job]

    def RunJobs(self, placements):
        '''Connect to cqm and run jobs'''
        for job, part in placements.iteritems():
            jspec = [{'tag':'job', 'jobid':job.id}]
            comm['qm'].RunJobs(jspec, [part.name])

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
    

