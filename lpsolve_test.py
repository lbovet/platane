from lpsolve55 import *

lp = lpsolve('make_lp', 0, 8)
#lpsolve('set_verbose', lp, IMPORTANT)
lpsolve('set_obj_fn', lp, [-1.0, -1.0, -1.0, -1.0, -1.0, -1.0, -1.0, -1.0])
lpsolve('add_constraint', lp, [1.0, 1.0, 1.0, 0, 0, 0, 0, 0], LE, 8.0)
lpsolve('add_constraint', lp, [0, 0, 0, 1.0, 1.0, 0, 0, 0], LE, 4.0)
lpsolve('add_constraint', lp, [0, 0, 0, 0, 0, 1.0, 0, 0], LE, 8.0)
lpsolve('add_constraint', lp, [0, 0, 0, 0, 0, 0, 1.0, 1.0], LE, 12.0)
lpsolve('add_constraint', lp, [1.0, 0, 0, 1.0, 0, 0, 0, 0], LE, 10.0)
lpsolve('add_constraint', lp, [0, 1.0, 0, 0, 1.0, 1.0, 1.0, 0], LE, 10.0)
lpsolve('add_constraint', lp, [0, 0, 1.0, 0, 0, 0, 0, 1.0], LE, 10.0)
lpsolve('set_lowbo', lp, [0, 0.0, 0, 0, 0, 0, 0, 0])
lpsolve('set_upbo', lp, [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0])
lpsolve('solve', lp)
print lpsolve('get_variables', lp)[0]
lpsolve('delete_lp', lp)