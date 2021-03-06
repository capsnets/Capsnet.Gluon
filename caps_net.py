import mxnet as mx
from mxnet import gluon
from mxnet.gluon import nn
from caps_layers import PrimaryCap, CapsuleLayer, length, Mask, squash

class CapsNet(gluon.HybridBlock):
    def __init__(self, n_class, num_routing, input_shape, outmask=True, **kwargs):
        super(CapsNet, self).__init__(**kwargs)
        N, C, W, H = input_shape
        self.n_class = n_class
        self.batch_size = N
        self.outmask = outmask
        self.input_shape = input_shape
        with self.name_scope():
            self.net = nn.HybridSequential(prefix='')
            self.net.add(nn.Conv2D(256, kernel_size=9, strides=1, padding=0, 
                                   activation='relu'))
            self.net.add(PrimaryCap(dim_capsule=8, n_channels=32, kernel_size=9, strides=2, 
                                    padding=0))
            caps_in_shape = (N, 1152, 8)
            weight_initializer = mx.init.Xavier(rnd_type='uniform', factor_type='avg', magnitude=3)
            self.net.add(CapsuleLayer(num_capsule=n_class, 
                                      dim_capsule=16, 
                                      num_routing=num_routing,
                                      in_shape=caps_in_shape, 
                                      weight_initializer=weight_initializer))
            
            self.decoder = nn.HybridSequential(prefix='')
            self.decoder.add(nn.Dense(512, activation='relu'))
            self.decoder.add(nn.Dense(1024, activation='relu'))
            self.decoder.add(nn.Dense(W*H, activation='sigmoid'))
            
    def hybrid_forward(self, F, x, y=None):
        digitcaps = self.net(x)
        #print "digitcaps", digitcaps.shape
        out_caps = length(F, digitcaps)
        
        if self.outmask:
            y_reshaped = F.reshape(y, (self.batch_size, -4, self.n_class, -1))
            #print "y_reshaped", y_reshaped.shape
            # decode network        
            #masked_by_y = Mask(F, [digitcaps, y])
            masked_by_y = F.linalg_gemm2(y_reshaped, digitcaps, transpose_a=True)
            masked_by_y = F.reshape(data=masked_by_y, shape=(-3, 0))
            out_mask = self.decoder(masked_by_y)
            out_mask = F.reshape(out_mask, self.input_shape)            
            return out_caps, out_mask
        else:
            return out_caps
        
    
def margin_loss(F, y_true, y_pred):
    """
    Margin loss for Eq.(4). When y_true[i, :] contains not just one `1`, this loss should work too. Not test it.
    :param y_true: [None, n_classes]
    :param y_pred: [None, num_capsule]
    :return: a scalar loss value.
    """    
    loss = y_true * F.square(F.maximum(0., 0.9 - y_pred)) + \
        0.5 * (1 - y_true) * F.square(F.maximum(0., y_pred - 0.1))
    return F.mean(F.sum(loss, 1))
    
def mask_mse_loss(F, mask_true, mask_pred):
    squared_error = F.square(mask_pred-mask_true)
    recon_error = F.mean(squared_error)
    return recon_error
    
    
        
        