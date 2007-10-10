#!/usr/bin/env python

'''Cobalt fake mpirun'''
__revision__ = ''
__version__ = '$Version$'

import getopt, os, pwd, sys, time, xmlrpclib, logging
import Cobalt.Logging, Cobalt.Proxy, Cobalt.Util

usehelp = "Usage:\nfake-mpirun [--version] [-h] <mpirun arguments>"

if __name__ == '__main__':
    if '--version' in sys.argv:
        print "fake-mpirun %s" % __revision__
        print "cobalt %s" % __version__
        raise SystemExit, 0
    if '-h' in sys.argv:
        print usehelp
        print """\
        
        This program is meant to be called from scripts submitted to 
        run using the cobalt queueing system.  It takes all of the same arguments
        as the system mpirun, but suppresses the -partition argument.  This
        argument will be set by the queueing system once it has decided where
        to run your job.
        """
        
        raise SystemExit, 0
    try:
        idx = sys.argv.index("-partition")
        arglist = sys.argv[1:idx] + sys.argv[idx+2:]
        print "NOTE: the -partition option should not be used, as the job"
        print "will run in the partition reserved by cobalt."
    except ValueError:
        arglist = sys.argv[1:]

    # these flags (which all take an argument) should not be passed to the real mpirun
    bad_args = ["-host", "-backend", "-shape"]
    for a in bad_args:
        try:
            idx = arglist.index(a)
            arglist = arglist[0:idx] + arglist[idx+2:]
            print "NOTE: the %s option should not be used." % a
        except ValueError:
            pass
    
        
    level = 30
    if '-d' in sys.argv:
        level = 10

    Cobalt.Logging.setup_logging('fake-mpirun', to_syslog=False, level=level)
    logger = logging.getLogger('fake-mpirun')

    try:
        os.environ["COBALT_JOBID"] = os.environ["COBALT_JOBID"]
    except KeyError:
        logger.error("fake-mpirun must be invoked by a script submitted to cobalt.")
        raise SystemExit, 1
        
    cqm = Cobalt.Proxy.queue_manager()
    response = cqm.GetJobs({'tag':'job', 'jobid':os.environ["COBALT_JOBID"], 'state':'*', 'procs':'*', 'location':'*', 'walltime':'*', 'outputdir':'*'})
    if len(response) == 0:
        logger.error("Error: cqm did not find a job with id " + os.environ["COBALT_JOBID"])
        raise SystemExit, 1
    if len(response) > 1:
        logger.error("Error: cqm did not find a unique job with id " + os.environ["COBALT_JOBID"])
        raise SystemExit, 1
         
    j = response[0]
    if j['location'] is None:
        logger.error("Error: fake-mpirun's parent is in state '%s' and has not specified a partition." % j['state'])
        raise SystemExit, 1
#    j['location'] = "ANLR00"
    
    arglist += ['-partition', j['location']]
    
    
    if "-np" in sys.argv:
        idx = sys.argv.index("-np")
    elif "-n" in sys.argv:
        idx = sys.argv.index("-n")
    elif "-nodes" in sys.argv:
        idx = sys.argv.index("-nodes")
    else:
        idx = -1
     
    if idx > 0:
        if int(sys.argv[idx+1]) > int(j['procs']):
            logger.error("Error: tried to request more processors (%s) than reserved (%s)." % (sys.argv[idx+1], j['procs']))
            raise SystemExit, 1
        
    user = pwd.getpwuid(os.getuid())[0]
    jobspec = {'jobid':os.environ["COBALT_JOBID"], 'user':user, 'true_mpi_args':arglist, 'walltime':j['walltime'], 'args':[], 'location':j['location'], 'outputdir':j['outputdir']}
    try:
        cqm = Cobalt.Proxy.queue_manager()
        pm = Cobalt.Proxy.process_manager()

        # try adding job to queue_manager
        pgid = cqm.ScriptMPI(jobspec)
        print "i see pgid of : ", pgid
        
        while True:
            r = pm.GetProcessGroup([{'tag':'process-group', 'pgid':pgid, 'state':'*'}])
            state = r[0]['state']
            if state == 'running':
                time.sleep(5)
                continue
            else:
                break
        print "process group %s has completed" % (pgid)
        pm.WaitProcessGroup([{'tag':'process-group', 'pgid':pgid, 'exit-status':'*'}])
        

    except Cobalt.Proxy.CobaltComponentError:
        logger.error("Can't connect to the queue manager")
        raise SystemExit, 1
    except xmlrpclib.Fault, flt:
        if flt.faultCode == 31:
            logger.error("System draining. Try again later")
            raise SystemExit, 1
        elif flt.faultCode == 30:
            logger.error("Job submission failed because: \n%s\nCheck 'cqstat -q' and the cqstat manpage for more details." % flt.faultString)
            raise SystemExit, 1
        elif flt.faultCode == 1:
            logger.error("Job submission failed due to queue-manager failure")
            raise SystemExit, 1
        else:
            logger.error("Job submission failed")
            logger.error(flt)
            raise SystemExit, 1
#     except:
#         logger.error("Error submitting job")
#         raise SystemExit, 1


    print "all done!"