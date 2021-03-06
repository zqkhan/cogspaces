import os
import sys
from copy import copy
from os import path
from os.path import join

import numpy as np
from cogspaces.pipeline import get_output_dir
from sacred import Experiment
from sacred.observers import FileStorageObserver
from sklearn.externals.joblib import Parallel
from sklearn.externals.joblib import delayed
from sklearn.utils import check_random_state

print(path.dirname(path.dirname(path.abspath(__file__))))
# Add examples to known modules
sys.path.append(
    path.dirname(path.dirname(path.dirname(path.abspath(__file__)))))
from exps.single import exp as single_exp

exp = Experiment('benchmark_trainsize')
basedir = join(get_output_dir(), 'benchmark_trainsize')
if not os.path.exists(basedir):
    os.makedirs(basedir)
exp.observers.append(FileStorageObserver.create(basedir=basedir))


@exp.config
def config():
    n_jobs = 20
    n_seeds = 20
    seed = 1000


@single_exp.config
def config():
    datasets = ['archi', 'hcp']
    reduced_dir = join(get_output_dir(), 'reduced')
    unmask_dir = join(get_output_dir(), 'unmasked')
    source = 'hcp_new_big'
    test_size = {'hcp': .1, 'archi': .5, 'brainomics': .5, 'camcan': .5,
                 'la5c': .5, 'full': .5}
    train_size = dict(hcp=None, archi=30, la5c=50, brainomics=30,
                      camcan=80,
                      human_voice=None)
    dataset_weights = {'brainomics': 1, 'archi': 1, 'hcp': 1}
    max_iter = 500
    verbose = 10
    seed = 20

    with_std = True
    with_mean = True
    per_dataset = True

    # Factored only
    n_components = 100

    batch_size = 128
    optimizer = 'adam'
    step_size = 1e-3

    alphas = np.logspace(-6, -1, 6)
    latent_dropout_rates = [0.75]
    input_dropout_rates = [0.25]
    dataset_weights_helpers = [[1]]

    n_splits = 10
    n_jobs = 1


def single_run(config_updates, rundir, _id):
    run = single_exp._create_run(config_updates=config_updates)
    observer = FileStorageObserver.create(basedir=rundir)
    run._id = _id
    run.observers = [observer]
    run()


@exp.automain
def run(n_seeds, n_jobs, _run, _seed):
    seed_list = check_random_state(_seed).randint(np.iinfo(np.uint32).max,
                                                  size=n_seeds)
    exps = []
    transfer_train_size = dict(hcp=None, archi=None, la5c=None,
                               brainomics=None,
                               camcan=None,
                               human_voice=None)
    transfer_datasets = ['archi', 'brainomics', 'camcan', 'hcp']

    for dataset in ['archi', 'brainomics', 'camcan']:
        for target_train_size in [5, 10, 20, .1, .2, .3, .4, .5]:
                this_train_size = copy(transfer_train_size)
                this_train_size[dataset] = target_train_size
                # Latent space model
                no_transfer = [{'datasets': [dataset],
                                'model': 'factored',
                                'train_size': this_train_size,
                                'seed': seed} for seed in seed_list
                               ]
                transfer = [{'datasets': [dataset, 'hcp'],
                             'model': 'factored',
                             'train_size': this_train_size,
                             'seed': seed} for seed in seed_list
                            ]
                these_transfer_datasets = copy(transfer_datasets)
                if dataset in these_transfer_datasets:
                    these_transfer_datasets.remove(dataset)
                datasets = [dataset] + these_transfer_datasets
                large_transfer = [{'datasets': datasets,
                                   'dataset_weights_helpers': [
                                       [1] * len(these_transfer_datasets)],
                                   'train_size': this_train_size,
                                   'model': 'factored',
                                   'seed': seed} for seed in seed_list
                                  ]
                exps += no_transfer
                exps += transfer
                exps += large_transfer

    np.random.shuffle(exps)

    rundir = join(basedir, str(_run._id), 'run')
    if not os.path.exists(rundir):
        os.makedirs(rundir)

    Parallel(n_jobs=n_jobs, verbose=10)(delayed(single_run)(config_updates, rundir, i)
                         for i, config_updates in enumerate(exps))
