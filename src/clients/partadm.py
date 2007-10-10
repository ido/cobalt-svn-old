#!/usr/bin/env python

'''Partadm sets partition attributes in the scheduler'''
__revision__ = '$Revision$'
__version__ = '$Version$'

import sys, getopt, xmlrpclib
import Cobalt.Util
from Cobalt.Proxy import ComponentProxy, ComponentLookupError


helpmsg = '''Usage: partadm.py [-a] [-d] [-s size] part1 part2 (add or del)
Usage: partadm.py -l
Usage: partadm.py [--activate|--deactivate] part1 part2 (functional or not)
Usage: partadm.py [--enable|--disable] part1 part2 (scheduleable or not)
Usage: partadm.py --queue=queue1:queue2 part1 part2
Usage: partadm.py --deps=dep1:dep2 part1 part2
Usage: partadm.py --free part1 part2
Usage: partadm.py --dump
Usage: partadm.py --load <filename>
Usage: partadm.py --version
Must supply one of -a or -d or -l or -start or -stop or --queue'''

if __name__ == '__main__':
    if '--version' in sys.argv:
        print "partadm %s" % __revision__
        print "cobalt %s" % __version__
        raise SystemExit, 0
    try:
        (opts, args) = getopt.getopt(sys.argv[1:], 'adlrs:',
                                     ['dump', 'free', 'load=', 'enable', 'disable', 'activate', 'deactivate',
                                      'queue=', 'deps='])
    except getopt.GetoptError, msg:
        print msg
        print helpmsg
        raise SystemExit, 1
    try:
        sched = Cobalt.Proxy.scheduler()
    except Cobalt.Proxy.CobaltComponentError:
        print "Failed to connect to scheduler"
        raise SystemExit, 1

    if '-r' in sys.argv:
        partdata = sched.GetPartition([{'tag':'partition', 'name':'*', 'queue':'*',
                                        'state':'*', 'scheduled':'*', 'functional':'*',
                                        'deps':'*'}])
        partinfo = Cobalt.Util.buildRackTopology(partdata)
        parts = args
        for part in args:
            for relative in partinfo[part][1]:
                if relative not in parts:
                    parts.append(relative)
    else:
        parts = args
    if '-a' in sys.argv:
        func = sched.AddPartition
        try:
            [size] = [opt[1] for opt in opts if opt[0] == '-s']
        except:
            print "Must supply partition size with -s"
            raise SystemExit, 1
        args = ([{'tag':'partition', 'name':partname, 'size':int(size), 'functional':False,
                  'scheduled':False, 'queue':'default', 'deps':[]} for partname in parts], )
    elif '-d' in sys.argv:
        func = sched.DelPartition
        args = ([{'tag':'partition', 'name':partname} for partname in parts], )
    elif '--enable' in sys.argv:
        func = sched.Set
        args = ([{'tag':'partition', 'name':partname} for partname in parts],
                {'scheduled':True})
    elif '--disable' in sys.argv:
        func = sched.Set
        args = ([{'tag':'partition', 'name':partname} for partname in parts],
                {'scheduled':False})
    elif '--activate' in sys.argv:
        func = sched.Set
        args = ([{'tag':'partition', 'name':partname} for partname in parts],
                {'functional':True})
    elif '--deactivate' in sys.argv:
        func = sched.Set
        args = ([{'tag':'partition', 'name':partname} for partname in parts],
                {'functional':False})
    elif '-l' in sys.argv:
        func = sched.GetPartition
        args = ([{'tag':'partition', 'name':'*', 'size':'*', 'state':'*', 'scheduled':'*', 'functional':'*',
                  'queue':'*', 'deps':'*'}], )
    elif '--queue' in [opt for (opt, arg)  in opts]:
        try:
            cqm = Cobalt.Proxy.queue_manager()
            existing_queues = [q.get('name') for q in cqm.GetQueues([ \
                {'tag':'queue', 'name':'*'}])]
        except:
            print "Error getting queues from queue_manager"
        queue = [arg for (opt, arg) in opts if opt == '--queue'][0]
        if queue.split(':') != [q for q in queue.split(':') if q in existing_queues]:
            print '\'' + queue + '\' is not an existing queue'
            raise SystemExit, 1
        func = sched.Set
        args = ([{'tag':'partition', 'name':partname} for partname in parts],
                {'queue':queue})
    elif '--deps' in [opt for (opt, arg) in opts]:
        deps = [arg for (opt, arg) in opts if opt == '--deps'][0]
        func = sched.Set
        args = ([{'tag':'partition', 'name':partname} for partname in parts], {'deps':deps.split(':')})
    elif '--free' in [opt for (opt, arg) in opts]:
        func = sched.Set
        args = ([{'tag':'partition', 'name':partname} for partname in parts], {'state':'idle'})
    elif '--dump' in [opt for (opt, arg) in opts]:
        func = sched.GetPartition
        args = ([{'tag':'partition', 'name':'*', 'size':'*', 'state':'*', 'functional':'*',
                  'scheduled':'*', 'queue':'*', 'deps':'*'}], )
    else:
        print helpmsg
        raise SystemExit, 1

    try:
        parts = apply(func, args)
    except xmlrpclib.Fault, fault:
        print "Command failure", fault
    except:
        print "strange failure"

    if '-l' in sys.argv:
        # need to cascade up busy and non-functional flags
        partinfo = Cobalt.Util.buildRackTopology(parts)
        busy = [part['name'] for part in parts if part['state'] == 'busy']
        for part in parts:
            for pname in busy:
                if pname in partinfo[part['name']][0] + partinfo[part['name']][1] and pname != part['name']:
                    part.__setitem__('state', 'blocked')
        offline = [part['name'] for part in parts if not part['functional']]
        forced = [part for part in parts \
                  if [down for down in offline \
                      if down in partinfo[part['name']][0] + partinfo[part['name']][1]]]
        [part.__setitem__('functional', '-') for part in forced]
        data = [['Name', 'Queue', 'Size', 'Functional', 'Scheduled', 'State', 'Dependencies']]
        data += [[part['name'], part['queue'], part['size'], part['functional'], part['scheduled'],
                  part['state'], ','.join(part['deps'])] for part in parts]
        Cobalt.Util.printTabular(data, centered=[3, 4])
    else:
        print parts
            
        
