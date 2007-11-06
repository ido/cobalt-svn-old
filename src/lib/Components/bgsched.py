#!/usr/bin/env python

'''Super-Simple Scheduler for BG/L'''
__revision__ = '$Revision$'

import logging
import math
import sys
import time
import Cobalt.Logging, Cobalt.Util

from Cobalt.Data import Data, ForeignData, ForeignDataDict
from Cobalt.Components.base import Component, exposed, automatic, query
from Cobalt.Proxy import ComponentProxy, ComponentLookupError

import Cobalt.SchedulerPolicies

logger = logging.getLogger("Cobalt.Components.scheduler")


class Reservation (Data):
    
    """Cobalt scheduler reservation."""
    
    fields = Data.fields.copy()
    fields.update(dict(
        tag = "reservation",
        name = None,
        start = None,
        duration = None,
        cycle = None,
        users = None,
        partitions = None,
    ))
    
    required_fields = ["name", "start", "duration"]
    
    def __init__ (self, *args, **kwargs):
        Data.__init__(self, *args, **kwargs)
        if self.partitions is None:
            self.partitions = []
        if self.users is None:
            self.users = []
    
    def overlaps(self, partition, start, duration):
        '''check job overlap with reservations'''
        if start + duration < self.start:
            return False

        part_list = self.partitions.split(":")
        no_overlap = True
        for part_name in part_list:
            if part_name==partition.name or part_name in partition.children or part_name in partition.parents:
                no_overlap = False
                break
        if no_overlap:
            return False

        if self.cycle and duration >= self.cycle:
            return True

        my_stop = self.start + self.duration
        if self.start <= start < my_stop:
            return True
        elif self.start <= (start + duration) < my_stop:
            return True
        if not self.cycle:
            return False
        
        # 3 cases, front, back and complete coverage of a cycle
        cstart = (start - self.start) % self.cycle
        cend = (start + duration - self.start) % self.cycle
        if cstart < self.duration:
            return True
        if cend < self.duration:
            return True
        if cstart > cend:
            return True
        
        return False

    def is_active(self, stime=False):
        if not stime:
            stime = time.time()
            
        if stime < self.start:
            return False
        
        if self.cycle:
            now = (stime - self.start) % self.cycle
        else:
            now = stime - self.start    
        if now <= self.duration:
            return True


class ReservationDict (Cobalt.Data.DataDict):
    
    item_cls = Reservation
    key = "name"
    
    def q_add (self, *args, **kwargs):
        reservations = Cobalt.Data.DataDict.q_add(self, *args, **kwargs)
        qm = ComponentProxy("queue-manager")
        system = ComponentProxy("system")
        queues = [spec['name'] for spec in qm.get_queues([{'name':"*"}])]
        for reservation in reservations:
            reservation_queue = "R.%s" % reservation.name
            if reservation_queue not in queues:
                try:
                    qm.add_queues([{'name':reservation_queue, 'state':"running", 'users':reservation.users}])
                except Exception, e:
                    logger.error("unable to add reservation queue %s (%s)" % (reservation_queue, e))
                else:
                    logger.info("added reservation queue %s" % reservation_queue)
            else:
                try:
                    qm.set_queues([{'name':reservation_queue}], {'state':"running", 'users':reservation.users})
                except Exception, e:
                    logger.error("unable to update reservation queue %s (%s)" % (reservation_queue, e))
                else:
                    logger.info("updated reservation queue %s" % reservation_queue)
                
    
        return reservations
        
    def q_del (self, *args, **kwargs):
        reservations = Cobalt.Data.DataDict.q_del(self, *args, **kwargs)
        qm = ComponentProxy('queue-manager')
        queues = [spec['name'] for spec in qm.get_queues([{'name':"*"}])]
        for reservation in reservations:
            reservation_queue = "R.%s" % reservation.name
            if reservation_queue in queues:
                try:
                    qm.set_queues([{'name':reservation_queue}], {'state':"dead"})
                except Exception, e:
                    logger.error("problem disabling reservation queue (%s)" % e)
                else:
                    logger.info("reservation queue %s disabled" % reservation_queue)

        return reservations

class Partition (ForeignData):
    """Partitions are allocatable chunks of the machine"""
    
    fields = Data.fields.copy()
    fields.update(dict(
        queue = None,
        name = None,
        nodecards = None,
        scheduled = None,
        functional = None,
        size = None,
        parents = None,
        children = None,
    ))
    
    def _can_run (self, job):
        """Check that job can run on partition with reservation constraints"""
        basic = self.scheduled and self.functional
        jsize = int(job.nodes) # should this be 'size' instead?
        psize = int(self.size)
        size = (psize >= jsize) and ((psize == 32) or (jsize > psize/2))
        if not (basic and size):
            return False
        else:
            return True


class PartitionDict (ForeignDataDict):
    item_cls = Partition
    __failname__ = 'System Connection'
    __function__ = ComponentProxy("system").get_partitions
    __fields__ = ['name', 'queue', 'nodecards', 'scheduled', 'functional', 'size', 'parents', 'children']
    key = 'name'

    def can_run(self, target_partition, job):
        for part in self.itervalues():
            if not part.functional:
                if target_partition.name in part.children or target_partition.name in part.parents:
                    return False
        
        return target_partition._can_run(job)
                

class Job (ForeignData):
    
    """A cobalt job."""
    
    fields = Data.fields.copy()
    fields.update(dict(
        nodes = None,
        location = None,
        jobid = None,
        state = None,
        index = None,
        walltime = None,
        queue = None,
        user = None,
    ))
    
    def __init__ (self, spec):
        Cobalt.Data.ForeignData.__init__(self, spec)
        self.partition = "none"
        logger.info("Job %s/%s: Found job" % (self.jobid, self.user))

def fifocmp (job1, job2):
    """Compare 2 jobs for first-in, first-out."""
    
    def fifo_value (job):
        return job.index or job.jobid
    
    return cmp(fifo_value(job1), fifo_value(job2))


class JobDict(ForeignDataDict):
    item_cls = Job
    key = 'jobid'
    __oserror__ = Cobalt.Util.FailureMode("QM Connection")
    __function__ = ComponentProxy("queue-manager").get_jobs
    __fields__ = ['nodes', 'location', 'jobid', 'state', 'index',
                  'walltime', 'queue', 'user']

class Queue(ForeignData):
    fields = Data.fields.copy()
    fields.update(dict(
        name = None,
        state = None,
        policy = None,
    ))

    def LoadPolicy(self):
        '''Instantiate queue policy modules upon demand'''
        if self.policy not in Cobalt.SchedulerPolicies.names:
            logger.error("Cannot load policy %s for queue %s" % \
                         (self.policy, self.name))
        else:
            pclass = Cobalt.SchedulerPolicies.names[self.policy]
            self.policy = pclass(self.name)


class QueueDict(ForeignDataDict):
    item_cls = Queue
    key = 'name'
    __function__ = ComponentProxy("queue-manager").get_queues
    __fields__ = ['name', 'state', 'policy']

    def Sync(self):
        qp = [(q.name, q.policy) for q in self.itervalues()]
        Cobalt.Data.ForeignDataDict.Sync(self)
        [q.LoadPolicy() for q in self.itervalues() \
         if (q.name, q.policy) not in qp]


class BGSched (Component):
    
    implementation = "bgsched"
    name = "scheduler"
    logger = logging.getLogger("Cobalt.Components.scheduler")
    
    def __init__(self, *args, **kwargs):
        Component.__init__(self, *args, **kwargs)
        self.reservations = ReservationDict()
        self.queues = QueueDict()
        self.jobs = JobDict()
        self.partitions = PartitionDict()
    
    def add_reservations (self, specs):
        return self.reservations.q_add(specs)
    add_reservation = exposed(query(add_reservations))

    def del_reservations (self, specs):
        return self.reservations.q_del(specs)
    del_reservations = exposed(query(del_reservations))

    def get_reservations (self, specs):
        return self.reservations.q_get(specs)
    get_reservations = exposed(query(get_reservations))

    #def SetReservation(self, *args):
    #    return self.reservations.Get(*args,
    #                                 callback = \
    #                                 lambda r, na:r.update(na))
    #SetReservation = exposed(SetReservation)

    def sync_data(self):
        for item in [self.jobs, self.queues, self.partitions]:
            try:
                item.Sync()
            except ComponentLookupError:
                self.logger.error(item.__class__.__name__ + " unable to sync")
    sync_data = automatic(sync_data)

    def schedule_jobs (self):
        '''look at the queued jobs, and decide which ones to start'''
        
        # if we're missing information, don't bother trying to schedule jobs
        if not (self.partitions.__oserror__.status and self.queues.__oserror__.status and self.jobs.__oserror__.status):
            self.logger.error("foreign data scynchronization failed: disabling scheduling")
            return
        
        # grab a snapshot of the currently active reservations to reduce the chance of
        # problems with reservations starting and stopping while we're in the middle
        # of scheduling
        active_reservations = []
        for res in self.reservations.itervalues():
            if res.is_active():
                active_reservations.append(res.name)
            
        active_queues = []
        for queue in self.queues.itervalues():
            if queue.name.startswith("R."):
                if queue.name[2:] in active_reservations:
                    active_queues.append(queue)
            else:
                if queue.state == "running":
                    active_queues.append(queue)
        
        active_jobs = self.jobs.q_get([{'state':"queued", 'queue':queue.name} for queue in active_queues])
        
        viable = active_jobs[:]
        viable.sort(fifocmp)
        potential = {}
        for job in viable[:]:
            tmp_list = []   
            for partition in self.partitions.itervalues():
                # check if the current partition is linked to the job's queue or reservation
                if job.queue.startswith('R.'):
                    part_in_res = False
                    for part_name in self.reservations[job.queue[2:]].partitions.split(":"):
                        if not part_name in self.partitions:
                            self.logger.error("reservation '%s' refers to non-existant partition '%s'" % (job.queue[2:], part_name))
                            continue
                        if not (partition.name==self.partitions[part_name].name or partition.name in self.partitions[part_name].children):
                            continue
                        # if we got here, then the partition is part of the reservation
                        part_in_res = True
                    
                    if not part_in_res:
                        continue
                    
                elif job.queue not in partition.queue.split(':'):
                    continue
                    
                if self.partitions.can_run(partition, job):
                    if active_reservations:
                        for res_name in active_reservations:
                            # if the proposed job overlaps an active reservation, don't run it -- unless the job
                            # belongs to the active reservation
                            if not self.reservations[res_name].overlaps(partition, time.time(), 60 * float(job.walltime)):
                                tmp_list.append(partition)
                            elif job.queue=="R.%s" % res_name:
                                tmp_list.append(partition)
                    else:
                        tmp_list.append(partition)
            
            if tmp_list:
                potential[job.jobid] = tmp_list
            else:
                viable.remove(job)
        
        for queue in self.queues.itervalues():
            queue.policy.Prepare(viable, potential)
        
        placements = []
        for job in viable:
            # do something sensible when tidy_placements yanked a job out from under us
            if not potential.has_key(job.jobid):
                continue
            queue = self.queues[job.queue]
            place = queue.policy.PlaceJob(job, potential)
            if place:
                del potential[job.jobid]
                self.tidy_placements(potential, place[1])
                placements.append(place)
        
        self.run_jobs(placements)
    schedule_jobs = automatic(schedule_jobs)

    def tidy_placements(self, potential, newlocation):
        '''Remove any potential spots that overlap with newlocation'''
        cleanup = []
        for job in potential.keys():
            for location in potential[job][:]:
                if location.name==newlocation.name or location.name in newlocation.parents or location.name in newlocation.children:
                    potential[job].remove(location)
            if not potential[job]:
                del potential[job]

#        for job in cleanup:
#            del potential[job]

    def run_jobs (self, placements):
        """Connect to cqm and run jobs."""
        
        try:
            cqm = ComponentProxy("queue-manager")
        except ComponentLookupError:
            self.logger.error("failed to connect to queue manager")
            return
        
        for placement in placements:
            job = placement[0]
            location = placement[1].name
            cqm.run_jobs([{'tag':"job", 'jobid':job.jobid}], [location])
