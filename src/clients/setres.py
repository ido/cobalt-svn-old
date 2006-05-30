#!/usr/bin/env python

'''Setup reservations in the scheduler'''
__revision__ = '$Id$'

import getopt, sys, time
import Cobalt.Proxy, Cobalt.Util

helpmsg = '''Usage: setres [-a] -n name -s <starttime> -d <duration> -p <partition> -u <user> [partion1] .. [partionN]
starttime is in format: YYYY_MM_DD-HH:MM
duration may be in minutes or HH:MM:SS
user and name are optional
-a automatically find all dependancies of the partion(s) listed'''

if __name__ == '__main__':
    scheduler = Cobalt.Proxy.scheduler()
    try:
        (opts, args) = getopt.getopt(sys.argv[1:], 's:d:n:p:u:a', [])
    except getopt.GetoptError, msg:
        print msg
        print helpmsg
        raise SystemExit, 1
    try:
        partition = [opt[1] for opt in opts if opt[0] == '-p']
    except:
        if args:
            partition = args
        else:
            print "Must supply either -p with value or partitions as arguments"
            print helpmsg
            raise SystemExit, 1
    try:
        [start] = [opt[1] for opt in opts if opt[0] == '-s']
        [duration] = [opt[1] for opt in opts if opt[0] == '-d']
    except:
        print "Must supply -s and -d with values" 
        print helpmsg
        raise SystemExit, 1
    if duration.count(':') == 0:
        dsec = int(duration) * 60
    else:
        units = duration.split(':')
        units.reverse()
        totaltime = 0
        mults = [1, 60, 3600]
        if len(units) > 3:
            print "time too large"
            raise SystemExit, 1
        dsec = sum([mults[index] * float(units[index]) for index in range(len(units))])
    (day, rtime) = start.split('-')
    (syear, smonth, sday) = [int(field) for field in day.split('_')]
    (shour, smin) = [int(field) for field in rtime.split(':')]
    starttime = time.mktime((syear, smonth, sday, shour, smin, 0, 0, 0, -1))
    print "Got starttime %s" % (time.strftime('%c', time.localtime(starttime)))
    if '-u' in sys.argv[1:]:
        user = [opt[1] for opt in opts if opt[0] == '-u'][0]
    else:
        user = ''
    if '-n' in sys.argv[1:]:
        [nameinfo] = [val for (opt, val) in opts if opt == '-n']
    else:
        nameinfo = 'system'
    if '-a' in sys.argv[1:]:
        allparts = []
        spec = []
        parts = scheduler.GetPartition([{'tag':'partition', 'name':'*', 'queue':'*', 'state':'*', \
                                     'scheduled':'*', 'functional':'*', 'deps':'*'}])
        partinfo = Cobalt.Util.buildRackTopology(parts)
        try:
            for part in partition:
                allparts.append(part)
                spec.append({'tag':'partition', 'name':part}]
                for relative in partinfo[part][1]:
                    if relative not in allparts:
                        spec.append({'tag':'partition', 'name':relative}]
                        allparts.append(relative)
        except:
            print "Invalid partition(s)"
            print helpmsg
            raise SystemExit, 1 
    else:
        spec = [{'tag':'partition', 'name':partition[0]}]
    try:
        print scheduler.AddReservation(spec, nameinfo, user, starttime, dsec)
    except:
        print "Couldn't contact the scheduler"
        
