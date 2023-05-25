from email.policy import strict
import torch
import torchvision.models
import os.path as osp
import copy
from ...log_service import print_log 
from .utils import \
    get_total_param, get_total_param_sum, \
    get_unit

# def load_state_dict(net, model_path):
#     if isinstance(net, dict):
#         for ni, neti in net.items():
#             paras = torch.load(model_path[ni], map_location=torch.device('cpu'))
#             new_paras = neti.state_dict()
#             new_paras.update(paras)
#             neti.load_state_dict(new_paras)
#     else:
#         paras = torch.load(model_path, map_location=torch.device('cpu'))
#         new_paras = net.state_dict()
#         new_paras.update(paras)
#         net.load_state_dict(new_paras)
#     return

# def save_state_dict(net, path):
#     if isinstance(net, (torch.nn.DataParallel,
#                         torch.nn.parallel.DistributedDataParallel)):
#         torch.save(net.module.state_dict(), path)
#     else:
#         torch.save(net.state_dict(), path)

def singleton(class_):
    instances = {}
    def getinstance(*args, **kwargs):
        if class_ not in instances:
            instances[class_] = class_(*args, **kwargs)
        return instances[class_]
    return getinstance

def preprocess_model_args(args):
    # If args has layer_units, get the corresponding
    #     units.
    # If args get backbone, get the backbone model.
    args = copy.deepcopy(args)
    if 'layer_units' in args:
        layer_units = [
            get_unit()(i) for i in args.layer_units
        ]
        args.layer_units = layer_units
    if 'backbone' in args:
        args.backbone = get_model()(args.backbone)
    return args

@singleton
class get_model(object):
    def __init__(self):
        self.model = {}

    def register(self, model, name):
        self.model[name] = model

    def __call__(self, cfg, verbose=True):
        """
        Construct model based on the config. 
        """
        if cfg is None:
            return None

        t = cfg.type

        # the register is in each file
        if t.find('pfd')==0:
            from .. import pfd
        elif t=='autoencoderkl':
            from .. import autokl
        elif (t.find('clip')==0) or (t.find('openclip')==0):
            from .. import clip
        elif t.find('openai_unet')==0:
            from .. import openaimodel
        elif t.find('controlnet')==0:
            from .. import controlnet
        elif t.find('seecoder')==0:
            from .. import seecoder
        elif t.find('swin')==0:
            from .. import swin

        args = preprocess_model_args(cfg.args)
        net = self.model[t](**args)

        pretrained = cfg.get('pretrained', None)
        if pretrained is None: # backward compatible
            pretrained = cfg.get('pth', None)
        map_location = cfg.get('map_location', 'cpu')
        strict_sd = cfg.get('strict_sd', True)

        if pretrained is not None:
            if osp.splitext(pretrained)[1] == '.pth':
                sd = torch.load(pretrained, map_location=map_location)
            elif osp.splitext(pretrained)[1] == '.ckpt':
                sd = torch.load(pretrained, map_location=map_location)['state_dict']
            elif osp.splitext(pretrained)[1] == '.safetensors':
                from safetensors.torch import load_file
                from collections import OrderedDict
                sd = load_file(pretrained, map_location)
                sd = OrderedDict(sd)
            net.load_state_dict(sd, strict=strict_sd)
            if verbose:
                print_log('Load model from [{}] strict [{}].'.format(pretrained, strict_sd))

        # display param_num & param_sum
        if verbose:
            print_log(
                'Load {} with total {} parameters,' 
                '{:.3f} parameter sum.'.format(
                    t, 
                    get_total_param(net), 
                    get_total_param_sum(net) ))
        return net

def register(name):
    def wrapper(class_):
        get_model().register(class_, name)
        return class_
    return wrapper
