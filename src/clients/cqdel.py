#!/usr/bin/env python

'''Cobalt queue delete'''
__revision__ = '$Revision$'
__version__ = '$Version$'

import getopt, os, pwd, sys, time
import Cobalt.Logging, Cobalt.Util
from Cobalt.Proxy import ComponentProxy, ComponentLookupError


usehelp = "Usage:\ncqdel [--version] [-f] <jobid> <jobid>"

if __name__ == '__main__':
    if '--version' in sys.argv:
        print "cqdel %s" % __revision__
        print "cobalt %s" % __version__
        raise SystemExit, 0
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'f')
    except getopt.GetoptError, gerr:
        print gerr
        print usehelp
        raise SystemExit, 1
    if len(args) < 1:
        print usehelp
        raise SystemExit, 1
    level = 30
    if '-d' in sys.argv:
        level = 10
    user = pwd.getpwuid(os.getuid())[0]
    Cobalt.Logging.setup_logging('cqdel', to_syslog=False, level=level)
    logger = Cobalt.Logging.logging.getLogger('cqdel')
    try:
        cqm = ComponentProxy("queue-manager")
    except ComponentLookupError:
        print >> sys.stderr, "Failed to connect to queue manager"
        sys.exit(1)
    
    for i in range(len(args)):
        try:
            args[i] = int(args[i])
        except:
            logger.error("jobid must be an integer")
            raise SystemExit, 1
    
    spec = [{'tag':'job', 'user':user, 'jobid':jobid} for jobid in args]
    jobs = cqm.del_jobs(spec)
    time.sleep(1)
    if jobs:
        data = [('JobID','User')] + [(job.get('jobid'), job.get('user')) for job in jobs]
        print "      Deleted Jobs"
        Cobalt.Util.print_tabular(data)
    else:
        print "cqdel: Job %s not found" % sys.argv[-1]

