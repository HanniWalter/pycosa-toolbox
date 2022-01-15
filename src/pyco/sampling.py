import z3
import pyco.modeling as modeling
import numpy as np
import pandas as pd
import itertools
import networkx as nx
from abc import ABC, abstractmethod


def int_to_config(i: int, n_options: int) -> np.ndarray:
    without_offset = np.array([int(x) for x in np.binary_repr(i)])
    offset = n_options + 1 - len(without_offset)
    binary = np.append(np.zeros(dtype=int, shape=offset), without_offset)

    return list(reversed(binary))

def mean_overlap_coefficient(S):

    nS = len(S)
    coefs = []
    for x, y in itertools.combinations(range(nS), 2):
        overlap_coefficient = len(set(S[x]) & set(S[y])) / min(len(S[x]), len(S[y]))
        coefs.append(overlap_coefficient)

    return sum(coefs) / len(coefs)



class Sampler(ABC):

    def __init__(self, fm: modeling.CNFExpression, **kwargs):
        self.fm = fm

        seed = kwargs.get('seed', 1)
        np.random.seed(seed)

    @abstractmethod
    def sample(self, **kwargs) -> pd.DataFrame:
        pass
    
    def constrain_enabled(self, options):
        pass
    
    def constrain_disabled(self, options):
        pass
    
    def constrain_min_enabled(self, options):
        pass

    def constrain_max_enabled(self, options):
        pass
    
    def constrain_min_disabled(self, options):
        pass
    
    def constrain_subset_enabled(self, options):
        pass
    
    def constrain_subset_disabled(self, options):
        pass

class RandomSampler(Sampler):
    def __init__(self, fm: modeling.CNFExpression, **kwargs):
        super().__init__(fm, **kwargs)
    
    def promote_diversity(self):
        pass  # stub for executing different techniques

class NaiveRandomSampler(RandomSampler):

    def __init__(self, fm: modeling.CNFExpression, **kwargs):
        super().__init__(fm, **kwargs)

    def sample(self, n: int):

        solutions = []
        for i in range(n):
            self.promote_diversity()

            solver = z3.Solver()
            solver.add(self.fm.bitvec_constraints)
            for solution in solutions:
                solver.add(self.fm.target != solution)

            if solver.check() == z3.sat:
                solution = solver.model()[self.fm.target]
                solutions.append(solution)

            else:
                print('Cannot find more than {} valid configurations'.format(len(solutions)))
                break

        solutions = np.vstack([int_to_config(s.as_long(), len(self.fm.index_map)) for s in solutions])[:, 1:]
        features = [self.fm.index_map[i] for i in self.fm.index_map]
        sample = pd.DataFrame(solutions, columns=features)
        return sample


class DiversityPromotionSampler(NaiveRandomSampler):

    def __init__(self, fm: modeling.CNFExpression, **kwargs):
        super().__init__(fm, **kwargs)

    def promote_diversity(self):
        self.fm.shuffle()

class DistanceBasedSampler(Sampler):

    """
    This class implements uniform random sampling with distance constraints.
    The main idea is that for all configurations, a random number of features
    is selected in order to obtain a representative configuration sample.
    This aims at avoiding bias introduced by the constraint solver.

    Reference:
    C. Kaltenecker, A. Grebhahn, N. Siegmund, J. Guo and S. Apel,
    "Distance-Based Sampling of Software Configuration Spaces,"
    2019 IEEE/ACM 41st International Conference on Software Engineering (ICSE),
    Montreal, QC, Canada, 2019, pp. 1084-1094, doi: 10.1109/ICSE.2019.00112.
    """
    def __init__(self, fm: modeling.CNFExpression, **kwargs):
        super().__init__(fm, **kwargs)

    @staticmethod
    def __hamming(v1, v2, target):
        """
        Auxiliary method that implements the Hamming or Manhattan distance for bit vectors.
        """
        h = v1 ^ v2
        s = max(target.bit_length(), v1.size().bit_length())
        return z3.Sum([z3.ZeroExt(s, z3.Extract(i, i, h)) for i in range(v1.size())])

    def sample(self, size: int):

        n_options = len(self.fm.index_map)

        # add one option since bitvector is longer than n_opt
        origin = z3.BitVecVal("0" * (n_options + 1), n_options)

        clauses = self.fm.bitvec_constraints
        target = self.fm.target

        clauses = z3.And(clauses)

        # for efficiency purposes, we use one solver instance
        # for each possible distance from the origin
        solvers = {i: z3.Solver() for i in range(1, n_options)}
        for index in solvers.keys():
            solvers[index].add(clauses)

            # TODO express distance constraint with the number of enabled features
            solvers[index].add(
                z3.Sum([z3.ZeroExt(n_options + 1, z3.Extract(i, i, target)) for i in range(n_options)]) == index
            )

        # set of existing solutions
        solutions = []

        # unsatisfiable distances
        available_distances = list(range(1, n_options))
        unsatisfiable = False
        sample_sized_reached = False

        while not (unsatisfiable or sample_sized_reached):
            distance = np.random.choice(available_distances)

            if solvers[distance].check() == z3.sat:
                solution = solvers[distance].model()[target]
                solvers[distance].add(target != solution)
                solutions.append(solution)
            else:
                available_distances.remove(distance)

            unsatisfiable = len(available_distances) == 0
            sample_sized_reached = len(solutions) == size

        solutions = np.vstack([int_to_config(s.as_long(), len(self.fm.index_map)) for s in solutions])[:, 1:]
        features = [self.fm.index_map[i] for i in self.fm.index_map]
        sample = pd.DataFrame(solutions, columns=features)
        return sample

class CoverageSampler(Sampler):
    """
    This class implements sampling strategies with regard to main effects, such as
    single features' or interactions' influences. This comprises both feature-wise, t-wise
    and negative-feature-wise / negative-t-wise sampling.
    Brief summary of sampling strategies:
    Feature-wise sampling:
    Activates one feature at a time while minimizing the total
    number of set of activated features. This usually only activates the mandatory features
    plus those implied by the one feature selected. The total number of configurations should be
    equal to the number of optional features.

    T-wise sampling:
    Similarly to feature-wise sampling, this activates a combination of T features
    per configuration test for this interaction's influence. Again, the total number of selected features
    is minimized, such that only implied and mandatory features are selected. The number of configurations cannot
    be greater than 'N over T', where N is the total number of features and T is the target interaction degree.

    Negative feature-wise sampling:
    Similar to feature-wise sampling with the exception that each optional feature
    is de-selected while the the total number of selected features is maximized. Here, we aim at identifying the
    influence caused by the absence of individual features.

    Negative t-wise sampling:
    Similar to t-wise sampling, but the combination of T features is de-selected and the total
    number of features is maximized. Here, we aim at identifying the influence caused by the absence
    of a feature combination.
    """
    def __init__(self, fm: modeling.CNFExpression, **kwargs):
        super().__init__(fm, **kwargs)

    def sample(self, t: int, negwise: bool = False, include_minimal: bool = False):

        optionals = self.fm.find_optional_options()['optional']

        n_options = len(self.fm.index_map)
        target = self.fm.target
        constraints = []
        solutions = []
        for interaction in itertools.combinations(optionals, t):

            # initialize a new optimizer
            optimizer = z3.Optimize()

            # add feature model clauses
            optimizer.add(self.fm.bitvec_constraints)

            # add previous solutions as constraints
            for solution in solutions:
                optimizer.add(solution != target)

            for opt in interaction:
                if not negwise:
                    constraint = z3.Extract(opt, opt, target) == 1
                else:
                    constraint = z3.Extract(opt, opt, target) == 0

                optimizer.add(constraint)

            # function that counts the number of enabled features
            func = z3.Sum(
                [
                    z3.ZeroExt(n_options, z3.Extract(i, i, target))
                    for i in range(n_options)
                ]
            )

            if not negwise:
                optimizer.minimize(func)
            else:
                optimizer.maximize(func)

            if optimizer.check() == z3.sat:
                solution = optimizer.model()[target]
                constraints.append(solution != target)
                solutions.append(solution)

        solutions = np.vstack([int_to_config(s.as_long(), len(self.fm.index_map)) for s in solutions])[:, 1:]
        features = [self.fm.index_map[i] for i in self.fm.index_map]
        sample = pd.DataFrame(solutions, columns=features)
        return sample

class GroupSampler(Sampler):

    def __init__(self, fm: modeling.CNFExpression, **kwargs):
        super().__init__(fm, **kwargs)

    def sample(self, n_groups=2, n_groupings=2):

        partitions, constraints = self.fm.to_partition_constraints(n_groups)
        #print(len(self.fm.index_map))
        '''detect optional features'''
        optionals = self.fm.find_optional_options()['optional']

        mutexes = []
        for group in self.fm.find_alternative_options(optionals):
            mutexes += group

        print(mutexes)
        optionals = list(set(optionals) - set(mutexes))

        n_features = len(self.fm.index_map)
        solver = z3.Optimize()
        solver.add(constraints)

        # distribute mutexes - constraint
        # get partitions of mutexes
        # compute overlap coefficient
        f = z3.Sum([
            z3.Sum([z3.ZeroExt(n_features + 1, z3.Extract(m, m, p)) for p in partitions]) - 1 for m in mutexes
        ])
        solver.minimize(f)

        # difference constraint: each optional feature can only be enabled once in one partition
        for i in optionals:
            c = z3.Sum([z3.ZeroExt(n_features + 1, z3.Extract(i, i, p)) for p in partitions]) == 1
            solver.add(c)

        # non-empty partitions are not allowed
        for p in partitions:
            func = z3.Sum([z3.ZeroExt(n_features + 1, z3.Extract(i, i, p)) for i in optionals]) > 1
            solver.add(func)

        # balance constraint
        func = sum([
            z3.Sum([(n_features // len(partitions) - z3.Sum([z3.ZeroExt(n_features + 1, z3.Extract(i, i, p)) for i in optionals]))]) for p in partitions
        ])
        solver.minimize(func)

        groupings = []
        for iteration in range(n_groupings):
            groups = []

            if solver.check() == z3.sat:
                solution = solver.model()
                for p in partitions:
                    group = solution[p]
                    groups.append((list(int_to_config(group.as_long(), len(self.fm.index_map)))))

                groupings.append(np.vstack(groups))

                # add previous groups to constraints
                for p in partitions:
                    for q in partitions:
                        solver.add(p != solution[q])
            else:
                raise ValueError('Number of groupings insufficient, increase by 1.')

        return groupings

def remove_colinearity(df):

    # courtesy by johannes

    # remove columns with identical values (dead features or mandatory features)
    nunique = df.nunique()
    mandatory_or_dead = nunique[nunique == 1].index.values

    df = df.drop(columns=mandatory_or_dead)

    if 'Unnamed: 0' in df.columns:
        df = df.drop(columns=['Unnamed: 0'])

    df_configs = df
    alternative_ft = []
    alternative_ft_names = []
    group_candidates = {}

    for i, col in enumerate(df_configs.columns):
        filter_on = df_configs[col] == 1
        filter_off = df_configs[col] == 0
        group_candidates[col] = []
        for other_col in df_configs.columns:
            if other_col != col:
                values_if_col_on = df_configs[filter_on][other_col].unique()
                if len(values_if_col_on) == 1 and values_if_col_on[0] == 0:
                    # other feature is always off if col feature is on
                    group_candidates[col].append(other_col)

    G = nx.Graph()
    for ft, alternative_candidates in group_candidates.items():
        for candidate in alternative_candidates:
            if ft in group_candidates[candidate]:
                G.add_edge(ft, candidate)

    cliques_remaining = True
    while cliques_remaining:
        cliques_remaining = False
        cliques = nx.find_cliques(G)
        for clique in cliques:
            # check if exactly one col is 1 in each row
            sums_per_row = df_configs[clique].sum(axis=1).unique()
            if len(sums_per_row) == 1 and sums_per_row[0] == 1.0:
                delete_ft = sorted(clique)[0]
                alternative_ft_names.append(delete_ft)
                df_configs.drop(delete_ft, inplace=True, axis=1)
                for c in clique:
                    G.remove_node(c)
                cliques_remaining = True
                break

    return df
