# -*- coding: utf-8 -*-
"""
Created on Tue Sep 20 12:06:00 2016
@author: Ingo Scholtes

(c) Copyright ETH Zurich, Chair of Systems Design, 2015-2016
"""

import numpy as _np
import collections as _co
import bisect as _bs
import sys as _sys
import operator

import scipy.sparse as _sparse
import scipy.sparse.linalg as _sla
import scipy.linalg as _la

from pathpy.Log import *
from pathpy.HigherOrderNetwork import HigherOrderNetwork


class Paths:
    """
    Instances of this class represent path statistics which can be analyzed using higher- and multi-order network
    models. The origin of the path statistics can be (i) n-gram files which provide us with a list of paths 
    in terms of n-grams of varying lengths, or (ii) a temporal network instance which provides us with a set of
    time-respecting paths based on a given maximum time difference delta.
    """

    def __init__(self):
        """
        Creates an empty Paths object
        """

        # the meanining of the paths dictionary is as follows: 
        # - paths[k] is a dictionary containing all paths of length k, indexed by a path tuple p = (u,v,w,...)
        # - for each tuple p of length k, paths[k][p] contains a tuple (i,j) where i refers to the number 
        #       of times p occurs as a subpath of a longer path, and j refers to the number of times p
        #       occurs as a *real* or *longest* path (i.e. not being a subpath of a longer path)
        self.paths = _co.defaultdict( lambda: _co.defaultdict( lambda: _np.array([0,0]) ))
        self.separator = ','



    def summary(self):
        """ 
        Returns a string containing basic summary info of this Paths instance
        """
        sum = 0
        spsum = 0
        lpsum = 0
        maxL = -1
        avgL = 0
        nodes = set()
        for k in self.paths:
            for p in self.paths[k]:
                sum += self.paths[k][p].sum()
                spsum += self.paths[k][p][0]
                lpsum += self.paths[k][p][1]
                avgL += self.paths[k][p][1] * k
                for v in p:
                    nodes.add(v)
            maxL = max(maxL, k)
        avgL = avgL / lpsum

        summary = 'Number of paths (unique/sub paths/total):\t' +  str(lpsum) + ' (' + str(self.getUniquePaths()) + '/'+ str(spsum) + '/' + str(sum) + ')\n'
        summary += 'Nodes:\t\t\t\t' + str(len(nodes)) + '\n'
        summary += 'Edges:\t\t\t\t' + str(len(self.paths[1])) + '\n'
        summary += 'Max. path length:\t\t' + str(maxL) + '\n'
        summary += 'Avg path length:\t\t' + str(avgL) + '\n'
        for k in self.paths:
            sum = 0 
            spsum = 0
            lpsum = 0
            for p in self.paths[k]:
                sum += self.paths[k][p].sum()          
                spsum += self.paths[k][p][0]
                lpsum += self.paths[k][p][1]
            summary += 'Paths of length k = ' + str(k) + '\t\t' + str(lpsum) + ' (' + str(self.getUniquePaths(l=k, considerLongerPaths=False)) + '/' + str(spsum) + '/'+ str(sum) +  ')\n'
        return summary


    def getSequence(self, stopchar='|'):
        """
        Returns a single sequence in which all 
        paths have been concatenated. Individual 
        paths can be separated by a stop character.
        """

        Log.add('Concatenating paths to sequence ...')

        sequence = []
        for l in self.paths:
            for p in self.paths[l]:
                segment = []
                for s in p:
                    segment.append(s)
                if not stopchar == '':
                    segment.append(stopchar)
                for f in range(self.paths[l][p][1]):
                    sequence += segment

        Log.add('finished')
        return sequence


    def getUniquePaths(self, l=0, considerLongerPaths=True):
        L = 0
        lmax = l
        if considerLongerPaths:
            lmax = max(self.paths)
        for j in range(l, lmax+1):
            for p in self.paths[j]:
                if self.paths[j][p][1]>0:
                    L += 1
        return L


    def __str__(self):
        """
        Returns the default string representation of 
        this Paths instance
        """
        return self.summary()


    def readEdges(filename=None, separator=',', weight = False, undirected=False, maxlines=_sys.maxsize, expandSubPaths=True):
        """
        Reads data from a file containing multiple lines of *edges* of the
        form "v,w,frequency,X" (where frequency is optional and X are arbitrary additional columns). The default separating 
        character ',' can be changed. In order to calculate the statistics of paths of any length, 
        by default all subpaths of length 1 (i.e. single nodes) contained in an edge will be considered.
        """
        p = Paths()

        p.separator = separator

        with open(filename, 'r') as f:
            Log.add('Reading edge data ... ')
            line = f.readline()
            n = 1 
            while line and n <= maxlines:
                fields = line.rstrip().split(separator)
                assert len(fields) >= 2, 'Error: malformed line: ' + line

                path = (fields[0],fields[1])

                if weight:                    
                    frequency = int(fields[2])
                else:
                    frequency = 1
                p.paths[1][path] += (0,frequency)
                if undirected:
                    reverse_path = (fields[1],fields[0])
                    p.paths[1][reverse_path] += (0,frequency)
                line = f.readline()
                n += 1
        # end of with open()
        
        if expandSubPaths:
            p.expandSubPaths()
        Log.add('finished.')

        return p


    def readFile(filename=None, separator=',', pathFrequency = False, maxlines=_sys.maxsize, maxN=_sys.maxsize, expandSubPaths = True):
        """ 
        Reads path data from a file containing multiple lines of n-grams of the 
        form "a,b,c,d,frequency" (where frequency is optional). The default separating 
        character ',' can be changed. Each n-gram will be interpreted as a path of length n-1, 
        i.e. bigrams a,b are considered as path of length one, trigrams a,b,c as path of length two, etc.
        In order to calculate the statistics of paths of any length, by default all subpaths of 
        length k < n-1 contained in an n-gram will be considered. I.e. for n=4 the four-gram a,b,c,d 
        will be considered as a single (longest) path of length n-1 = 3 and three subpaths 
        a->b, b->c, c->d of length k=1 and two subpaths a->b->c amd b->c->d of length k=2 will be 
        additionally counted.

        @param filename: name of the n-gram file to read data from

        @param separator: the character used to separate nodes on the path, i.e. using a 
            separator character of ';' n-grams are represented as a;b;c;...

        @param pathFrequency: if set to true, the last entry in each n-gram will be interpreted as 
            weight (i.e. frequency of the path), e.g. a,b,c,d,4 means that four-gram a,b,c,d has weight four.
            False by default, which means each path occurrence is assigned a default weight of one (adding weights 
            of multiple occurrences).

        @param maxlines: The maximum number of lines (i.e. ngrams) to read from the input file

        @param maxN: The maximum n for the n-grams to read, i.e. setting maxN to 15 will ignore all n-grams of length 
            16 and longer, which means that only paths up to length n-1 are considered.

        @param expandSubPaths: by default all subpaths of the given ngrams are generated, i.e. 
            for an input file with a single trigram a;b;c a path a->b->c of length two will be generated
            as well as two subpaths a->b and b->c of length one
        """
        assert filename is not "", 'Empty filename given'
    
        # If subpath expansion is applied, we keep the information how many times a path 
        # has been observed as a subpath, and how many times as a "real" path        

        p = Paths()

        p.separator = separator
        maxL = 0 

        with open(filename, 'r') as f:
            Log.add('Reading ngram data ... ')
            line = f.readline()
            n = 1 
            while line and n <= maxlines:
                fields = line.rstrip().split(separator)
                path = ()
                # Add frequency of "real" path to second component of occurrence counter
                if pathFrequency:
                    for i in range(0, len(fields)-1):
                        # Omit empty fields
                        v = fields[i].strip()
                        if len(v)>0:
                            path += (v,)
                    frequency = int(fields[len(fields)-1])
                    if len(path) <= maxN:
                        p.paths[len(path)-1][path] += (0,frequency)
                        maxL = max(maxL, len(path)-1)
                    else: # cut path at maxN
                        p.paths[maxN-1][path[:maxN]] += (0,frequency)
                        maxL = max(maxL, maxN-1)
                else:
                    for i in range(0, len(fields)):
                        # Omit empty fields
                        v = fields[i].strip()
                        if len(v)>0:
                            path += (v,)
                    if len(path) <= maxN:
                        p.paths[len(path)-1][path] += (0,1)
                        maxL = max(maxL, len(path)-1)
                    else: # cut path at maxN
                        p.paths[maxN-1][path[:maxN]] += (0,1)
                        maxL = max(maxL, maxN-1)
                line = f.readline()
                n += 1                
        # end of with open()
        Log.add('finished. Read ' + str(n-1) + ' paths with maximum length ' + str(maxL))
        
        if expandSubPaths:
            p.expandSubPaths()
        Log.add('finished.')

        return p


    def ObservationCount(self):
        """
        Returns the total number of observed pathways of any length 
        (includes multiple observations for paths with a frequency weight)
        """

        sum = 0
        for k in self.paths:
            for p in self.paths[k]:
                sum += self.paths[k][p][1]
        return sum


    def expandSubPaths(self):
        """
        This function implements the sub path expansion, i.e. 
        for a four-gram a,b,c,d, the paths a->b, b->c, c->d of 
        length one and the paths a->b->c and b->c->d of length 
        two will be counted.
        """     
        Log.add('Calculating sub path statistics ... ')

        # the expansion of all subpaths in paths with a maximum path length of maxL
        # neccessarily generates paths of *any* length up to MaxL.
        # Forcing the generation of all these indices here, prevents us 
        # from mutating indices during subpath creation. The fact that indices are
        # immutable allows us to use efficient iterators and prevent unncessary copying

        # Thanks to the use of defaultdict, the following trick will prevent us from 
        # repeatedly testing whether l already exists as a key
        for l in range(max(self.paths)):
                self.paths[l] = self.paths[l]

        # expand subpaths in all paths of any length ... 
        for pathLength in self.paths:
            for path in self.paths[pathLength]:
                                
                # The frequency is given by the number of occurrences as longest 
                # path, which is stored in the second entry of the numpy array
                frequency = self.paths[pathLength][path][1]

                # Generate all subpaths of length k for k = 0 to k = pathLength-1 (inclusive)
                for k in range(0, pathLength):
                    # Generate subpaths of length k for all start indices s for s = 0 to s = pathLength-k (inclusive)
                    for s in range(0, pathLength-k+1):
                        # Add frequency as a subpath to *first* entry of occurrence counter
                        self.paths[k][path[s:s+k+1]] += (frequency,0)


    @staticmethod
    def fromTemporalNetwork(tempnet, delta=1, maxLength=_sys.maxsize):
        """ Calculates the frequency of all time-respecting paths up to maximum length of k, assuming 
        a maximum temporal distance of delta between consecutive time-stamped links on a path. 
        This (static) method returns an instance of the class Paths, which can subsequently be used to 
        generate higher-order network representations based on the path statistics.

        @param delta: Indicates the maximum temporal distance up to which time-stamped links will be 
        considered to contribute to time-respecting paths. For (u,v;3) and (v,w;7) a time-respecting path (u,v)->(v,w) 
        will be inferred for all 0 < delta <= 4, while no time-respecting path will be inferred for all delta > 4. 
        If the max time diff is not set specifically, the default value of delta=1 will be used, meaning that a
        time-respecting path u -> v -> w will only be inferred if there are *directly consecutive* time-stamped 
        links (u,v;t) (v,w;t+1). Every time-stamped edge is further considered a path of length one, i.e. for maxLength=1 
        this function will simply return the statistics of time-stamped edges.
        
        @param maxLength: Indicates the maximum length up to which time-respecting paths should be calculated, 
             which can be limited due to computational efficiency. A value of k will generate all time-respecting paths 
             consisting of up to k time-stamped links. Note that generating a multi-order model with a maximum order of k 
             requires to extract time-respecting paths with *at least* length k. If a limitation of the maxLength is not 
             required for computational reasons, this parameter should not be set (as it will change the statistics of 
             paths)
        """
        
        if maxLength==_sys.maxsize:
            Log.add('Extracting time-respecting paths for delta = ' + str(delta) + ' ...')
        else:
            Log.add('Extracting time-respecting paths up to length ' + str(k) + ' for delta = ' + str(delta) + ' ...')      

        # for dictionary p.paths paths[k] contains a list of all 
        # time-respecting paths p with length k and paths[k][p] contains 
        # a two-dimensional counter whose first component counts the number of 
        # occurrences of p as subpath of a longer path and whose second component counts 
        # the number of occurrences of p as "real" path
        p = Paths()

        # a dictionary for those paths that can possibly be extended 
        # by future time-stamped links
        candidates = _co.defaultdict ( lambda: _co.defaultdict( lambda: list() ) )

        # a dictionary of longest time-respecting paths (i.e. not those paths which are 
        # subpaths of a longer time-respecting path
        longest_paths = set()

        # TODO: We need to keep the information how many times a time-respecting path 
        # has been observed as a *subpath* of a longer time-respecting path, and how many 
        # times as a "real", i.e. *longest* time-respecting path

        # loop over all time stamps t of edges
        for t in tempnet.ordered_times:

            for e in tempnet.time[t]:

                # each edge is a new longest path of length one (independent of delta)
                # p.paths[1][(e[0], e[1])] += (0,1)

                # hypothesize that the edge is the root of a longest time-respecting path
                root = True                

                # add edge to candidates that can be extended by future paths
                if maxLength>1:
                    candidates[t][e[1]].append( ( (e[0], e[1], t), ) )

                # check whether candidates with time stamps in [t-delta, t) can be continued ... 
                for t_prev in candidates:
                    if t_prev >= t-delta and t_prev < t:
                        # ... and where the last node is e[0] ...
                        if e[0] in candidates[t_prev]:
                            for c in candidates[t_prev][e[0]]:

                                # c is a path (p_0, p_1, ...) which ends in node e[0]                            
                                new_path = c + ((e[0], e[1], t),)

                                # (e[0], e[1]) is not the root of the longest path
                                # since it is a continuation of a longer path
                                root = False

                                # increment the path counter (for being a subpath)
                                # p.paths[len(new_path)-1][new_path] += (1,0)

                                # if the newly found path continues what has previously been considered 
                                # a longest path, we must correct the longest_path counter
                                longest_paths.discard(c)
                                longest_paths.add(new_path)

                                # finally, we add the newly found path to candidates for paths 
                                # which can be continued by future edges
                                if len(new_path)<maxLength:
                                    candidates[t][e[1]].append(new_path)
                
                # if the time-stamped edge is the root of a 
                # longest time-respecting path, we start a new longest path 
                if root:
                    longest_paths.add( ((e[0], e[1], t),) )
            
            # remove all candidate paths whose time stamp is smaller than t-delta
            for t_prev in list(candidates.keys()):
                if t_prev < t-delta:                    
                    del(candidates[t_prev])
        
        # Count occurrences as longest time-respecting path
        for x in longest_paths: 
            path = (x[0][0],)
            for edge in x:
                path += (edge[1],)
            p.paths[len(x)][path] += _np.array([0,1])

        # expand all sub paths of longest paths
        p.expandSubPaths()
        Log.add('finished.')

        return p
    

    def addPathTuple(self, path, expandSubPaths=True, frequency=(0,1)):
        """
        Adds a tuple of elements as a path
        if the elements are not strings, a conversion 
        """
        
        assert len(path)>0, 'Error: paths needs to contain at least one element'        

        if type(path[0]) == str:
            path_str = path
        else: 
            path_str = tuple(map(str, path))

        self.paths[len(path)-1][path_str] += frequency

        if expandSubPaths:
            for k in range(0, len(path_str)-1):
                for s in range(len(path_str)-k):
                    # for all start indices from 0 to n-k

                    subpath = ()
                    # construct subpath
                    for i in range(s, s+k+1):
                        subpath += (path_str[i],)
                    # add subpath weight to first component of occurrences                   
                    self.paths[k][subpath] += (1, 0)



    def getContainedPaths(p, node_filter):
        """
        Returns maximum-length sub-paths of p which
        only contain nodes given in the node_filter

        @param p: a path tuple to check for contained paths, e.g. (a, b, c, d, e, f, g)
        @param node_filter: a set of nodes limiting the contained paths, e.g. [a,b,d,f,g]
            For the example above, this method will return [(a,b), (d,), (f,g)]
        """
        contained_paths = []
        current_path = ()
        for k in range(0, len(p)):
            if p[k] in node_filter:
                current_path += (p[k],)
            else:
                if len(current_path)>0:
                    contained_paths.append(current_path)
                    current_path = ()
        if len(current_path)>0:
            contained_paths.append(current_path)        
        
        return contained_paths


    def filterPaths(self, node_filter, minLength=0, maxLength=sys.maxsize):
        """
        Returns a new paths object containing only paths between nodes in a given 
        filter set. For each of the paths in the current Paths object,
        the set of maximally contained subpaths between nodes in node_filter is extracted.

        @param node_filter: the nodes for which paths with be extracted from the current
            set of paths
        @param minLength: the minimum length of paths to extract
        @param maxLength: the maximum length of paths to extracr
        """                
    
        p = Paths()
        for l in self.paths:
            for x in self.paths[l]:
                if self.paths[l][x][1]>0:                    
                    
                    # determine all contained subpaths which only pass through nodes in node_filter
                    contained = Paths.getContainedPaths(x, node_filter)                    
                    for s in contained:
                        if len(s)-1>=minLength and len(s)-1<=maxLength:
                            p.addPathTuple(s, expandSubPaths=True, frequency=self.paths[l][x][1])
        return p



    def projectPaths(self, mapping):
        """
        Returns a new path object in which nodes have been mapped to different labels
        given by an arbitrary mapping function. This can be used, e.g., to map page click streams 
        to topic streams, based on a mapping from pages to topics
        
        @param mapping: a dictionary, mapping nodes to labels
        """
        p = Paths()
        for l in self.paths:
            for x in self.paths[l]:
                if self.paths[l][x][1]>0:
                    newP = ()
                    for v in x:
                        newP += (mapping[v],)
                    p.addPathTuple(newP, expandSubPaths=True, frequency=self.paths[l][x][1])
        return p



    def addPath(self, ngram, separator=',', expandSubPaths = True, pathFrequency = None):
        """
        Adds the path(s) of a single n-gram to the path statistics object.

        @param ngram: An ngram representing a path between nodes, separated by the separator character, e.g. 
            the 4-gram a;b;c;d represents a path of length three (with separator ';')

        @param separator: The character used as separator for the ngrams (';' by default)

        @param expandSubPaths: by default all subpaths of the given ngram are generated, i.e. 
            for the trigram a;b;c a path a->b->c of length two will be generated 
            as well as two subpaths a->b and b->c of length one

        @weight weight: the weight (i.e. frequency) of the ngram
        """

        fields = ngram.rstrip().split(separator)
        path = ()        
        for i in range(0, len(fields)):
            path += (fields[i],)

        # add the occurrences as *longest* path to the second component of the numpy array
        if pathFrequency != None:
            self.paths[len(path)-1][path] += (0, pathFrequency)
        else:
            self.paths[len(path)-1][path] += (0, 1)

        if expandSubPaths:
            for k in range(0, len(path)-1):
                for s in range(len(path)-k):
                    # for all start indices from 0 to n-k

                    subpath = ()
                    # construct subpath
                    for i in range(s, s+k+1):
                        subpath += (path[i],)
                    # add subpath weight to first component of occurrences
                    if pathFrequency != None:                        
                        self.paths[k][subpath] += (pathFrequency, 0)
                    else:
                        self.paths[k][subpath] += (1, 0)



    def getSlowDownFactor(self, k=2, lanczosVecs = 15, maxiter = 1000):    
        """
        Returns a factor S that indicates how much slower (S>1) or faster (S<1)
        a diffusion process evolves in a k-order model of the path statistics
        compared to what is expected based on a first-order model. This value captures 
        the effect of order correlations of length k on a diffusion process which evolves 
        based on the observed paths.
        """

        assert k>1, 'Slow-down factor can only be calculated for orders larger than one'
    
        #NOTE to myself: most of the time goes for construction of the 2nd order
        #NOTE            null graph, then for the 2nd order null transition matrix
    
        gk = HigherOrderNetwork(self, k=k)
        gkn = HigherOrderNetwork(self, k=k, nullModel = True)
    
        Log.add('Calculating slow down factor ... ', Severity.INFO)

        # Build transition matrices
        Tk = gk.getTransitionMatrix()
        Tkn = gkn.getTransitionMatrix()
    
        # Compute eigenvector sequences
        # NOTE: ncv=13 sets additional auxiliary eigenvectors that are computed
        # NOTE: in order to be more confident to find the one with the largest
        # NOTE: magnitude, see
        # NOTE: https://github.com/scipy/scipy/issues/4987
        w2 = _sla.eigs(Tk, which="LM", k=2, ncv=lanczosVecs, return_eigenvectors=False, maxiter=maxiter)
        evals2_sorted = _np.sort(-_np.absolute(w2))

        w2n = _sla.eigs(Tkn, which="LM", k=2, ncv=lanczosVecs, return_eigenvectors=False, maxiter=maxiter)
        evals2n_sorted = _np.sort(-_np.absolute(w2n))

        Log.add('finished.', Severity.INFO)
    
        return _np.log(_np.abs(evals2n_sorted[1]))/_np.log(_np.abs(evals2_sorted[1]))



    def getEntropyGrowthRateRatio(self, method='MLE', k=2, lanczosVecs=15, maxiter=1000):
        """
        Computes the ratio between the entropy growth rate ratio between
        the k-order and first-order model of a temporal network t. Ratios smaller
        than one indicate that the temporal network exhibits non-Markovian characteristics
        """
    
        # NOTE to myself: most of the time here goes into computation of the
        # NOTE            EV of the transition matrix for the bigger of the
        # NOTE            two graphs below (either 2nd-order or 2nd-order null)

        assert (method == 'MLE' or method=='Miller'), 'Only methods MLE or Miller are supported'
    
        # Generate k-order network
        gk = HigherOrderNetwork(self, k=k)
        g1 = HigherOrderNetwork(self, k=1)
    
        Log.add('Calculating entropy growth rate ratio ... ', Severity.INFO)
    
        # Compute entropy growth rate of observed transition matrix
        A = g1.getAdjacencyMatrix(weighted=False, transposed = True)
        Tk = gk.getTransitionMatrix()
        Tk_pi = HigherOrderNetwork.getLeadingEigenvector(Tk, normalized=True, lanczosVecs=lanczosVecs, maxiter=maxiter)

        Tk.data *=  _np.log2(Tk.data)

        # Apply Miller correction to the entropy estimation
        if method == 'Miller':
            # Here, K is the number of different k-paths that can exist based on the
            # observed edges
            K = (A**k).sum()
            print('K = ', K)

            # N is the number of observations used to estimate the transition probabilities
            # in the second-order network. This corresponds to the total edge weight in the 
            # k-order network, or - alternatively - to the number of paths of length k
            N = 0
            for p in self.paths[k]:
                N += self.paths[k][p].sum()
            print('N = ', N)
            Hk = _np.sum( Tk * Tk_pi ) + (K-1)/(2*N)
        else:
            # simple MLE estimation
            Hk = -_np.sum( Tk * Tk_pi )

        Hk = _np.absolute(Hk)

        # Compute entropy rate of null model       
        gk_n = HigherOrderNetwork(self, k=k, nullModel = True)

        # For the entropy rate of the null model, no Miller correction is needed
        # since we assume that transitions correspond to the true probabilities
        Tk_n = gk_n.getTransitionMatrix()
        Tk_n_pi = HigherOrderNetwork.getLeadingEigenvector(Tk_n)
        Tk_n.data *=  _np.log2(Tk_n.data)
        Hk_n = -_np.sum( Tk_n * Tk_n_pi )
        Hk_n = _np.absolute(Hk_n)

        Log.add('finished.', Severity.INFO)

        # Return ratio
        return Hk/Hk_n   


    def BetweennessPreference(self, k=1, normalized=False, method = 'MLE'):
        """
        Calculates the k-th order betweenness preferences of 
        k-th order nodes based on the mutual information of path 
        statistics of length k+1. The minimum order k for which 
        betweenness preference can be computed is one, in which 
        case for each first-order node v all paths s->v->d of length 
        two will be considered for all nodes s and d. In the general case of 
        order k, for a k-th order node v_1-...-v_{k} the statistics 
        of all paths s-v_1-...v_{k-1} -> v_1-...-v_{k} -> v_2-...-v_{k}-d
        of length two in the k-th order network (i.e. length k+1) in the first-order
        network will be considered in the calculation.

        @order: The order of nodes for which to calculate betweenness preference

        @nornalized: whether or not to normalize betweenness preference values

        @method: which method to use for the entropy calculation. The default 'MLE' uses 
            the standard Maximum-Likelihood estimation of entropy. Setting method to 
            'Miller' additionally applies a Miller-correction. see e.g. 
            Liam Paninski: Estimation of Entropy and Mutual Information, Neural Computation 5, 2003 or 
            http://www.nowozin.net/sebastian/blog/estimating-discrete-entropy-part-2.html
        """
        assert method == 'MLE' or method =='Miller'
        raise NotImplementedError



    def getNodes(self):
        """
        Returns the list of nodes for the underlying 
        set of paths
        """
        nodes = set()
        for p in self.paths[0]:
            nodes.add(p[0])
        return nodes


    def getDistanceMatrix(self):
        """
        Calculates shortest path distances between all pairs of 
        nodes based on the observed shortest paths (and subpaths)
        """
        shortest_path_lengths = _co.defaultdict( lambda: _co.defaultdict( lambda: _np.inf ) )
        
        Log.add('Calculating distance matrix based on empirical paths ...', Severity.INFO)
        # Node: no need to initialize shortest_path_lengths[v][v] = 0
        # since paths of length zero are contained in self.paths

        for l in self.paths:
            for p in self.paths[l]:
                start = p[0]
                end = p[-1]
                if l < shortest_path_lengths[start][end]:
                    shortest_path_lengths[start][end] = l
        
        Log.add('finished.', Severity.INFO)

        return shortest_path_lengths


    def getShortestPaths(self):
        """
        Calculates all observed shortest paths (and subpaths) between 
        all pairs of nodes
        """
        shortest_paths = _co.defaultdict( lambda: _co.defaultdict( lambda: set() ) )
        shortest_path_lengths = _co.defaultdict( lambda: _co.defaultdict( lambda: _np.inf ) )
        
        Log.add('Calculating shortest paths based on empirical paths ...', Severity.INFO)

        for l in self.paths:
            for p in self.paths[l]:
                s = p[0]
                d = p[-1]
                # we found a path of length l from s to d
                if l < shortest_path_lengths[s][d]:
                    shortest_path_lengths[s][d] = l
                    shortest_paths[s][d] = set()
                    shortest_paths[s][d].add(p)
                elif l == shortest_path_lengths[s][d]:
                    shortest_paths[s][d].add(p)

        Log.add('finished.', Severity.INFO)
        
        return shortest_paths


    def BetweennessCentrality(self, normalized=False):
        """
        Calculates the betweenness centrality of nodes based on
        observed shortest paths between all pairs of nodes
        """

        node_centralities = _co.defaultdict( lambda: 0 )
        shortest_paths = self.getShortestPaths()

        for s in shortest_paths:
            for d in shortest_paths[s]:
                for p in shortest_paths[s][d]:
                    for x in p[1:-1]:
                        if s != d != x:
                            # print('node ' + x + ': ' + str(1.0 / len(shortest_paths[start][end])))                            
                            node_centralities[x] += 1.0 / len(shortest_paths[s][d])
                            # node_centralities[x] += 1.0
        if normalized:
            m = max(node_centralities.values())
            for v in node_centralities:
                node_centralities[v] /= m

        # assign zero values to nodes not occurring on shortest paths
        nodes = self.getNodes()
        for v in nodes:
            node_centralities[v] += 0

        return node_centralities


    def ClosenessCentrality(self, normalized=False):
        """
        Calculates the closeness centrality of nodes based on
        observed shortest paths between all nodes 
        """

        node_centralities = _co.defaultdict( lambda: 0 )
        shortest_path_lengths = self.getDistanceMatrix()                

        for x in shortest_path_lengths:
            for d in shortest_path_lengths[x]:
                if x != d and shortest_path_lengths[x][d] < _np.inf:
                    node_centralities[x] += 1.0 / shortest_path_lengths[x][d]

        # assign zero values to nodes not occurring
        nodes = self.getNodes()
        for v in nodes:
            node_centralities[v] += 0

        return node_centralities
    

    def VisitationProbabilities(self):
        """
        Calculates the probabilities that randomly chosen paths
        pass through nodes. If 5 out of 100 paths (of any length) contain 
        node v, it will be assigned a value of 0.05. This measure can be 
        interpreted as path-based ground truth for the notion of importance 
        captured by PageRank applied to a graphical abstraction of the paths.
        """

        Log.add('Calculating path visitation probabilities...', Severity.INFO)

        # entries capture the probability that a given node is visited on an arbitrary path
        # Note: this is identical to the subpath count of zero-length paths
        # (i.e. the relative frequencies of nodes across all pathways)
        visitation_probabilities = _co.defaultdict( lambda: 0 )

        # total number of visits
        visits = 0.0
        
        for l in self.paths:
            for p in self.paths[l]:
                for v in p:
                    # count occurrences in longest paths only!
                    visitation_probabilities[v] += float(self.paths[l][p][1])
                    visits += float(self.paths[l][p][1])

        for v in visitation_probabilities:
            visitation_probabilities[v] /= visits
                    

        Log.add('finished.', Severity.INFO)

        return visitation_probabilities