import torch
import warnings
from gpytorch.functions import log_normal_cdf
from gpytorch.distributions import base_distributions
from gpytorch.likelihoods.likelihood import _OneDimensionalLikelihood


class BinomialLikelihood(_OneDimensionalLikelihood):

    def __init__(self):
        super(BinomialLikelihood, self).__init__()

    def forward(self, function_samples, **kwargs):
        # conditional distribution p(y|f(x))
        # print("\nfwd function_samples", function_samples.shape)
        output_probs = torch.tensor(base_distributions.Normal(0, 1).cdf(function_samples))
        # print("\nfwd output_probs", output_probs.shape)
        return base_distributions.Binomial(total_count=self.n_trials, probs=output_probs)

    def log_marginal(self, observations, function_dist, *args, **kwargs):
        marginal = self.marginal(function_dist, *args, **kwargs)
        return marginal.log_prob(observations)

    def marginal(self, function_dist, **kwargs):
        # predictive distribution
        mean = function_dist.mean
        var = function_dist.variance
        link = mean.div(torch.sqrt(1 + var))
        output_probs = base_distributions.Normal(0, 1).cdf(link)
        return base_distributions.Binomial(total_count=self.n_trials, probs=output_probs)

    def expected_log_prob(self, observations, function_dist, *params, **kwargs):

        raise NotImplementedError

        # expected log likelihood over the variational GP distribution

        # def log_prob_lambda(function_samples):
        #     print(function_samples)
        #     print(observations)
        #     print(function_samples.shape)
        #     print(observations.shape)
        #     print((function_samples.mul(observations)).shape)
        #     print(self.n_trials)
        #     exit()
        #     return log_normal_cdf(function_samples.mul(observations))

        # log_prob_lambda = lambda function_samples: log_normal_cdf(function_samples.mul(observations))

        # log_prob = self.quadrature(log_prob_lambda, function_dist)
        # log_prob = 
        print(log_prob)
        print(log_prob.shape)
        exit()
        return log_prob

