#!/usr/bin/env python

'''Cobalt job administration command'''
__revision__ = '$Revision$'

import sys
import Cobalt.Logging, Cobalt.Proxy, Cobalt.Util

__helpmsg__ = 'Usage: cqadm [-d] [--hold] [--release] [--run=<location>] ' + \
              '[--kill] [--delete] [--queue=queuename] <jobid> <jobid>\n' + \
              '       cqadm [-d] [--addq] [--delq] [--getq] [--stopq] [--startq] ' + \
              '[--drainq] [--killq] [--setq property=value:property=value] <queue> <queue>'

def get_queues(cqm_conn):
    '''gets queues from cqmConn'''
    info = [{'tag':'queue', 'name':'*', 'state':'*', 'users':'*',
             'maxtime':'*', 'mintime':'*', 'maxuserjobs':'*',
             'maxqueued':'*', 'maxrunning':'*', 'adminemail':'*',
             'totalnodes':'*'}]
    return cqm_conn.GetQueues(info)

if __name__ == '__main__':

    options = {'getq':'getq', 'd':'debug', 'hold':'hold', 'release':'release',
               'kill':'kill', 'delete':'delete', 'addq':'addq', 'delq':'delq',
               'stopq':'stopq', 'startq':'startq', 'drainq':'drainq', 'killq':'killq'}
    doptions = {'j':'setjobid', 'setjobid':'setjobid', 'queue':'queue',
                'run':'run', 'setq':'setq'}

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
    if opts['addq'] or opts['delq'] or opts['getq'] or opts['setq'] or opts['startq'] or opts['stopq'] or opts['drainq'] or opts['killq']:
        spec = [{'tag':'queue', 'name':qname} for qname in args]
    else:
        spec = [{'tag':'job', 'jobid':jobid} for jobid in args]

    cqm = Cobalt.Proxy.queue_manager()
    kdata = [item for item in ['--kill', '--delete'] if item in sys.argv]
    if opts['setjobid']:
        response = cqm.SetJobID(int(opts['setjobid']))
    elif kdata:
        for cmd in kdata:
            if cmd == '--delete':
                response = cqm.DelJobs(spec, True)
            else:
                response = cqm.DelJobs(spec)
    elif opts['run']:
        location = opts['run']
        response = cqm.RunJobs(spec, location.split(':'))
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
            response = cqm.AddQueue(spec)
            datatoprint = [('Added Queues', )] + \
                          [(q.get('name'), ) for q in response]
            Cobalt.Util.print_tabular(datatoprint)
    elif opts['getq']:
        response = get_queues(cqm)
        for q in response:
            if q.get('maxtime', '*') != '*':
                q['maxtime'] = "%02d:%02d:00" % (divmod(int(q.get('maxtime')), 60))
            if q.get('mintime', '*') != '*':
                q['mintime'] = "%02d:%02d:00" % (divmod(int(q.get('mintime')), 60))
        datatoprint = [('Queue', 'Users', 'MinTime', 'MaxTime', 'MaxRunning',
                        'MaxQueued', 'MaxUserNodes', 'TotalNodes',
                        'AdminEmail', 'State')] + \
                        [(q.get('name', '*'), q.get('users', '*'),
                          q.get('mintime','*'), q.get('maxtime','*'),
                          q.get('maxrunning','*'),q.get('maxqueued','*'),
                          q.get('maxusernodes','*'),q.get('totalnodes','*'),
                          q.get('adminemail', '*'),q.get('state'))
                         for q in response]
        Cobalt.Util.print_tabular(datatoprint)
    elif opts['delq']:
        response = cqm.DelQueues(spec)
        datatoprint = [('Deleted Queues', )] + \
                      [(q.get('name'), ) for q in response]
        Cobalt.Util.print_tabular(datatoprint)
    elif opts['setq']:
        props = [p.split('=') for p in opts['setq'].split(' ')]
        updates = {}
        for prop, val in props:
            if prop.lower() in ['maxtime', 'mintime'] and val.count(':') > 0:
                t = val.split(':')
                val = str(int(t[0])*60 + int(t[1]))
            updates.update({prop.lower():val})
        response = cqm.SetQueues(spec, updates)
    elif opts['stopq']:
        response = cqm.SetQueues(spec, {'state':'stopped'})
    elif opts['startq']:
        response = cqm.SetQueues(spec, {'state':'running'})
    elif opts['drainq']:
        response = cqm.SetQueues(spec, {'state':'draining'})
    elif opts['killq']:
        response = cqm.SetQueues(spec, {'state':'dead'})
    else:
        updates = {}
        if opts['hold']:
            updates['state'] = 'hold'
        elif opts['release']:
            updates['state'] = 'queued'
        if opts['queue']:
            queue = opts['queue']
            updates['queue'] = queue
        response = cqm.SetJobs(spec, updates)
    Cobalt.Logging.logging.debug(response)
