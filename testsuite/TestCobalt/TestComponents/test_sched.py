import time

from Cobalt.Exceptions import DataCreationError

from Cobalt.Components.simulator import Simulator
from Cobalt.Components.bgsched import Reservation

class Job (object):
    def __init__(self, walltime, queue):
        # remember that walltime is in minutes
        self.walltime = walltime
        self.queue = queue

class TestReservation (object):

    def setup (self):
        self.system = Simulator(config_file="simulator.xml")
        self.system.add_partitions([{'name':"ANLR00"}])
        self.test_partition = self.system.partitions.values()[0]
    
    def test_required_name (self):
        spec = {'start':0, 'duration':0}
        try:
            reservation = Reservation(spec)
        except DataCreationError:
            pass
        else:
            assert not "didn't require name"
        spec['name'] = "my_reservation"
        try:
            reservation = Reservation(spec)
        except DataCreationError:
            assert not "failed with name specified"
    
    def test_init (self):
        reservation = Reservation({'name':"mine", 'start':0, 'duration':0})
        assert reservation.tag == "reservation"
        assert reservation.name == "mine"
        assert reservation.start == 0
        assert reservation.duration == 0
        assert reservation.cycle is None
        assert reservation.users == ""
        assert reservation.partitions == ""
    
    def test_active (self):
        reservation = Reservation({'name':"mine", 'start':100, 'duration':50})
        for current_time in xrange(1, 100):
            assert not reservation.is_active(current_time)
        for current_time in xrange(100, 150):
            assert reservation.is_active(current_time)
        for current_time in xrange(151, 250):
            assert not reservation.is_active(current_time)
    
    def test_active_cyclic (self):
        reservation = Reservation({'name':"mine", 'start':100, 'duration':10, 'cycle':50})
        assert not reservation.is_active(99)
        assert reservation.is_active(100)
        assert reservation.is_active(109)
        assert not reservation.is_active(111)
        assert not reservation.is_active(149)
        assert reservation.is_active(150)
        assert reservation.is_active(159)
        assert not reservation.is_active(161)
    
    def test_overlaps (self):
        reservation = Reservation({'name':"mine", 'start':100, 'duration':50, 'partitions':"ANLR00"})
        assert not reservation.overlaps(partition=self.test_partition, start=0, duration=99)
        assert reservation.overlaps(partition=self.test_partition, start=0, duration=100)
        assert reservation.overlaps(partition=self.test_partition, start=99, duration=1)
        assert reservation.overlaps(partition=self.test_partition, start=99, duration=50)
        assert reservation.overlaps(partition=self.test_partition, start=149, duration=1)
        assert not reservation.overlaps(partition=self.test_partition, start=150, duration=100)
    
    def test_overlaps_cyclic (self):
        reservation = Reservation({'name':"mine", 'start':100, 'duration':10, 'cycle':50, 'partitions':"ANLR00"})
        assert not reservation.overlaps(partition=self.test_partition, start=0, duration=99)
        assert reservation.overlaps(partition=self.test_partition, start=0, duration=100)
        assert reservation.overlaps(partition=self.test_partition, start=99, duration=1)
        assert reservation.overlaps(partition=self.test_partition, start=99, duration=10)
        assert reservation.overlaps(partition=self.test_partition, start=101, duration=1)
        assert reservation.overlaps(partition=self.test_partition, start=109, duration=1)
        assert not reservation.overlaps(partition=self.test_partition, start=110, duration=39)
        assert reservation.overlaps(partition=self.test_partition, start=90, duration=100)
        
    def test_job_within_reservation (self):
        # past reservation
        reservation = Reservation({'name':"mine", 'start':100, 'duration':3600, 'partitions':"ANLR00", 'queue':"default"})
        j = Job(5, "default")
        assert not reservation.job_within_reservation(j)
        j = Job(70, "default")
        assert not reservation.job_within_reservation(j)
        
        # current reservation
        reservation = Reservation({'name':"mine", 'start':time.time(), 'duration':3600, 'partitions':"ANLR00", 'queue':"default"})
        j = Job(5, "default")
        assert reservation.job_within_reservation(j)
        j = Job(70, "default")
        assert not reservation.job_within_reservation(j)
        
        # future reservation
        reservation = Reservation({'name':"mine", 'start':time.time() + 3600, 'duration':3600, 'partitions':"ANLR00", 'queue':"default"})
        j = Job(5, "default")
        assert not reservation.job_within_reservation(j)
        j = Job(40, "default")
        assert not reservation.job_within_reservation(j)
        j = Job(70, "default")
        assert not reservation.job_within_reservation(j)

    def test_job_within_reservation_cyclic (self):
        reservation = Reservation({'name':"mine", 'start':time.time()-3000, 'duration':3600, 'cycle':4000, 'partitions':"ANLR00", 'queue':"default"})
        # jobs ends inside the reservation
        j = Job(6, "default")
        assert reservation.job_within_reservation(j)
        # job ends in the "dead zone"
        j = Job(12, "default")
        assert not reservation.job_within_reservation(j)
        # job ends the next time the reservation is active
        j = Job(50, "default")
        assert not reservation.job_within_reservation(j)
        # job lasts longer than the reservation
        j = Job(100, "default")
        assert not reservation.job_within_reservation(j)
