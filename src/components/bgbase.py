#!/usr/bin/env python

import pprint
import re
import DB2
import Cobalt.Data

class Base(Cobalt.Data.Data):
    
    pass

class BaseSet(Cobalt.Data.DataSet):
    '''Defines a BG/L system'''
    __object__ = Base
    __ncdefs__ = {'J102':'N0', 'J104':'N1', 'J106':'N2', 'J108':'N3',
                  'J111':'N4', 'J113':'N5', 'J115':'N6', 'J117':'N7',
                  'J203':'N8', 'J205':'N9', 'J207':'NA', 'J209':'NB',
                  'J210':'NC', 'J212':'ND', 'J214':'NE', 'J216':'NF'}

    def __init__(self, racks, psetsize):
        Cobalt.Data.DataSet.__init__(self)
        self.racks = racks
        self.psetsize = psetsize
        self.buildMachine()

    def getPartIONodes(self, partname):
        '''retrieves the IOnodes for the specified partition'''
        ionodes = []
        db2 = DB2.connect(uid='bglsysdb',pwd='xxx',dsn='bgdb0').cursor()
        
        # first get blocksize in nodes
        db2.execute("select size from BGLBLOCKSIZE where blockid='%s'" % partname)
        blocksize = db2.fetchall()
        print 'blocksize is', blocksize[0][0], 'nodes'

        if int(blocksize[0][0]) < 512:
            print "small block"
            db2.execute("select * from tBGLSMALLBLOCK where blockid='%s' order by ionodepos" % partname)
            result = db2.fetchall()
            for b in result:
                rack = b[1].strip()[1:3]
                midplane = b[1].strip()[-1]
                ionodes.append("R%s-M%s-%s:%s-%s" % (rack, midplane, self.__ncdefs__[b[3].strip()],
                                                     b[4].strip(), b[5].strip()))
        else:  #match up rack and midplane(s)?
            db2.execute("select bpid from TBGLBPBLOCKMAP where blockid='%s'" % partname)
            result = db2.fetchall()
            for b in result:
                rack = b[0].strip()[1:3]
                midplane = b[0].strip()[-1]
                print "R%s-M%s" % (rack, midplane)
                #ionodes = self.getIONodes(rack, midplane)
        db2.close()
        return ionodes

    def getIONodes(self):
        '''Get location of i/o nodes from db2'''

#         db2 = DB2.connect(uid='bglsysdb',pwd='xxx',dsn='bgdb0').cursor()
#         db2.execute("SELECT LOCATION,IPADDRESS FROM tbglippool")
 #         results = db2.fetchall()
#         db2data = [(location.strip(),ip) for (location, ip) in results]
#         db2.close()

        #sample for 1:32 system
        ioreturn = [('R00-M1-NA-I:J18-U01', '172.30.0.53'),
                    ('R00-M1-NA-I:J18-U11', '172.30.0.54'),
                    ('R00-M1-NB-I:J18-U01', '172.30.0.55'),
                    ('R00-M1-NB-I:J18-U11', '172.30.0.56'),
                    ('R00-M1-NC-I:J18-U01', '172.30.0.57'),
                    ('R00-M1-NC-I:J18-U11', '172.30.0.58'),
                    ('R00-M1-ND-I:J18-U01', '172.30.0.59'),
                    ('R00-M1-ND-I:J18-U11', '172.30.0.60'),
                    ('R00-M1-NE-I:J18-U01', '172.30.0.61'),
                    ('R00-M1-NE-I:J18-U11', '172.30.0.62'),
                    ('R00-M1-NF-I:J18-U01', '172.30.0.63'),
                    ('R00-M1-NF-I:J18-U11', '172.30.0.64'),
                    ('R00-M1-N9-I:J18-U11', '172.30.0.52'),
                    ('R00-M0-N1-I:J18-U11', '172.30.0.4'),
                    ('R00-M0-N2-I:J18-U01', '172.30.0.5'),
                    ('R00-M0-N2-I:J18-U11', '172.30.0.6'),
                    ('R00-M0-N3-I:J18-U01', '172.30.0.7'),
                    ('R00-M0-N3-I:J18-U11', '172.30.0.8'),
                    ('R00-M0-N4-I:J18-U01', '172.30.0.9'),
                    ('R00-M0-N4-I:J18-U11', '172.30.0.10'),
                    ('R00-M0-N5-I:J18-U01', '172.30.0.11'),
                    ('R00-M0-N5-I:J18-U11', '172.30.0.12'),
                    ('R00-M0-N6-I:J18-U01', '172.30.0.13'),
                    ('R00-M0-N6-I:J18-U11', '172.30.0.14'),
                    ('R00-M0-N7-I:J18-U01', '172.30.0.15'),
                    ('R00-M0-N7-I:J18-U11', '172.30.0.16'),
                    ('R00-M0-N8-I:J18-U01', '172.30.0.17'),
                    ('Rp00-M0-N8-I:J18-U11', '172.30.0.18'),
                    ('R00-M0-N9-I:J18-U01', '172.30.0.19'),
                    ('R00-M0-N9-I:J18-U11', '172.30.0.20'),
                    ('R00-M0-NA-I:J18-U01', '172.30.0.21'),
                    ('R00-M0-NA-I:J18-U11', '172.30.0.22'),
                    ('R00-M0-NB-I:J18-U01', '172.30.0.23'),
                    ('R00-M0-NB-I:J18-U11', '172.30.0.24'),
                    ('R00-M0-NC-I:J18-U01', '172.30.0.25'),
                    ('R00-M0-NC-I:J18-U11', '172.30.0.26'),
                    ('R00-M0-ND-I:J18-U01', '172.30.0.27'),
                    ('R00-M0-ND-I:J18-U11', '172.30.0.28'),
                    ('R00-M0-NE-I:J18-U01', '172.30.0.29'),
                    ('R00-M0-NE-I:J18-U11', '172.30.0.30'),
                    ('R00-M0-NF-I:J18-U01', '172.30.0.31'),
                    ('R00-M0-N0-I:J18-U01', '172.30.0.1'),
                    ('R00-M0-N0-I:J18-U11', '172.30.0.2'),
                    ('R00-M0-N1-I:J18-U01', '172.30.0.3'),
                    ('R00-M0-NF-I:J18-U11', '172.30.0.32'),
                    ('R00-M1-N0-I:J18-U01', '172.30.0.33'),
                    ('R00-M1-N0-I:J18-U11', '172.30.0.34'),
                    ('R00-M1-N1-I:J18-U01', '172.30.0.35'),
                    ('R00-M1-N1-I:J18-U11', '172.30.0.36'),
                    ('R00-M1-N2-I:J18-U01', '172.30.0.37'),
                    ('R00-M1-N2-I:J18-U11', '172.30.0.38'),
                    ('R00-M1-N3-I:J18-U01', '172.30.0.39'),
                    ('R00-M1-N3-I:J18-U11', '172.30.0.40'),
                    ('R00-M1-N4-I:J18-U01', '172.30.0.41'),
                    ('R00-M1-N4-I:J18-U11', '172.30.0.42'),
                    ('R00-M1-N5-I:J18-U01', '172.30.0.43'),
                    ('R00-M1-N5-I:J18-U11', '172.30.0.44'),
                    ('R00-M1-N6-I:J18-U01', '172.30.0.45'),
                    ('R00-M1-N6-I:J18-U11', '172.30.0.46'),
                    ('R00-M1-N7-I:J18-U01', '172.30.0.47'),
                    ('R00-M1-N7-I:J18-U11', '172.30.0.48'),
                    ('R00-M1-N8-I:J18-U01', '172.30.0.49'),
                    ('R00-M1-N8-I:J18-U11', '172.30.0.50'),
                    ('R00-M1-N9-I:J18-U01', '172.30.0.51')]

        ioreturn.sort()

        # if only using 1 ionode per ionode processor card, filter out
        # every other entry in ioreturn
        if self.psetsize in [32, 128]:
            for x in ioreturn:
                if 'U11' in x[0]:
                    print 'deleting', x
                    ioreturn.remove(x)
            
        return [re.sub('-I', '', x[0]) for x in ioreturn]

    def buildMachine(self):
        '''build machine representation from racks and psetsize'''
        ionodes = self.getIONodes()
        total_ionodes = (1024/self.psetsize) * self.racks  #total ionodes
        total_midplanes = self.racks * 2
        iopermidplane = total_ionodes/total_midplanes
        print 'total_ionodes: %d\ntotal_midplanes: %d\niopermidplane: %d' % (total_ionodes, total_midplanes, iopermidplane)
        print 'length of ionodes', len(ionodes)
        q = total_ionodes
        while q > 0:
            print 'self.psetsize/q', self.psetsize/q

            for x in range(0, total_ionodes, q):
                print 'io extent=%d, starting ionode is %d' % (q, x)
                if q == total_ionodes:
                    print 'defining whole machine block'
                    base_type = 'full'
                elif q == iopermidplane*2:
                    print 'defining rack', x / (iopermidplane*2)
                    base_type = 'rack'
                elif q == iopermidplane:
                    print 'defining R%d M%d' % (x / (iopermidplane*2), (x / iopermidplane) % 2)
                    base_type = 'midplane'
                else:
                    print 'R%d M%d N%d' % (x / (iopermidplane*2), (x / iopermidplane) % 2, x % (iopermidplane))
                    base_type = 'block'

                includedIOn = ','.join(['%s' % ionodes[y] for y in range(x, x+q)])
                computeNodes = q * self.psetsize
                start_ionode = x
                rack = '%02d' % (x / (iopermidplane*2))
                midplane = '%d' % ((x / iopermidplane) % 2)
                self.Add({'tag':'base', 'type':base_type, 'rack':rack, 'midplane':midplane,
                          'ionodes':includedIOn, 'computenodes':'%d' % computeNodes, 'psets':'%d' % q,
                          'state':'idle'})

            q = q / 2
        return

    def getParents(self, block):
        '''returns parents of block, based on ionodes'''
        parents = [x for x in self.data if block.get('ionodes') in x.get('ionodes') and block.get('ionodes') != x.get('ionodes')]
        return parents

    def getChildren(self, block):
        '''returns children of block, based on ionodes'''
        cionodes = block.get('ionodes').split(',')
        csize = len(cionodes)

        children = []
        for b in self.data:
            if len(b.get('ionodes').split(',')) < csize and [x for x in b.get('ionodes').split(':') if x in cionodes]:
                children.append(b)
        return children

    def getMidplaneIONodes(self, rack, midplane):
        '''returns the ionodes in the midplane specified'''
        io = self.Get([{'tag':'base', 'rack':rack, 'midplane':midplane, 'ionodes':'*'}])
        if io:
            return io[0].get('ionodes')
        else:
            return None
        
        
if __name__ == '__main__':
    newbaseset = BaseSet(1, 32)
    machine = newbaseset.Get([{'tag':'base', 'psets':'*', 'startnc':'*', 'rack':'*', 'midplane':'*',
                               'ionodes':'*', 'computenodes':'*', 'type':'*', 'state':'*'}])
    pprint.pprint(machine)
    print 'parents of 16:17:18:19'
    child = newbaseset.Get([{'tag':'base', 'psets':'*', 'startnc':'*', 'rack':'*', 'midplane':'*',
                             'ionodes':'R00-M1-NC:J18-U01', 'computenodes':'*', 'type':'*', 'state':'*'}])
    testparents = newbaseset.getParents(child[0])
    for p in testparents:
        print "%s-%s: R%s M%s %s" % (p.get('computenodes'), p.get('type'), p.get('rack'), p.get('midplane'), p.get('ionodes'))

    print 'children'
    testchildren = newbaseset.getChildren(child[0])
    for c in testchildren:
        print "%s-%s: R%s M%s %s" % (c.get('computenodes'), c.get('type'), c.get('rack'), c.get('midplane'), c.get('ionodes'))

    midio = newbaseset.getMidplaneIONodes('00', '0')
    print midio
    
    print newbaseset.getPartIONodes("64_R001_J106_N2")
    print newbaseset.getPartIONodes("NCAR_R00")
    