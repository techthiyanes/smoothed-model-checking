import os
import sys
import GPy
import torch
import random
import argparse
import numpy as np
from math import sqrt
import pickle5 as pickle

sys.path.append(".")
from paths import *
from baselineGPs.utils import train_GP, evaluate_GP
from baselineGPs.binomial_likelihood import Binomial
from data_utils import get_bernoulli_data, get_binomial_data, normalize_columns, get_tensor_data

random.seed(0)
np.random.seed(0)


parser = argparse.ArgumentParser()
parser.add_argument("--likelihood", default='binomial', type=str, help='')
parser.add_argument("--inference", default='laplace', type=str, help='Choose laplace or expectation_propagation')
parser.add_argument("--load", default=False, type=eval, help="If True load the model else train it")
parser.add_argument("--n_posterior_samples", default=30, type=int, help="Number of samples from posterior distribution")
parser.add_argument("--variance", default=.5, type=int, help="")
parser.add_argument("--lengthscale", default=.5, type=int, help="")
args = parser.parse_args()


models_path = os.path.join("baselineGPs", models_path)
os.makedirs(os.path.dirname(models_path), exist_ok=True)

for filepath, train_filename, val_filename, params_list, math_params_list in data_paths:

    print(f"\n=== Training {train_filename} ===")

    with open(os.path.join(data_path, filepath, train_filename+".pickle"), 'rb') as handle:
        data = pickle.load(handle)

    if args.likelihood=='binomial':
        x_train, y_train, n_samples, n_trials_train = get_binomial_data(data)
        likelihood = Binomial()
        x_train = normalize_columns(x_train).numpy()
        y_train = y_train.unsqueeze(1).numpy()

    else:
        raise NotImplementedError

    # import pods
    # data = pods.datasets.toy_linear_1d_classification(seed=0)
    # Y = data["Y"][:, 0:1]
    # Y[Y.flatten() == -1] = 0
    # print(data["X"], Y)
    # print(data["X"].shape, Y.shape)
    # exit()

    out_filename = f"{train_filename}"
    Y_metadata = {'trials':np.full(y_train.shape, n_trials_train)}

    
    kernel = GPy.kern.RBF(input_dim=1, variance=args.variance, lengthscale=args.lengthscale)


    if args.inference=='laplace':
        inference = GPy.inference.latent_function_inference.Laplace()
        model = GPy.core.GP(X=x_train, Y=y_train, kernel=kernel, inference_method=inference, likelihood=likelihood, 
            Y_metadata=Y_metadata)

    elif args.inference=='expectation_propagation':
        ep = GPy.inference.latent_function_inference.expectation_propagation.EP()
        model = GPy.core.GP(X=x_train, Y=y_train, kernel=kernel, likelihood=likelihood, inference_method=ep,
            name="gp_classification")

    else:
        raise NotImplementedError



    if args.load:
        with open(os.path.join(models_path, "gp_"+out_filename+".pkl"), 'rb') as file:
            model = pickle.load(file)

        file = open(os.path.join(models_path,f"gp_{out_filename}_training_time.txt"),"r+")
        print(f"\nTraining time = {file.read()}")

    else:

        model, training_time = train_GP(model=model, x_train=x_train, y_train=y_train)

        with open(os.path.join(models_path, "gp_"+out_filename+".pkl"), 'wb') as file:
            pickle.dump(model, file)

        file = open(os.path.join(models_path,f"gp_{out_filename}_training_time.txt"),"w")
        file.writelines(training_time)
        file.close()

    print(f"\n=== Validation {val_filename} ===")

    if filepath=='Poisson':

        raise NotImplementedError
        # x_test, post_samples, post_mean, post_std, evaluation_dict = evaluate_GP(model=model, x_val=None, y_val=None, 
        #     n_trials_val=None, n_posterior_samples=args.n_posterior_samples, n_params=n_params)

    else:
        with open(os.path.join(data_path, filepath, val_filename+".pickle"), 'rb') as handle:
            val_data = pickle.load(handle)
        
        post_mean, q1, q2, evaluation_dict = evaluate_GP(model=model, val_data=val_data,
            n_samples=n_samples, n_posterior_samples=args.n_posterior_samples)
