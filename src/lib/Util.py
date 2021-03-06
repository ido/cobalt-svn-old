'''Utility funtions for Cobalt programs'''
__revision__ = '$Revision$'

import copy_reg
import cPickle
import os
import types
import smtplib
import socket
import sys
import time
import datetime
import ConfigParser
import os.path
import subprocess
from datetime import date, datetime
from getopt import getopt, GetoptError
from Cobalt.Exceptions import TimeFormatError, TimerException, ThreadPickledAliveException
import logging
from threading import Thread
from Queue import Queue
import inspect
import re
import select
import errno

import Cobalt
from Cobalt.Proxy import ComponentProxy

no_pytz = False
try:
    from pytz import timezone
    import pytz
except ImportError:
    no_pytz = True

logger = logging.getLogger('Util')

config_true_values = ['true', 'yes','1','on']
config_false_values = ['false', 'no','0','off']

config = ConfigParser.ConfigParser()

def init_cobalt_config():
    try:
        config.read(Cobalt.CONFIG_FILES)
    except:
        logger.critical("init_cobalt_config: Error Opening Cobalt Config File")
        raise


def get_config_option(section, option, default=None):
    '''Get an option from the cobalt config file.  Must be called after
       Cobalt.Util.init_cobalt_cofig.
       
       If the option is not found and a default is specified, then the default
       will be returned.  If the default is None, then an exception will be 
       raised, appropriate to whether or not the section is found and a message
       will be written to the log.  

       If a non-None default is specified, then the default value will be used
       no message is logged.
        

    '''
    try:
        value = config.get(section, option)
    except ConfigParser.NoOptionError:
        if default == None:
            logger.error("get_config_option: Option %s not found in section [%s]", 
                option, section)
            raise
        else:
            value = default
    except ConfigParser.NoSectionError:
        if default == None:
            logger.error("get_config_option: Section [%s] not found", section)
            raise
        else:
            value = default

    return value


def sleep(t):
    
    """The python sleep uses a select() to handle sleep to allow for
       subsecond sleeps.  Apparently, on 64-bit Linux kernels, this
       use of select() has been known to throw a  kernel error into 
       user-space.  In the case of Cobalt, this can cause components to
       unregister themselves.  Use this function to prevent such pain."""

    try:
        time.sleep(t)
    except IOError:
        logger.warning("IOError trapped from time.sleep() and ignored.")
    

def check_dependencies(dependency_string):

    if dependency_string.lower() == 'none':
        #we are removing all job dependencies.
        print "Removing job dependencies"
        return

    deps = set(dependency_string.split(":"))
    
    query = []
    for dep in deps:
        try:
            query.append({"jobid": int(dep)})
        except:
            pass
    
    jobs = ComponentProxy("queue-manager").get_jobs(query)
    
    job_ids = set( [str(j["jobid"]) for j in jobs] )
    
    missing = deps.difference(job_ids)
    
    if missing:
        print "WARNING: dependencies %s do not match jobs currently in the "\
                "queue" % ":".join(missing)
    

def get_time(date_string):
    '''Parse a time string that may be specified as minutes, HH:MM, HH:MM:SS, 
    or DD:HH:MM:SS, and return the total number of minutes.  Raise an 
    exception for bad values.
    
    '''
    time_info = {}

    units = date_string.split(":")

    if len(units) == 1:
        time_info["minutes"] = units[0]
    elif len(units) == 2:
        time_info["hours"] = units[0]
        time_info["minutes"] = units[1]
    elif len(units) == 3:
        time_info["hours"] = units[0]
        time_info["minutes"] = units[1]
        time_info["seconds"] = units[2]
    elif len(units) == 4:
        time_info["days"] = units[0]
        time_info["hours"] = units[1]
        time_info["minutes"] = units[2]
        time_info["seconds"] = units[3]
    else:
        raise TimeFormatError, "time may be specified as minutes, HH:MM, HH:MM:SS, or DD:HH:MM:SS"

    for key in time_info:
        try:
            time_info[key] = int(time_info[key])
        except ValueError:
            raise TimeFormatError, "illegal value '%s' for %s" % (time_info[key], key)
            
    if time_info.has_key("seconds"):
        if time_info["seconds"] < 0 or time_info["seconds"] > 59:
            raise TimeFormatError, "seconds value '%s' outside range [0, 59]" % time_info["seconds"]

    if time_info.has_key("minutes"):
        if len(time_info) == 1:
            if time_info["minutes"] < 0:
                raise TimeFormatError, "minutes value must not be negative"
       

    if time_info.has_key("hours"):
        if len(time_info) < 4:
            if time_info["hours"] < 0:
                raise TimeFormatError, "hours value must not be negative"

    if time_info.has_key("days"):
        if time_info["days"] < 0:
            raise TimeFormatError, "days value must not be negative"

    minutes = time_info.get("minutes", 0)
    minutes += 60 * time_info.get("hours", 0)
    minutes += 1440 * time_info.get("days", 0)

    # XML-RPC only allows 32-bit integers... so make sure the user isn't
    # trying to specify a number that causes an explosion
    if minutes > 2**31:
        raise TimeFormatError, "%d years is too long" % (minutes/525600, )

    return minutes


def dgetopt(arglist, opt, vopt, msg):
    '''parse options into a dictionary'''
    ret = {}
    for optname in opt.values() + vopt.values():
        ret[optname] = False
    gstr = "".join(opt.keys()) + "".join([longopt+':' for longopt in vopt.keys()])
    try:
        (opts, args) = getopt(arglist, gstr)
    except GetoptError, gerr:
        print gerr
        print msg
        raise SystemExit, 1
    for (gopt, garg) in opts:
        option = gopt[1:]
        if opt.has_key(option):
            ret[opt[option]] = True
        else:
            ret[vopt[option]] = garg
    return ret, list(args)

def merge_nodelist(locations):
    '''create a set of dashed-ranges from a node list'''
    reg = re.compile('(\D+)(\d+)')
    prefix = reg.match(locations[0]).group(1)

    # create a sorted list of the node numbers
    uniq = []
    for name in locations:
        newnum = int(reg.match(name).group(2))
        if not newnum in uniq:
            uniq.append(newnum)
    uniq.sort()

    # iterate through the sorted list, identifying gaps in the sequential numbers
    breaks = []
    start = 0
    idx = 0
    for idx in range(1,len(uniq)):
        if uniq[idx] != uniq[idx-1] + 1:
            breaks.append((start,idx-1))
            start = idx
            
    breaks.append((start, idx))

    # produce pretty output for contiguous ranges
    ret = []
    for t in breaks:
        if uniq[t[1]] - uniq[t[0]] > 0:
            ret.append("[%s%s-%s]" % (prefix, uniq[t[0]], uniq[t[1]]))
        else:
            ret.append("%s%s" % (prefix, uniq[t[0]]))

    return ','.join(ret)


def dgetopt_long(arglist, opt, vopt, msg):
    '''parse options into a dictionary, long and short options supported'''
    ret = {}
    for optname in opt.values() + vopt.values():
        ret[optname] = False
    long_opts = []
    gstr = ''

    # options that don't require args
    for o in opt.keys():
        if len(o) > 1:
            long_opts.append(o)
        else:
            gstr = gstr + o
    # options that require args
    for o in vopt.keys():
        if len(o) > 1:
            long_opts.append(o + '=')
        else:
            gstr = gstr + o + ':'

    try:
        (opts, args) = getopt(arglist, gstr, long_opts)
    except GetoptError, gerr:
        print gerr
        print msg
        raise SystemExit, 1

    for (gopt, garg) in opts:
        option = gopt.split('-')[-1]
        if opt.has_key(option):
            ret[opt[option]] = True
        else:
            ret[vopt[option]] = garg

    return ret, list(args)

def print_vertical(rows):
    '''print data in horizontal format'''
    hmax = max([len(str(x)) for x in rows[0]])
    hformat = '    %%-%ds: %s' % (hmax+1, '%s')
    for row in rows[1:]:
        for x in range(len(row)):
            if x == 0:
                print "%s: %s" % (rows[0][x], row[x])
            else:
                print hformat % (rows[0][x], row[x])
        print

def print_tabular(rows):
    '''print data in tabular format'''
    cmax = tuple([-1 * max([len(str(row[index])) for row in rows]) for index in xrange(len(rows[0]))])
    fstring = ("%%%ss  " * len(cmax)) % cmax
    print fstring % rows[0]
    print ((-1 * sum(cmax))  + (len(cmax) * 2)) * '='
    for row in rows[1:]:
        try:
            print fstring % row
        except IOError:
            return

def printTabular(rows, centered = []):
    '''print data in tabular format'''
    for row in rows:
        for index in xrange(len(row)):
            if isinstance(row[index], types.BooleanType):
                if row[index]:
                    row[index] = 'X'
                else:
                    row[index] = ''
    total = 0
    for column in xrange(len(rows[0])):
        width = max([len(str(row[column])) for row in rows])
        for row in rows:
            if column in centered:
                row[column] = row[column].center(width)
            else:
                row[column] = str(row[column]).ljust(width)
        total += width + 2
    try:
        print '  '.join(rows[0])
        print total * '='
        for row in rows[1:]:
            print '  '.join(row)
    except IOError:
        return

def print_dtab(dtab, fields = []):
    '''print dictionary data in tabular format'''
    if not fields:
        fields = dtab[0].keys()
    fieldlen = [(field, max([len(str(drow[field])) for drow in dtab] + [len(field)])) for field in fields]
    fstring = ''
    for key, value in fieldlen:
        fstring += '%%(%s)%ss  ' % (key, (-1 * value))
    header = "".join([("%" + str(value) + "s  ")%(key) for key, value in fieldlen])
    print header
    print (sum([value for key, value in fieldlen]) + (2 * len(fieldlen))) * '='
    for drow in dtab:
        print fstring % drow

def buildRackTopology(partlist):
    '''Build a dict of partition -> (parents, children)'''
    partinfo = {}
    partport = {}
    for part in partlist:
        partport[part['name']] = part
        partinfo[part['name']] = ([], [])
    for part in partlist:
        parents = [ppart['name'] for ppart in partlist if part['name'] in ppart['deps']]
        while parents:
            next = parents.pop()
            partinfo[part['name']][0].append(next)
            ndp = [ppart['name'] for ppart in partlist if next in ppart['deps']]
            parents += ndp
        children = part['deps'][:]  # copy because popping this below would
                                    # clear the deps list, and all children
                                    # are not added properly
        while children:
            next = children.pop()
            partinfo[part['name']][1].append(next)
            children += partport[next]['deps']
    return partinfo

def sendemail(toaddr, subj, msg, smtpserver = 'localhost'):
    '''Sends an email'''
    msgstr = ("From: %s\r\nTo: %s\r\nSubject: %s\r\n\r\n" % ('cobalt@%s' % socket.getfqdn(), (',').join(toaddr), subj))
    try:
        server = smtplib.SMTP(smtpserver)
    except Exception, e:
        print "Problem sending mail", e
        return
    try:
        server.sendmail('cobalt@%s' % socket.getfqdn(), toaddr, msgstr + msg)
    except Exception, msg:
        print 'Problem sending mail', msg
    server.quit()
    
def runcommand(cmd, args):
    '''Execute command, returning rc, stdout, stderr'''
    proc = subprocess.Popen([os.path.expandvars(cmd)] + args, close_fds = True, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
    out, err = proc.communicate()
    return (proc.returncode, out, err)

def escape_string(string, chars = "\""):
    string = string.replace('\\', '\\\\')
    for char in list(chars):
        string = string.replace(char, '\\' + char)
    return string

_replace_quote_re = re.compile(r'\'')
def convert_argv_to_quoted_command_string(argv):
    mod_argv = []
    for arg in argv:
        mod_argv.append("'" + _replace_quote_re.sub('\'"\'"\'', arg) + "'")
    return " ".join(mod_argv)

class AccountingLog:
    def __init__(self, name):
        CP = ConfigParser.ConfigParser()
        CP.read(Cobalt.CONFIG_FILES)
        try:
            self.logdir = os.path.expandvars(CP.get('cqm', 'log_dir'))
        except ConfigParser.NoOptionError:
            self.logdir = Cobalt.DEFAULT_LOG_DIRECTORY
        self.date = None
        self.logfile = open('/dev/null', 'w+')
        self.name = name
    def RotateLog(self):
        if self.date != time.localtime()[:3]:
            self.date = time.localtime()[:3]
            date_string = "%s_%02d_%02d" % self.date
            logfile = "%s/%s-%s.log" % (self.logdir, self.name, date_string)
            try:
                self.logfile = open(logfile, 'a+')
            except IOError:
                self.logfile = open("/dev/null", 'a+')
    def LogMessage(self, message):
        self.RotateLog()
        timenow = time.strftime("%Y-%m-%d %T", time.localtime())
        
        try:
            self.logfile.write("%s %s\n" % (timenow, message))
            self.logfile.flush()
        except IOError, e:
            logger.error("AccountingLog failure : %s" % e)

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


def processfilter(cmdstr, jobdict):
    '''Run a filter on the job, passing in all job args and processing all output'''
    extra = []
    for key, value in jobdict.iteritems():
        if isinstance(value, list):
            extra.append('%s=%s' % (key, ':'.join([escape_string(str(v), ":") for v in value])))
        else:
            extra.append('%s=%s' % (key, str(value)))
    rc, out, err = Cobalt.Util.runcommand(cmdstr, extra)
    if err:
        # strip \n from last line of stderr to make sure only
        # one \n is print'ed 
        err = err.rstrip('\n')
        print >> sys.stderr, err
    if rc != 0:
        print >> sys.stderr, "Filter %s failed" % (cmdstr)
        sys.exit(1)
    out = out.split('\n')
    for line in out:
        try:
            key, value = line.strip().split('=', 1)
        except ValueError:
            continue
        if key not in jobdict.keys():
            jobdict[key] = value
        elif isinstance(jobdict[key], list):
            jobdict[key] = value.split(':')
        elif isinstance(jobdict[key], dict):
            jobdict[key].update(eval(value))
        else:
            jobdict[key] = value


class Timer (object):
    '''the timer object keeps track of start, stop and elapsed times'''
    def __init__(self, max_time = None):
        self.__start_times = []
        self.__stop_times = []
        if max_time != None and max_time < 0:
            raise TimerException, "maximum time may not be negative (max_time=%s)" % (max_time,)
        self.__max_time = max_time
        self.__elapsed_time = 0.0
    
    def start(self):
        '''(re)start time tracking'''
        if self.is_active:
            raise TimerException, "timer already started"
        self.__start_times.append(time.time())
        
    def stop(self):
        '''stop time tracking'''
        if not self.is_active:
            raise TimerException, "timer not active"
        self.__stop_times.append(time.time())
        self.__elapsed_time += self.__stop_times[-1] - self.__start_times[-1]

    def __get_is_active(self):
        '''determine if the timer is currently running'''
        return len(self.__start_times) > len(self.__stop_times)

    is_active = property(__get_is_active, doc = "flag indicating if the time is currently active")

    def __get_elapsed_time(self):
        '''get the time elapsed while the timer has been active, including any current activity'''
        if not self.is_active:
            return self.__elapsed_time
        else:
            return self.__elapsed_time + time.time() - self.__start_times[-1]

    elapsed_time = property(__get_elapsed_time, doc = "time elapsed while the has been active, including any current activity")

    def __get_max_time(self):
        return self.__max_time

    def __set_max_time(self, max_time):
        if max_time != None and max_time < 0:
            raise TimerException, "maximum time may not be negative (max_time=%s)" % (max_time,)
        self.__max_time = max_time

    max_time = property(__get_max_time, __set_max_time)

    def __get_has_expired(self):
        '''determine if the timer has expired'''
        if self.__max_time != None:
            return self.elapsed_time > self.__max_time
        else:
            # raise TimerException, "timer does not have a maximum time associated with it"
            return False

    has_expired = property(__get_has_expired, doc = "flag indicating if the timer has expired")

    def __get_start_times(self):
        '''create and return a duplicate list of the start times'''
        return list(self.__start_times)

    start_times = property(__get_start_times, doc = "list of start times")

    def __get_stop_times(self):
        '''create and return a duplicate list of the stop times'''
        return list(self.__stop_times)

    stop_times = property(__get_stop_times, doc = "list of end times")

    def __get_elapsed_times(self):
        '''create and return a list of elapsed times'''
        elapsed_times = []
        for index in xrange(len(self.__stop_times)):
            elapsed_times.append(self.__stop_times[index] - self.__start_times[index])
        if self.is_active:
            elapsed_times.append(time.time() - self.__start_times[-1])
        return elapsed_times

    elapsed_times = property(__get_elapsed_times, doc = "list of elapsed times")

def getattrname(clsname, attrname):
    '''return mangled private attribute names so that they may be looked up in the dictionary or using getattr()'''
    if attrname[0:2] != "__" or attrname[-2:] == "__":
        return attrname
    else:
        return "_" + clsname.lstrip("_") + attrname

class ClassInfoMetaclass (type):
    '''when a class is created, add private attributes to the class that contain a reference to the class and the class name'''
    def __init__(cls, name, bases, dict):
        type.__init__(cls, name, bases, dict)
        setattr(cls, getattrname(name, "__cls"), cls)
        setattr(cls, getattrname(name, "__clsname"), name)

#
# NOTE: replaced by type.mro().  the desired order as stated below is obtained using <type>.mro()[::-1].
#
# _class_list_map = {}
# 
# def _get_class_list(cls):
#     '''
#     return a list of the classes used to construct the supplied class.  the list is ordered such that a base class will always
#     appear before classes derived from that base class.
#     '''
#     try:
#         return _class_list_map[cls]
#     except KeyError:
#         classes = []
#         classtree = inspect.getclasstree([cls], True)
#         if len(classtree) > 1:
#             for superclass, super2classes in classtree[0::2]:
#                 for sc in _get_class_list(superclass):
#                     if sc not in classes:
#                         classes.append(sc)
#         classes.append(cls)
#         _class_list_map[cls] = classes
#         return classes
#


_class_pickle_methods_map = {}
_class_unpickle_methods_map = {}

def _get_pickle_method_list(cls):
    try:
        return _class_pickle_methods_map[cls]
    except KeyError:
        methods = []
        for cls in cls.mro():
            method = getattr(cls, getattrname(cls.__name__, "__pickle_data"), None)
            if method and callable(method):
                methods.append(method)
        _class_pickle_methods_map[cls] = methods
        return methods

def _get_unpickle_method_list(cls):
    try:
        return _class_unpickle_methods_map[cls]
    except KeyError:
        methods = []
        for cls in cls.mro()[::-1]:
            method = getattr(cls, getattrname(cls.__name__, "__unpickle_data"), None)
            if method and callable(method):
                methods.append(method)
        _class_unpickle_methods_map[cls] = methods
        return methods

def pickle_data(obj):
    data = obj.__dict__.copy()
    for method in _get_pickle_method_list(obj.__class__):
        method(obj, data)
    return data

def unpickle_data(obj, data):
    obj.__dict__.update(data)
    for method in _get_unpickle_method_list(obj.__class__):
        method(obj, data)


class PickleAwareThread (object):
    __metaclass__ = ClassInfoMetaclass

    def __init__(self, group = None, target = None, name = None, args = (), kwargs = {}):
        self.__thread = Thread(group = group, target = self.__run_thread, name = name, args = args, kwargs = kwargs)
        self.__group = group
        self.__target = target
        self.__name = self.__thread.getName()
        self.__args = args
        self.__kwargs = kwargs
        self.__is_daemon = self.__thread.isDaemon()
        self.__started = False
        self.__stopped = False

    def __pickle_data(self, data):
        del data[getattrname(self.__clsname, "__thread")]

    def __unpickle_data(self, data):
        if not self.__started:
            self.__thread = Thread(group = self.__group, target = self.__run_thread, name = self.__name, args = self.__args,
                kwargs = self.__kwargs)
        else:
            self.__thread = None

    def __getstate__(self):
        return pickle_data(self)

    def __setstate__(self, data):
        unpickle_data(self, data)

    def start(self):
        if self.__thread:
            self.__started = True
            self.__thread.start()
        else:
            assert False, "thread already started"

    def __run_thread(self):
        self.__started = True
        try:
            self.run()
        finally:
            self.__stopped = True

    def run(self):
        if self.__target:
            self.__target(*self.__args, **self.__kwargs)

    def join(self, timeout = None):
        if self.__thread:
            self.__thread.join(timeout)
        elif not self.__stopped:
            raise ThreadPickledAliveException

    def getName(self):
        return self.__name

    def setName(self, name):
        self.__name = name
        if self.__thread:
            self.__thread.setName(name)

    def isAlive(self):
        if self.__thread:
            return self.__thread.isAlive()
        elif self.__stopped:
            return False
        else:
            raise ThreadPickledAliveException

    def isDaemon(self):
        return self.__is_daemon

    def setDaemon(self, daemonic):
        assert not self.__started, "cannot set daemon status of active thread"
        self.__thread.setDaemon(daemonic)
        self.is_daemon = daemonic


# routines to pickle and unpickle class and instance methods.  the routines are registered with copy_reg so that cPickle will use
# them whenever it encounters a method type.
_method_class_map = {}

def _pickle_method(method):
    func_name = method.im_func.__name__
    obj = method.im_self
    cls = method.im_class
    if cls == types.TypeType:
        cls = obj
        obj = None
    try:
        func_cls = _method_class_map[method]
    except KeyError:
        found = False
        for func_cls in cls.mro():
            try:
                func = func_cls.__dict__[getattrname(func_cls.__name__, func_name)]
            except KeyError:
                pass
            else:
                if method.im_func == func.__get__(obj, cls).im_func:
                    _method_class_map[method] = func_cls
                    found = True
                    break
        assert found == True, "method was not found!"
    func_name = getattrname(func_cls.__name__, func_name)
    return _unpickle_method, (func_name, func_cls, obj, cls)

def _unpickle_method(func_name, func_cls, obj, cls):
    try:
        func = func_cls.__dict__[func_name]
    except KeyError:
        #no longer exists.
        return None
    return func.__get__(obj, cls)

copy_reg.pickle(types.MethodType, _pickle_method, _unpickle_method)


# we made a huge mistake using pickle
def fix_set(state):
    import sets
    for k in state:
        if isinstance(state[k], sets.Set):
            state[k] = set(state[k])


def sec_to_str(t):

    '''convert a time in secs since epoch into a formated string for output
    viewing, containing timezone information.

    '''

    timestamp = None
    offset = None
    tzname = None

    

    if no_pytz:
        timestamp = time.strftime("%c", time.localtime(t))
        
        tzh = 0
        tzm = 0

        if time.strftime("%Z", time.localtime(t)).find('DT') != -1:
            tzh = (time.timezone / 3600) - 1
            tzm = time.timezone / 60 % 60
        
        else:
            tzh = time.timezone / 3600
            tzm = time.timezone / 60 % 60

        offset = "%+.2d%.2d" % (-tzh,tzm)
        tzname = time.strftime("(%Z)", time.localtime(t))

    else:
        tzname = os.environ.get('TZ','UTC')
        try:
            tz = timezone(tzname)
        except pytz.exceptions.UnknownTimeZoneError:
            tz = timezone('UTC')

        dt = datetime.fromtimestamp(t, tz)
        
        timestamp = dt.strftime("%c")
        offset = dt.strftime("%z")
        tzname = dt.strftime("(%Z)")

    time_str =  "%s %s %s" % (timestamp, offset, tzname)

    return time_str



class file_message(object):
    
    def __init__(self, filename, msg):
        self.filename = filename
        self.msg = msg
        self.msg_len = len(msg)
        self.written = 0


class disk_writer_thread(Thread):
    
    '''Thread for enabling safe non-blocking disk writes

    '''

    def __init__(self, *args, **kwargs):
        '''Initialize the thread.  And prepare it for running.

        '''
        super(disk_writer_thread, self).__init__(*args, **kwargs)
        self.msg_queue = Queue()

    
    def send(self, item):
        #Item should be a list of filename, msg tupples
        self.msg_queue.put(item)

    def extract(self):
        '''Pull out all pending messages.

        '''
        item_list = []
        while not self.msg_queue.empty():
            item_list.append(self.msg_queue.get())
        return item_list

    def close(self):
        self.msg_queue.put(None)
        self.msg_queue.join()

    def run(self):

        active_file_msgs = []
        active_fds = {}
        os.environ["STAT_SLEEP"] = '10'
        while True: #keep this thread alive

            if not self.msg_queue.empty():
                item = self.msg_queue.get()
                if item == None:
                    break
            
                active_file_msgs.append(file_message(item[0],item[1]+"\n"))
            
            if active_file_msgs == []:
                #We have no pending messages
                Cobalt.Util.sleep(5.0)
                continue


            messages_to_remove = []
            for file_msg in active_file_msgs:
                
                try:
                    fd = os.open(file_msg.filename, os.O_WRONLY|os.O_CREAT|os.O_APPEND|os.O_NONBLOCK)
                except IOError as (num, strerror):
                    
                    errcode = errno.errorcode[num]

                    if num == errno.EACCES:
                        logger.error("Unable to write to %s with error code: "
                                "%s. Permission Denied.", errcode,
                                    file_msg.filename)
                        messages_to_remove.append(file_msg)
                    elif num == errno.EDQUOT: 
                        logger.error("Unable to write to %s. Quota Exceeded.", file_msg.filename)
                        messages_to_remove.append(file_msg)
                    elif num in [errno.EFAULT,errno.EINVAL,errno.EIO]:
                        logger.error("Unable to write to %s. Fatal Error.", file_msg.filename)
                        messages_to_remove.append(file_msg) 
                    elif num == errno.ENXIO:
                        logger.error("Why are you trying to open a pipe?")
                        messages_to_remove.append(file_msg) 
                    else:
                        logger.debug("Failed to write to %s.  Holding message for retry.",
                                file_msg.filename)
                        continue
                except OSError as (num, strerror):

                    if num == errno.EACCES:
                        logger.error("Unable to write to %s. Permission Denied.",file_msg.filename)
                        messages_to_remove.append(file_msg)
                    elif num == errno.EDQUOT: 
                        logger.error("Unable to write to %s. Quota Exceeded.", file_msg.filename)
                        messages_to_remove.append(file_msg)
                    elif num in [errno.EFAULT,errno.EINVAL,errno.EIO]:
                        logger.error("Unable to write to %s. Fatal Error.", file_msg.filename)
                        messages_to_remove.append(file_msg) 
                    elif num == errno.ENXIO:
                        logger.error("Why are you trying to open a pipe?")
                        messages_to_remove.append(file_msg) 
                    else:
                        logger.debug("Failed to write to %s.  Holding message for retry.", 
                                file_msg.filename)
                        continue
                except Exception:
                    logger.critical("Unknown error recieved when writing to cobaltlog %s. "\
                            "Traceback follows:" % file_msg.filename)
                    logger.critical(traceback.format_exc())
                    logger.critical("This message has been discarded.")
                    messages_to_remove.append(file_msg)

                else:
                    active_fds[fd] = file_msg

            #if we had any error out badly enough, just remove the messages for lack of being able to write
            for msg in messages_to_remove:
                active_file_msgs.remove(msg)

            timeout = 0
            while (timeout < 3):

                try:
                
                    r_fd, w_fd, x_fd = select.select([], active_fds.keys(), [], 5.0)
                
                except IOError:
                    logger.info("Select failed for open file descriptors.  Kernel bug?")
                    break

                if w_fd == []:
                    timeout += 1
                    if timeout > 3:
                        logger.warn("Unable to write to all file descriptors this pass due to timeout.")
                    continue

                for fd in w_fd:
                    
                    #Only you can prevent partial writes
                    count = 0
                    try:
                        count = os.write(fd, file_msg.msg[file_msg.written:])
                    except IOError:
                        logger.warn("Unable to complete write to ")

                    if active_fds[fd].msg_len > (active_fds[fd].written + count):
                        active_fds[fd].written += count
                    else:
                        active_file_msgs.remove(active_fds[fd])
                        del active_fds[fd]
                        os.close(fd)

                if active_fds == {}:
                    #yep, we're done
                    break
                
            #End while timeout > 3

            #Not running out of descriptors would be nice
            if active_fds != {}:
                fd_list = active_fds.keys()
                for fd in fd_list:
                    os.close(fd)
                    del active_fds[fd]
            
            Cobalt.Util.sleep(1.0) #Don't hammer this into the ground

        #End of while True:

        logger.warn("Non-blocking File IO thread terminated.")

