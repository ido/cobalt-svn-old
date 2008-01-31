#!/usr/bin/env python

'''Cobalt job administration command'''
__revision__ = '$Revision$'
__version__ = '$Version$'

import sys, xmlrpclib
import Cobalt.Logging, Cobalt.Util
import getpass
from Cobalt.Proxy import ComponentProxy, ComponentLookupError
from Cobalt.Components.cqm import QueueError

__helpmsg__ = 'Usage: cqadm [--version] [-d] [--hold] [--release] [--run=<location>] ' + \
              '[--kill] [--delete] [--queue=queuename] [--time=time] <jobid> <jobid>\n' + \
              '       cqadm [-d] [-f] [--addq] [--delq] [--getq] [--stopq] [--startq] ' + \
              '[--drainq] [--killq] [--setq "property=value property=value"] [--unsetq "property property"] --policy=<qpolicy> <queue> <queue>\n' + \
              '       cqadm [-j <next jobid>]'

def get_queues(cqm_conn):
    '''gets queues from cqmConn'''
    info = [{'tag':'queue', 'name':'*', 'state':'*', 'users':'*',
             'maxtime':'*', 'mintime':'*', 'maxuserjobs':'*',
             'maxusernodes':'*', 'maxqueued':'*', 'maxrunning':'*',
             'adminemail':'*', 'totalnodes':'*', 'cron':'*', 'policy':'*', 'priority':'*'}]
    return cqm_conn.get_queues(info)

if __name__ == '__main__':
    if '--version' in sys.argv:
        print "cqadm %s" % __revision__
        print "cobalt %s" % __version__
        raise SystemExit, 0

    options = {'getq':'getq', 'f':'force', 'd':'debug', 'hold':'hold',
               'release':'release', 'kill':'kill', 'delete':'delete',
               'addq':'addq', 'delq':'delq', 'stopq':'stopq',
               'startq':'startq', 'drainq':'drainq', 'killq':'killq'}
    doptions = {'j':'setjobid', 'setjobid':'setjobid', 'queue':'queue',
                'i':'index', 'policy':'policy', 'run':'run',
                'setq':'setq', 'time':'time', 'unsetq':'unsetq', }

    (opts, args) = Cobalt.Util.dgetopt_long(sys.argv[1:], options,
                                            doptions, __helpmsg__)

    if len(args) == 0 and not [arg for arg in sys.argv[1:] if arg not in
                               ['getq', 'j', 'setjobid']]:
        print "At least one jobid or queue name must be supplied"
        print __helpmsg__
        raise SystemExit, 1

    if opts['debug']:
        debug = True
        level = 10
    else:
        debug = False
        level = 30

    if len(opts) == 0:
        print "At least one command must be specified"
        print __helpmsg__
        raise SystemExit, 1

    if opts['hold'] and opts['release']:
        print "Only one of --hold or --release can be used at once"
        print __helpmsg__
        raise SystemExit, 1

    Cobalt.Logging.setup_logging('cqadm', to_syslog=False, level=level)

    # set the spec whether working with queues or jobs
    if opts['addq'] or opts['delq'] or opts['getq'] or opts['setq'] \
           or opts['startq'] or opts['stopq'] or opts['drainq'] \
           or opts['killq'] or opts['policy'] or opts['unsetq']:
        spec = [{'tag':'queue', 'name':qname} for qname in args]
    else:
        for i in range(len(args)):
            try:
                args[i] = int(args[i])
            except:
                print >> sys.stderr, "jobid must be an integer"
                raise SystemExit, 1
    
        spec = [{'tag':'job', 'jobid':jobid} for jobid in args]

    try:
        cqm = ComponentProxy("queue-manager")
    except ComponentLookupError:
        print >> sys.stderr, "Failed to connect to queue manager"
        sys.exit(1)
    
    kdata = [item for item in ['--kill', '--delete'] if item in sys.argv]
    if opts['setjobid']:
        try:
            response = cqm.set_jobid(int(opts['setjobid']))
        except ValueError:
            print "The new jobid must be an integer"
            raise SystemExit, 1
        except xmlrpclib.Fault, flt:
            print flt.faultString
            raise SystemExit, 1
    elif kdata:
        user = getpass.getuser()
        for cmd in kdata:
            if cmd == '--delete':
                response = cqm.del_jobs(spec, True, user)
            else:
                response = cqm.del_jobs(spec, user)
    elif opts['run']:
        location = opts['run']
        part_list = ComponentProxy("system").get_partitions([{'name': location}])
        if len(part_list) != 1:
            print "Error: cannot find partition named '%s'" % location
            raise SystemExit, 1
        response = cqm.run_jobs(spec, location.split(':'))
    elif opts['addq']:
        existing_queues = get_queues(cqm)
        if [qname for qname in args if qname in
            [q.get('name') for q in existing_queues]]:
            print 'queue already exists'
            response = ''
        elif len(args) < 1:
            print 'Must specify queue name'
            raise SystemExit, 1
        else:
            response = cqm.add_queues(spec)
            datatoprint = [('Added Queues', )] + \
                          [(q.get('name'), ) for q in response]
            Cobalt.Util.print_tabular(datatoprint)
    elif opts['getq']:
        response = get_queues(cqm)
        for q in response:
            if q['maxtime'] is not None:
                q['maxtime'] = "%02d:%02d:00" % (divmod(int(q.get('maxtime')), 60))
            if q['mintime'] is not None:
                q['mintime'] = "%02d:%02d:00" % (divmod(int(q.get('mintime')), 60))
        header = [('Queue', 'Users', 'MinTime', 'MaxTime', 'MaxRunning',
                   'MaxQueued', 'MaxUserNodes', 'TotalNodes',
                   'AdminEmail', 'State', 'Cron', 'Policy', 'Priority')]
        datatoprint = [(q['name'], q['users'],
                        q['mintime'], q['maxtime'],
                        q['maxrunning'], q['maxqueued'],
                        q['maxusernodes'], q['totalnodes'],
                        q['adminemail'], q['state'],
                        q['cron'], q['policy'], q['priority'])
                       for q in response]
        datatoprint.sort()
        Cobalt.Util.print_tabular(header + datatoprint)
    elif opts['delq']:
        response = []
        try:
            response = cqm.del_queues(spec, opts['force'])
            datatoprint = [('Deleted Queues', )] + \
                          [(q.get('name'), ) for q in response]
            Cobalt.Util.print_tabular(datatoprint)
        except xmlrpclib.Fault, flt:
            print flt.faultString
    elif opts['setq']:
        props = [p.split('=') for p in opts['setq'].split(' ')]
        for p in props:
            if len(p) != 2:
                print "Improperly formatted argument to setq : %r" % p
                raise SystemExit, 1
        updates = {}
        for prop, val in props:
            if prop.lower() in ['maxtime', 'mintime']:
                if val.count(':') in [0, 2]:
                    t = val.split(':')
                    for i in t:
                        try:
                            if i != '*':
                                dummy = int(i)
                        except:
                            print prop + ' value is not a number'
                            raise SystemExit, 1
                    if val.count(':') == 2:
                        t = val.split(':')
                        val = str(int(t[0])*60 + int(t[1]))
                    elif val.count(':') == 0:
                        pass
                else:
                    print 'Time for ' + prop + ' is not valid, must be in hh:mm:ss or mm format'
            updates.update({prop.lower():val})
        try:
            response = cqm.set_queues(spec, updates)
        except xmlrpclib.Fault, flt:
            if flt.faultCode == QueueError.fault_code:
                print flt.faultString
                sys.exit(1)
    elif opts['unsetq']:
        updates = {}
        for prop in opts['unsetq'].split(' '):
            updates[prop.lower()] = None

        response = cqm.set_queues(spec, updates)
    elif opts['stopq']:
        response = cqm.set_queues(spec, {'state':'stopped'})
    elif opts['startq']:
        response = cqm.set_queues(spec, {'state':'running'})
    elif opts['drainq']:
        response = cqm.set_queues(spec, {'state':'draining'})
    elif opts['killq']:
        response = cqm.set_queues(spec, {'state':'dead'})
    elif opts['policy']:
        response = cqm.set_queues(spec, {'policy':opts['policy']})
    else:
        updates = {}
        new_q_name = None
        if opts['hold']:
            updates['state'] = 'hold'
            if not spec:
                print "you must specify a jobid to hold"
                raise SystemExit, 1
            copy = []
            for s in spec:
                s['state'] = 'queued'
                copy.append(s.copy())
            for c in copy:
                c['state'] = 'user hold'
            spec += copy
        elif opts['release']:
            updates['state'] = 'queued'
            if not spec:
                print "you must specify a jobid to release"
                raise SystemExit, 1
            copy = []
            for s in spec:
                s['state'] = 'hold'
                copy.append(s.copy())
            for c in copy:
                c['state'] = 'user hold'
            spec += copy
        if opts['queue']:
            new_q_name = opts['queue']
        if opts['index']:
            updates['index'] = opts['index']
        if opts['time']:
            if ':' in opts['time']:
                units = opts['time'].split(':')
                units.reverse()
                totaltime = 0
                mults = [0, 1, 60]
                if len(units) > 3:
                    print "time too large"
                    raise SystemExit, 1
                totaltime = sum([mults[index] * float(units[index]) \
                                 for index in range(len(units))])
                opts['time'] = str(totaltime)
            else:
                try:
                    t = int(opts['time'])
                    if t < 0:
                        print "time can't be negative"
                        raise Exception("time can't be negative")
                except:
                    print "Invalid value for time"
                    raise SystemExit, 1
            updates['walltime'] = opts['time']
        try:
            response = cqm.set_jobs(spec, updates)
            if new_q_name:
                response += cqm.move_jobs(spec, new_q_name)
        except xmlrpclib.Fault, flt:
            response = []
            if flt.faultCode == 30 or flt.faultCode == 42:
                print flt.faultString
                raise SystemExit, 1
            else:
                print flt.faultString
    if not response:
        Cobalt.Logging.logging.error("Failed to match any jobs or queues")
    else:
        Cobalt.Logging.logging.debug(response)
