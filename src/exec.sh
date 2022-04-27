#!/bin/bash

############
# settings #
############

N_POSTERIOR_SAMPLES=100

EP_GP_N_EPOCHS=3000
EP_GP_LR=0.01

SVI_GP_VARIATIONAL_DISTRIBUTION="cholesky"
SVI_GP_VARIATIONAL_STRATEGY="default"
SVI_GP_BATCH_SIZE=100
SVI_GP_N_EPOCHS=500
SVI_GP_LR=0.01

SVI_BNN_ARCHITECTURE="3L"
SVI_BNN_BATCH_SIZE=100
SVI_BNN_N_EPOCHS=10000
SVI_BNN_LR=0.001
SVI_BNN_N_HIDDEN=30

#######
# run #
#######

source ../venv/bin/activate

DATE=$(date +%Y-%m-%d)
TIME=$(date +%H:%M:%S)
LOGS="out/logs/"
mkdir -p $LOGS
OUT="${LOGS}${DATE}_${TIME}_out.txt"

# python EP_GPs/train.py --n_epochs=$EP_GP_N_EPOCHS --lr=$EP_GP_LR >> $OUT 2>&1

# python SVI_GPs/train.py --variational_distribution=$SVI_GP_VARIATIONAL_DISTRIBUTION \
# 	--variational_strategy=$SVI_GP_VARIATIONAL_STRATEGY --batch_size=$SVI_GP_BATCH_SIZE \
# 	--n_epochs=$SVI_GP_N_EPOCHS --lr=$SVI_GP_LR --n_posterior_samples=$N_POSTERIOR_SAMPLES >> $OUT 2>&1

# python SVI_BNNs/train.py --architecture=$SVI_BNN_ARCHITECTURE --batch_size=$SVI_BNN_BATCH_SIZE \
# 	--n_epochs=$SVI_BNN_N_EPOCHS --lr=$SVI_BNN_LR --n_hidden=$SVI_BNN_N_HIDDEN \
# 	--n_posterior_samples=$N_POSTERIOR_SAMPLES >> $OUT 2>&1

python plot_comparison.py --ep_gp_n_epochs=$EP_GP_N_EPOCHS --ep_gp_lr=$EP_GP_LR \
	--svi_gp_variational_distribution=$SVI_GP_VARIATIONAL_DISTRIBUTION \
	--svi_gp_variational_strategy=$SVI_GP_VARIATIONAL_STRATEGY --svi_gp_batch_size=$SVI_GP_BATCH_SIZE \
	--svi_gp_n_epochs=$SVI_GP_N_EPOCHS --svi_gp_lr=$SVI_GP_N_EPOCHS --svi_bnn_architecture=$SVI_BNN_ARCHITECTURE \
	--svi_bnn_batch_size=$SVI_BNN_BATCH_SIZE --svi_bnn_n_epochs=$SVI_BNN_N_EPOCHS --svi_bnn_lr=$SVI_BNN_LR \
	--svi_bnn_n_hidden=$SVI_BNN_N_HIDDEN --n_posterior_samples=$N_POSTERIOR_SAMPLES >> $OUT 2>&1