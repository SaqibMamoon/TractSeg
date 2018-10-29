import os
from tractseg.experiments.old_3.LowResClassificationConfig import Config as LowResClassificationConfig


class Config(LowResClassificationConfig):
    EXP_NAME = os.path.basename(__file__).split(".")[0]

    NUM_EPOCHS = 200
    MODEL = "UNet_Pytorch_weighted"
    CLASSES = "20_endpoints"
    LOSS_WEIGHT = 10
    LOSS_WEIGHT_LEN = 100       #nr of epochs

