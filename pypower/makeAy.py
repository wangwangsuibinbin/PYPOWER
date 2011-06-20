# Copyright (C) 1996-2011 Power System Engineering Research Center
# Copyright (C) 2010-2011 Richard Lincoln
#
# PYPOWER is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation, either version 3 of the License,
# or (at your option) any later version.
#
# PYPOWER is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with PYPOWER. If not, see <http://www.gnu.org/licenses/>.

from numpy import array, diff, any, zeros, r_, flatnonzero as find
#from scipy.sparse import csr_matrix as sparse
from scipy.sparse import lil_matrix as sparse

from idx_cost import MODEL, PW_LINEAR, NCOST, COST


def makeAy(baseMVA, ng, gencost, pgbas, qgbas, ybas):
    """Make the A matrix and RHS for the CCV formulation.

    Constructs the parameters for linear "basin constraints" on Pg, Qg
    and Y used by the CCV cost formulation, expressed as

         AY * X <= BY

    where X is the vector of optimization variables. The starting index
    within the X vector for the active, reactive sources and the Y
    variables should be provided in arguments PGBAS, QGBAS, YBAS. The
    number of generators is NG.

    Assumptions: All generators are in-service.  Filter any generators
    that are offline from the GENCOST matrix before calling MAKEAY.
    Efficiency depends on Qg variables being after Pg variables, and
    the Y variables must be the last variables within the vector X for
    the dimensions of the resulting AY to be conformable with X.

    @see: U{http://www.pserc.cornell.edu/matpower/}
    """
    ## find all pwl cost rows in gencost, either real or reactive
    iycost = find(gencost[:, MODEL] == PW_LINEAR)

    ## this is the number of extra "y" variables needed to model those costs
    ny = iycost.shape[0]

    if ny == 0:
        Ay = zeros((0, ybas+ny-1))
        by = array([])
        return Ay, by

    ## if p(i),p(i+1),c(i),c(i+1) define one of the cost segments, then
    ## the corresponding constraint on Pg (or Qg) and Y is
    ##                                             c(i+1) - c(i)
    ##  Y   >=   c(i) + m * (Pg - p(i)),      m = ---------------
    ##                                             p(i+1) - p(i)
    ##
    ## this becomes   m * Pg - Y   <=   m*p(i) - c(i)

    ## Form A matrix.  Use two different loops, one for the PG/Qg coefs,
    ## then another for the y coefs so that everything is filled in the
    ## same order as the compressed column sparse format used by matlab
    ## this should be the quickest.

    m = sum( gencost[iycost, NCOST].astype(int) )  ## total number of cost points
    Ay = sparse((m - ny, ybas + ny - 1))
    by = array([])
    ## First fill the Pg or Qg coefficients (since their columns come first)
    ## and the rhs
    k = 0
    for i in iycost:
        ns = gencost[i, NCOST].astype(int)         ## # of cost points segments = ns-1
        p = gencost[i, COST:COST + 2 * ns - 1:2] / baseMVA
        c = gencost[i, COST + 1:COST + 2 * ns:2]
        m = diff(c) / diff(p)               ## slopes for Pg (or Qg)
        if any(diff(p) == 0):
            print 'makeAy: bad x axis data in row ##i of gencost matrix' % i
        b = m * p[:ns - 1] - c[:ns - 1]        ## and rhs
        by = r_[by,  b]
        if i > ng:
            sidx = qgbas + (i - ng) - 1        ## this was for a q cost
        else:
            sidx = pgbas + i - 1               ## this was for a p cost

        ## FIXME: Bug in SciPy 0.7.2 prevents setting with a sequence
#        Ay[k:k + ns - 1, sidx] = m
        for ii, kk in enumerate(range(k, k + ns - 1)):
            Ay[kk, sidx] = m[ii]

        k = k + ns - 1
    ## Now fill the y columns with -1's
    k = 0
    j = 0
    for i in iycost:
        ns = gencost[i, NCOST].astype(int)
        ## FIXME: Bug in SciPy 0.7.2 prevents setting with a sequence
#        Ay[k:k + ns - 1, ybas + j - 1] = -ones(ns - 1)
        for kk in range(k, k + ns - 1):
            Ay[kk, ybas + j - 1] = -1
        k = k + ns - 1
        j = j + 1

    return Ay, by
