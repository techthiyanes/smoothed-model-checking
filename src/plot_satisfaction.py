import os
import sys
import pyro
import torch
import random
import argparse
import matplotlib
import numpy as np
import pandas as pd
import seaborn as sns
import pickle5 as pickle
import matplotlib.pyplot as plt

from paths import *
from SVI_BNNs.bnn import BNN_smMC
from EP_GPs.smMC_GPEP import smMC_GPEP
from SVI_GPs.variational_GP import GPmodel
from posterior_plot_utils import plot_posterior_ax, plot_validation_ax
from data_utils import get_tensor_data, normalize_columns

parser = argparse.ArgumentParser()
parser.add_argument("--ep_gp_n_epochs", default=3000, type=int, help="Max number of training iterations")
parser.add_argument("--svi_gp_likelihood", default='binomial', type=str, help='Choose bernoulli or binomial')
parser.add_argument("--svi_gp_variational_distribution", default='cholesky', type=str, help="Variational distribution")
parser.add_argument("--svi_gp_variational_strategy", default='default', type=str, help="Variational strategy")
parser.add_argument("--svi_gp_batch_size", default=100, type=int, help="Batch size")
parser.add_argument("--svi_gp_n_epochs", default=1000, type=int, help="Number of training iterations")
parser.add_argument("--svi_gp_lr", default=0.01, type=float, help="Learning rate")
parser.add_argument("--svi_bnn_likelihood", default='binomial', type=str, help="Choose 'bernoulli' or 'binomial'")
parser.add_argument("--svi_bnn_architecture", default='3L', type=str, help="NN architecture")
parser.add_argument("--svi_bnn_batch_size", default=100, type=int, help="Batch size")
parser.add_argument("--svi_bnn_n_epochs", default=10000, type=int, help="Number of training iterations")
parser.add_argument("--svi_bnn_lr", default=0.001, type=float, help="Learning rate")
parser.add_argument("--svi_bnn_n_hidden", default=30, type=int, help="Size of hidden layers")
parser.add_argument("--n_posterior_samples", default=1000, type=int, help="Number of samples from posterior distribution")
parser.add_argument("--plot_training_points", default=False, type=bool, help="")
parser.add_argument("--train_device", default="cpu", type=str, help="Choose 'cpu' or 'cuda'")
parser.add_argument("--eval_device", default="cpu", type=str, help="Choose 'cpu' or 'cuda'")
args = parser.parse_args()
print(args)

palette = sns.color_palette("magma_r", 3)
sns.set_style("darkgrid")
sns.set_palette(palette)
matplotlib.rc('font', **{'size':9, 'weight' : 'bold'})

out_txt = os.path.join(plots_path, "evaluation_out.txt")
try:
    os.remove(out_txt)
except OSError:
    file = open(out_txt,"w")
    file.writelines(args.__dict__)

for filepath, train_filename, val_filename, params_list, math_params_list in case_studies:

    with open(out_txt, "a") as file:
        file.write(f"\n\nValidation set: {val_filename}\n")

    print(f"\n=== Eval on {val_filename} ===")

    random.seed(0)
    np.random.seed(0)
    torch.manual_seed(0)

    ### Load data

    with open(os.path.join(data_path, filepath, train_filename+".pickle"), 'rb') as handle:
        train_data = pickle.load(handle)

    with open(os.path.join(data_path, filepath, val_filename+".pickle"), 'rb') as handle:
        val_data = pickle.load(handle)

    ### Validation uncertainty

    x_val, y_val_bernoulli = val_data['params'], val_data['labels']
    p = y_val_bernoulli.mean(1).flatten()
    sample_variance = [((param_y-param_y.mean())**2).mean() for param_y in y_val_bernoulli]
    std = np.sqrt(sample_variance).flatten()
    n_trials_val = get_tensor_data(val_data)[3]
    errors = (1.96*std)/np.sqrt(n_trials_val)

    with open(out_txt, "a") as file:
        file.write(f"\nValidation avg_unc={np.mean(2*errors)}")

    ### Set plots

    n_params = len(params_list)

    if n_params==1:
        fig, ax = plt.subplots(1, 3, figsize=(9, 3), dpi=150, sharex=True, sharey=True)

    elif n_params==2:
        fig, ax = plt.subplots(1, 4, figsize=(11, 3), dpi=150, sharex=True, sharey=True)

    ### Eval models on validation set
    
    print(f"\nEP GP model:")

    if n_params>5:
        print("\nEP is unfeasible on this dataset.")

    else:

        out_filename = f"ep_gp_{train_filename}_epochs={args.ep_gp_n_epochs}"
        smc = smMC_GPEP()
        training_time = smc.load(filepath=os.path.join(models_path, "EP_GPs/"), filename=out_filename)

        x_train, y_train, n_samples_train, n_trials_train = smc.transform_data(train_data)
        x_val, y_val, n_samples_val, n_trials_val = smc.transform_data(val_data)
        post_mean, q1, q2, evaluation_dict = smc.eval_gp(x_train=x_train, x_val=x_val, y_val=val_data['labels'], 
            n_samples=n_samples_val, n_trials=n_trials_val)

        with open(out_txt, "a") as file:
            file.write(f"\nEP GP\ttraining_time={training_time}\tmse={evaluation_dict['mse']}\tval_acc={evaluation_dict['val_accuracy']} avg_unc={evaluation_dict['avg_uncertainty_area']}")
    
    if n_params<=2:

        ax = plot_posterior_ax(ax=ax, ax_idxs=[0,1], params_list=params_list, math_params_list=math_params_list,  
            train_data=train_data, test_data=val_data, post_mean=post_mean, q1=q1, q2=q2, title='EP GP', legend=None,
            palette=palette)

    print(f"\nSVI GP model:")

    out_filename = f"svi_gp_{train_filename}_epochs={args.svi_gp_n_epochs}_lr={args.svi_gp_lr}_batch={args.svi_gp_batch_size}_{args.svi_gp_variational_distribution}_{args.svi_gp_variational_strategy}"

    inducing_points = normalize_columns(get_tensor_data(train_data)[0])
    model = GPmodel(inducing_points=inducing_points, variational_distribution=args.svi_gp_variational_distribution,
        variational_strategy=args.svi_gp_variational_strategy, likelihood=args.svi_gp_likelihood)
    training_time = model.load(filepath=os.path.join(models_path, "SVI_GPs/"), filename=out_filename, 
        training_device=args.train_device)
        
    post_mean, q1, q2, evaluation_dict = model.evaluate(train_data=train_data, val_data=val_data, 
        n_posterior_samples=args.n_posterior_samples, device=args.eval_device)

    with open(out_txt, "a") as file:
        file.write(f"\nSVI GP\ttraining_time={training_time}\tmse={evaluation_dict['mse']}\tval_acc={evaluation_dict['val_accuracy']} avg_unc={evaluation_dict['avg_uncertainty_area']}")

    if n_params<=2:

        ax = plot_posterior_ax(ax=ax, ax_idxs=[1,2], params_list=params_list, math_params_list=math_params_list,  
            train_data=train_data, test_data=val_data, post_mean=post_mean, q1=q1, q2=q2, title='SVI GP', legend=None,
            palette=palette)

    print(f"\nSVI BNN model:")

    pyro.clear_param_store()

    out_filename = f"svi_bnn_{train_filename}_epochs={args.svi_bnn_n_epochs}_lr={args.svi_bnn_lr}_batch={args.svi_bnn_batch_size}_hidden={args.svi_bnn_n_hidden}_{args.svi_bnn_architecture}"
    
    bnn_smmc = BNN_smMC(model_name=filepath, list_param_names=params_list, likelihood=args.svi_bnn_likelihood,
        input_size=len(params_list), n_hidden=args.svi_bnn_n_hidden, architecture_name=args.svi_bnn_architecture)
    training_time = bnn_smmc.load(filepath=os.path.join(models_path, "SVI_BNNs/"), filename=out_filename, 
        training_device=args.train_device)

    post_mean, q1, q2, evaluation_dict = bnn_smmc.evaluate(train_data=train_data, val_data=val_data,
        n_posterior_samples=args.n_posterior_samples, device=args.eval_device)

    with open(out_txt, "a") as file:
        file.write(f"\nSVI BNN\ttraining_time={training_time}\tmse={evaluation_dict['mse']}\tval_acc={evaluation_dict['val_accuracy']} avg_unc={evaluation_dict['avg_uncertainty_area']}")

    if n_params<=2:

        ax = plot_posterior_ax(ax=ax, ax_idxs=[2,3], params_list=params_list, math_params_list=math_params_list,  
            train_data=train_data, test_data=val_data, post_mean=post_mean, q1=q1, q2=q2, title='SVI BNN', legend='auto',
            palette=palette)

        ### plot validation

        ax = plot_validation_ax(ax=ax, params_list=params_list, math_params_list=math_params_list, 
            test_data=val_data, val_data=val_data, z=1.96, palette=palette)

        ### save plot

        plt.tight_layout()
        plt.close()
        os.makedirs(os.path.join(plots_path), exist_ok=True)

        plot_filename = train_filename if val_filename is None else val_filename
        fig.savefig(os.path.join(plots_path, f"{plot_filename}.png"))