import os
import sys
import torch
import gpytorch
import argparse
import numpy as np
import pandas as pd
import seaborn as sns
from math import sqrt
import pickle5 as pickle
from itertools import product
import matplotlib.pyplot as plt

from variational_GP import GPmodel, train_GP 
from data_utils import build_bernoulli_dataframe, build_binomial_dataframe
from bernoulli_likelihood import BernoulliLikelihood

parser = argparse.ArgumentParser()
parser.add_argument("--variational_distribution", default='cholesky', type=str, help="Variational distribution")
parser.add_argument("--variational_strategy", default='unwhitened', type=str, help="Variational strategy")
parser.add_argument("--train", default=True, type=eval, help="If True train the model else load it")
parser.add_argument("--n_epochs", default=1000, type=int, help="Number of training iterations")
parser.add_argument("--lr", default=0.01, type=float, help="Learning rate")
parser.add_argument("--n_test_points", default=100, type=int, help="Number of test params")
parser.add_argument("--n_posterior_samples", default=1000, type=int, help="Number of samples from posterior distribution")
args = parser.parse_args()


for train_filename, val_filename in [
    ["SIR_DS_200samples_10obs_Beta", "SIR_DS_20samples_5000obs_Beta"],
    # ["SIR_DS_200samples_10obs_Gamma", "SIR_DS_20samples_5000obs_Gamma"],
    ["SIR_DS_256samples_5000obs_BetaGamma", "SIR_DS_256samples_10obs_BetaGamma"]
    ]:

    print(f"\n=== Training {train_filename} ===")

    out_filename = f"bernoulli_{train_filename}_epochs={args.n_epochs}_lr={args.lr}"

    with open(f"../Data/SIR/{train_filename}.pickle", 'rb') as handle:
        data = pickle.load(handle)
    x_train, y_train, n_params = build_bernoulli_dataframe(data)

    x_train_bin, y_train_bin, _, n_trials_train = build_binomial_dataframe(data)

    inducing_points = torch.tensor(data['params'], dtype=torch.float32)

    model = GPmodel(inducing_points=inducing_points, variational_distribution=args.variational_distribution,
        variational_strategy=args.variational_strategy)
    # likelihood = gpytorch.likelihoods.BernoulliLikelihood()
    likelihood = BernoulliLikelihood()

    if args.train:

        model = train_GP(model=model, likelihood=likelihood, x_train=x_train, y_train=y_train, n_epochs=args.n_epochs, 
            lr=args.lr)
        os.makedirs(os.path.dirname("models/"), exist_ok=True)
        torch.save(model.state_dict(), "models/gp_state_"+out_filename+".pth")

    print(f"\n=== Validation {val_filename} ===")

    with open(f"../Data/SIR/{val_filename}.pickle", 'rb') as handle:
        data = pickle.load(handle)
    x_val, y_val, n_params, n_trials_val = build_binomial_dataframe(data)

    model.eval()    
    likelihood.eval()

    state_dict = torch.load("models/gp_state_"+out_filename+".pth")
    model.load_state_dict(state_dict)


    with torch.no_grad():

        x_test = []
        for col_idx in range(n_params):
            single_param_values = x_val[:,col_idx]
            x_test.append(torch.linspace(single_param_values.min(), single_param_values.max(), args.n_test_points))
        x_test = torch.stack(x_test, dim=1)

        if n_params==2:
            x_test = torch.tensor(list(product(x_test[:,0], x_test[:,1])))

        posterior_bernoulli = likelihood(model(x_test)) 
        # pred_samples = posterior_bernoulli.sample(sample_shape=torch.Size((args.n_posterior_samples,)))

        # print("\npred_samples.shape =", pred_samples.shape, "= (n. bernoulli samples, n. test params)")

    # z = 1.96
    # pred_mean = pred_samples.mean(0)
    # pred_std = pred_samples.std(0)
    # lower_ci = pred_mean-z*pred_std/sqrt(n_bernoulli_samples)
    # upper_ci = pred_mean+z*pred_std/sqrt(n_bernoulli_samples)
 
    path='plots/SIR/'
    os.makedirs(os.path.dirname(path), exist_ok=True)


    if n_params==1:

        fig, ax = plt.subplots(1, 1, figsize=(6*n_params, 5))

        sns.scatterplot(x=x_val, y=y_val/n_trials_val, ax=ax, label='validation pts')
        sns.scatterplot(x=x_train_bin, y=y_train_bin/n_trials_train, ax=ax, 
            label='training points', marker='.', color='black')

        sns.lineplot(x=x_test, y=posterior_bernoulli.mean, ax=ax, label='posterior')
        ax.fill_between(x_test, posterior_bernoulli.mean-posterior_bernoulli.variance, 
            posterior_bernoulli.mean+posterior_bernoulli.variance, alpha=0.5)

    else:
        torch.set_printoptions(precision=2)
        fig, ax = plt.subplots(1, 2, figsize=(6*n_params, 5))

        data = pd.DataFrame({'beta':x_val[:,0],'gamma':x_val[:,1],'val_counts':y_val.flatten()/n_trials_val})
        data["beta"] = data["beta"].apply(lambda x: format(float(x),".2f"))
        data["gamma"] = data["gamma"].apply(lambda x: format(float(x),".2f"))
        data = data.pivot("beta", "gamma", "val_counts")
        sns.heatmap(data, ax=ax[0], label='validation pts')

        data = pd.DataFrame({'beta':x_test[:,0],'gamma':x_test[:,1],'posterior_mean':posterior_bernoulli.mean})
        data["beta"] = data["beta"].apply(lambda x: format(float(x),".2f"))
        data["gamma"] = data["gamma"].apply(lambda x: format(float(x),".2f"))
        data = data.pivot("beta", "gamma", "posterior_mean")
        sns.heatmap(data, ax=ax[1], label='posterior mean')

    fig.savefig(path+f"bernoulli_"+out_filename+".png")
    plt.close()


