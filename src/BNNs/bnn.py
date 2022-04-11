import os
import sys
import time
import pyro
import torch
import random
import scipy.io
import matplotlib
import numpy as np
from math import pi
import torch.nn as nn
from pyro import poutine
import pickle5 as pickle
import torch.optim as optim
from pyro.nn import PyroModule
import matplotlib.pyplot as plt
import torch.nn.functional as F
from pyro.optim import Adam, SGD
from sklearn import preprocessing
from itertools import combinations
from torch.autograd import Variable
from paths import models_path, plots_path
from pyro.distributions import Normal, Binomial
from pyro.infer import SVI, Trace_ELBO, TraceMeanField_ELBO

sys.path.append(".")
from BNNs.dnn import DeterministicNetwork
from data_utils import Poisson_observations
from evaluation_metrics import execution_time, evaluate_posterior_samples

softplus = torch.nn.Softplus()


class BNN_smMC(PyroModule):

    def __init__(self, model_name, list_param_names, train_set, val_set, input_size, architecture_name='3L', 
        n_hidden=10, n_test_points=20):
        # initialize PyroModule
        super(BNN_smMC, self).__init__()
        
        # BayesianNetwork extends PyroModule class
        self.det_network = DeterministicNetwork(input_size=input_size, hidden_size=n_hidden, architecture_name=architecture_name)
        self.name = "bayesian_network"

        self.train_set_fn = train_set
        self.val_set_fn = val_set
        self.input_size = input_size
        self.n_hidden = n_hidden
        self.output_size = 1
        self.n_test_points = n_test_points
        self.model_name = model_name
        self.param_name = list_param_names
        self.mre_eps = 0.000001
        self.casestudy_id = self.model_name+''.join(self.param_name)

    def load_train_data(self):
        with open(self.train_set_fn, 'rb') as handle:
            datasets_dict = pickle.load(handle)

        self.X_train = datasets_dict["params"]
        
        P_train = datasets_dict["labels"]
        n_train_points, M_train = P_train.shape

        self.M_train = M_train
        self.n_training_points = n_train_points
        self.T_train = np.sum(P_train,axis=1)
        xmax = np.max(self.X_train, axis = 0)
        xmin = np.min(self.X_train, axis = 0)
        self.MAX = xmax
        self.MIN = xmin

        self.X_train_scaled = -1+2*(self.X_train-self.MIN)/(self.MAX-self.MIN)
        self.T_train_scaled = np.expand_dims(self.T_train, axis=1)

    def load_val_data(self):
        with open(self.val_set_fn, 'rb') as handle:
            datasets_dict = pickle.load(handle)

        self.X_val = datasets_dict["params"]
        
        P_val = datasets_dict["labels"]
        n_val_points, M_val = P_val.shape

        self.M_val = M_val
        self.n_val_points = n_val_points
        self.T_val = np.sum(P_val,axis=1)
        
        self.X_val_scaled = -1+2*(self.X_val-self.MIN)/(self.MAX-self.MIN)
        
        self.T_val_scaled = self.T_val

    def model(self, x_data, y_data):

        priors = {}
    
        # set Gaussian priors on the weights of self.det_network
        for key, value in self.det_network.state_dict().items():
            loc = torch.zeros_like(value)
            scale = torch.ones_like(value)#/value.size(dim=0)
            prior = Normal(loc=loc, scale=scale)
            priors.update({str(key):prior})

        # pyro.random_module places `priors` over the parameters of the nn.Module 
        # self.det_network and returns a distribution, which upon calling 
        # samples a new nn.Module (`lifted_module`)
        lifted_module = pyro.random_module("module", self.det_network, priors)()
    
        # samples are conditionally independent w.r.t. the observed data
        lhat = lifted_module(x_data) # out.shape = (batch_size, num_classes)
        
        pyro.sample("obs", Binomial(total_count=self.M_train, probs=lhat), obs=y_data)

    def guide(self, x_data, y_data=None):

        dists = {}
        for key, value in self.det_network.state_dict().items():

            # torch.randn_like(x) builds a random tensor whose shape equals x.shape
            loc = pyro.param(str(f"{key}_loc"), torch.randn_like(value)) 
            scale = pyro.param(str(f"{key}_scale"), torch.randn_like(value))

            # softplus is a smooth approximation to the ReLU function
            # which constraints the scale tensor to positive values
            distr = Normal(loc=loc, scale=softplus(scale))

            # add key-value pair to the samples dictionary
            dists.update({str(key):distr})
        # define a random module from the dictionary of distributions
        lifted_module = pyro.random_module("module", self.det_network, dists)()

        # compute predictions on `x_data`
        lhat = lifted_module(x_data)
        return lhat

    
    def forward(self, inputs, n_samples=10):
        """ Compute predictions on `inputs`. 
        `n_samples` is the number of samples from the posterior distribution.
        If `avg_prediction` is True, it returns the average prediction on 
        `inputs`, otherwise it returns all predictions 
        """

        preds = []
        # take multiple samples
        for _ in range(n_samples):         
            guide_trace = poutine.trace(self.guide).get_trace(inputs)
            preds.append(guide_trace.nodes['_RETURN']['value'])
        
        t_hats = torch.stack(preds).squeeze()
        t_mean = torch.mean(t_hats, 0)
        t_std = torch.std(t_hats, 0)
        
        return t_hats, t_mean, t_std
    
    def set_training_options(self, n_epochs = 1000, lr = 0.01):

        self.n_epochs = n_epochs
        self.lr = lr        

    def train(self):
        random.seed(0)
        np.random.seed(0)
        torch.manual_seed(0)

        #adam_params = {"lr": self.lr, "betas": (0.95, 0.999)}
        adam_params = {"lr": self.lr}
        optim = Adam(adam_params)
        elbo = TraceMeanField_ELBO()
        svi = SVI(self.model, self.guide, optim, loss=elbo)

        batch_T_t = torch.FloatTensor(self.T_train_scaled)
        batch_X_t = torch.FloatTensor(self.X_train_scaled)

        start = time.time()

        loss_history = []
        for j in range(self.n_epochs):
            loss = svi.step(batch_X_t, batch_T_t)/ self.n_training_points
            if (j+1)%50==0:
                print("Epoch ", j+1, "/", self.n_epochs, " Loss ", loss)
                loss_history.append(loss)

        self.loss_history = loss_history

        if self.n_epochs >= 50:
            fig = plt.figure()
            plt.plot(np.arange(0,self.n_epochs,50), np.array(self.loss_history))
            plt.title("loss")
            plt.xlabel("epochs")
            plt.tight_layout()
            plt.savefig(self.plot_path+"loss.png")
            plt.close()

        training_time = execution_time(start=start, end=time.time())
        print("\nTraining time: ", training_time)
        return training_time

    def evaluate(self, y_val, n_posterior_samples, poisson=False):
        # Does not work for Poisson case 

        random.seed(0)
        np.random.seed(0)
        torch.manual_seed(0)    

        start = time.time()

        with torch.no_grad():

            if self.model_name == 'Poisson':

                raise NotImplementedError

                # x_val_t, y_val = Poisson_observations(n_posterior_samples)
                # y_val = y_val.flatten()

            else:
                x_val_t = torch.FloatTensor(self.X_val_scaled)
                # y_val = torch.tensor(self.T_val_scaled.flatten())
                y_val = torch.tensor(y_val)

            x_test_t = []
            x_test_unscaled_t = []
            for col_idx in range(self.input_size):
                single_param_values = self.X_val_scaled[:,col_idx]
                single_param_values_unscaled = self.X_val[:,col_idx]
                x_test_t.append(torch.linspace(single_param_values.min(), single_param_values.max(), self.n_test_points))
                x_test_unscaled_t.append(torch.linspace(single_param_values_unscaled.min(), single_param_values_unscaled.max(), self.n_test_points))
            x_test_t = torch.stack(x_test_t, dim=1)

            if self.input_size>1:
                x_test_cart_t = torch.cartesian_prod(*[x_test_t[:,i] for i in range(x_test_t.shape[1])])

            x_test = x_test_t.numpy()
            x_test_unscaled = torch.stack(x_test_unscaled_t, dim=1).numpy()
            
            if self.input_size == 1:
                T_test_bnn, test_mean_pred, test_std_pred = self.forward(x_test_t)
            else: 
                T_test_bnn, test_mean_pred, test_std_pred = self.forward(x_test_cart_t)

            T_val_bnn, val_mean_pred, val_std_pred = self.forward(x_val_t)
        
        evaluation_time = execution_time(start=start, end=time.time())
        print(f"Evaluation time = {evaluation_time}")

        T_val_bnn = T_val_bnn.squeeze()

        post_mean, post_std,q1, q2 , evaluation_dict = evaluate_posterior_samples(y_val=y_val,
            post_samples=T_val_bnn, n_params=self.n_val_points, n_trials=self.M_val)

        evaluation_dict.update({"evaluation_time":evaluation_time})

        return self.X_val, T_val_bnn, post_mean, post_std, q1, q2, evaluation_dict

    def save(self, net_name = "bnn_net.pt"):

        param_store = pyro.get_param_store()
        print(f"\nlearned params = {param_store}")
        param_store.save(self.model_path+"_"+net_name)

    def load(self, net_name = "bnn_net.pt"):
        path = self.model_path+"_"+net_name
        param_store = pyro.get_param_store()
        param_store.load(path)
        for key, value in param_store.items():
            param_store.replace_param(key, value, value)
        print("\nLoading ", path)

    def run(self, n_epochs, lr, y_val, n_posterior_samples, identifier=1, train_flag=True):

        # print("Loading data...")
        self.load_train_data()
        self.load_val_data()

        self.set_training_options(n_epochs, lr)

        fld_id = "epochs={}_lr={}_id={}".format(n_epochs,lr, identifier)
        self.plot_path = f"BNNs/{plots_path}/BNN_Plots_{self.casestudy_id}_{self.det_network.architecture_name}_Arch_{fld_id}/"
        self.model_path = os.path.join("BNNs",models_path,f"BNN_{self.casestudy_id}_{self.det_network.architecture_name}_Arch_{fld_id}")

        os.makedirs(self.plot_path, exist_ok=True)
        os.makedirs(f"BNNs/{models_path}", exist_ok=True)

        if train_flag:
            print("Training...")
            training_time = self.train()
            print("Saving...")
            self.save()

            file = open(os.path.join(f"BNNs/{models_path}",f"BNN_{self.casestudy_id}_{self.det_network.architecture_name}_Arch_{fld_id}"),"w")
            file.writelines(training_time)
            file.close()

        else:
            self.load()
            file = open(os.path.join(f"BNNs/{models_path}",f"BNN_{self.casestudy_id}_{self.det_network.architecture_name}_Arch_{fld_id}"),"r+")
            print(f"\nTraining time = {file.read()}")

        return self.evaluate(y_val, n_posterior_samples)

