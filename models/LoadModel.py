import numpy as np
from torch import nn
import torch
from torchvision import models, transforms, datasets
import torch.nn.functional as F
import pretrainedmodels

from config import pretrained_model

import pdb

class MainModel(nn.Module):
    def __init__(self, config):
        super(MainModel, self).__init__()
        self.use_dcl = config.use_dcl
        self.num_classes = config.numcls
        self.backbone_arch = config.backbone
        self.use_Asoftmax = config.use_Asoftmax
        print(self.backbone_arch)

        if self.backbone_arch in dir(models):
            self.model = getattr(models, self.backbone_arch)()
            if self.backbone_arch in pretrained_model:
                self.model.load_state_dict(torch.load(pretrained_model[self.backbone_arch]))
        else:
            if self.backbone_arch in pretrained_model:
                self.model = pretrainedmodels.__dict__[self.backbone_arch](num_classes=1000, pretrained=None)
            else:
                self.model = pretrainedmodels.__dict__[self.backbone_arch](num_classes=1000)

        if self.backbone_arch == 'resnet50' or self.backbone_arch == 'se_resnet50':
            self.model = nn.Sequential(*list(self.model.children())[:-2])
        if self.backbone_arch == 'senet154':
            self.model = nn.Sequential(*list(self.model.children())[:-3])
        if self.backbone_arch == 'se_resnext101_32x4d':
            self.model = nn.Sequential(*list(self.model.children())[:-2])
        if self.backbone_arch == 'se_resnet101':
            self.model = nn.Sequential(*list(self.model.children())[:-2])
        self.avgpool = nn.AdaptiveAvgPool2d(output_size=1)
        self.classifier = nn.Linear(2048, self.num_classes, bias=False)

        if self.use_dcl:
            if config.cls_2:
                self.classifier_swap = nn.Linear(2048, 2, bias=False)
            if config.cls_2xmul:
                self.classifier_swap = nn.Linear(2048, 2*self.num_classes, bias=False)
            self.Convmask = nn.Conv2d(2048, 1, 1, stride=1, padding=0, bias=True)
            self.avgpool2 = nn.AvgPool2d(2, stride=2)

        if self.use_Asoftmax:
            self.Aclassifier = AngleLinear(2048, self.num_classes, bias=False)

    def forward(self, x, last_cont=None):
        x = self.model(x) # torch.Size([8, 2048, 14, 14])
        if self.use_dcl: # reference to 3.2 Construction Learning in paper
            mask = self.Convmask(x) # torch.Size([8, 1, 14, 14])
            mask = self.avgpool2(mask) # torch.Size([8, 1, 7, 7])
            mask = torch.tanh(mask) #
            mask = mask.view(mask.size(0), -1) # torch.Size([8, 49])

        x = self.avgpool(x) # torch.Size([8, 2048, 1, 1]) (output_size =1)
        x = x.view(x.size(0), -1) # torch.Size([8, 2048])
        out = []
        # reference to 3.1.1 region confusion mechanism
        out.append(self.classifier(x)) # nn.Linear(2048,200) torch.Size([8, 200])

        if self.use_dcl:
            # reference to 3.1.2 Adversarial learning
            out.append(self.classifier_swap(x)) # nn.Linear(2048,400) torch.Size([8, 400])
            # reference to 3.2 Construction Learning in paper
            out.append(mask) # torch.Size([8, 2048])

        if self.use_Asoftmax:
            if last_cont is None:
                x_size = x.size(0)
                out.append(self.Aclassifier(x[0:x_size:2]))
            else:
                last_x = self.model(last_cont)
                last_x = self.avgpool(last_x)
                last_x = last_x.view(last_x.size(0), -1)
                out.append(self.Aclassifier(last_x))

        return out
