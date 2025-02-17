import torch
from ...frontend.torch_frontend import ScatteringTorch
from ..core.scattering3d import scattering3d
from .base_frontend import ScatteringBase3D


class HarmonicScatteringTorch3D(ScatteringTorch, ScatteringBase3D):
    def __init__(self, J, shape, L=3, sigma_0=1, max_order=2, rotation_covariant=True, method='integral', points=None,
                 integral_powers=(0.5, 1., 2.), backend='torch', window=None): # MP: added new argument
        ScatteringTorch.__init__(self)
        ScatteringBase3D.__init__(self, J, shape, L, sigma_0, max_order,
                                  rotation_covariant, method, points,
                                  integral_powers, backend, window) # MP: added new argument

        self.build()

    def build(self):
        ScatteringBase3D._instantiate_backend(self, 'kymatio.scattering3d.backend.')
        ScatteringBase3D.build(self)
        ScatteringBase3D.create_filters(self)

        self.register_filters()

    def register_filters(self):
        # transfer the filters from numpy to torch
        for k in range(len(self.filters)):
            filt = torch.zeros(self.filters[k].shape + (2,))
            filt[..., 0] = torch.from_numpy(self.filters[k].real).reshape(self.filters[k].shape)
            filt[..., 1] = torch.from_numpy(self.filters[k].imag).reshape(self.filters[k].shape)
            self.filters[k] = filt
            self.register_buffer('tensor' + str(k), self.filters[k])

        g = torch.zeros(self.gaussian_filters.shape + (2,))
        g[..., 0] = torch.from_numpy(self.gaussian_filters.real)
        self.gaussian_filters = g
        self.register_buffer('tensor_gaussian_filter', self.gaussian_filters)
        
        # MP: New block starts here ----
        
        if self.window is not None:
            w = torch.zeros(self.window.shape + (2,))
            w[..., 0] = torch.from_numpy(self.window.real)
            w[..., 1] = torch.from_numpy(self.window.imag)
            self.window = w
            self.register_buffer("tensor_window", self.window)
        
        # MP: New block ends here ------

    def scattering(self, input_array):
        if not torch.is_tensor(input_array):
            raise TypeError(
                'The input should be a torch.cuda.FloatTensor, '
                'a torch.FloatTensor or a torch.DoubleTensor.')

        if input_array.dim() < 3:
            raise RuntimeError('Input tensor must have at least three '
                               'dimensions.')

        if (input_array.shape[-1] != self.O or input_array.shape[-2] != self.N
            or input_array.shape[-3] != self.M):
            raise RuntimeError(
                'Tensor must be of spatial size (%i, %i, %i).' % (
                    self.M, self.N, self.O))

        input_array = input_array.contiguous()

        batch_shape = input_array.shape[:-3]
        signal_shape = input_array.shape[-3:]

        input_array = input_array.reshape((-1,) + signal_shape + (1,))


        buffer_dict = dict(self.named_buffers())
        for k in range(len(self.filters)):
            self.filters[k] = buffer_dict['tensor' + str(k)]
        
        if self.window is not None:
            self.window = buffer_dict['tensor_window'] # MP: added line

        methods = ['integral', 'map'] # MP: modified from ['integral']
        if not self.method in methods:
            raise ValueError('method must be in {}'.format(methods))

        if self.method == 'integral': \
                self.averaging = lambda x: self.backend.compute_integrals(x, self.integral_powers)
            
        # MP: new block starts here ----------

        if self.method == 'map':
                self.averaging = lambda x: self.backend.compute_maps(x, self.integral_powers)

        # MP: new block ends here ------------

        S = scattering3d(input_array, filters=self.filters, rotation_covariant=self.rotation_covariant, L=self.L,
                         J=self.J, max_order=self.max_order, backend=self.backend, averaging=self.averaging,
                         window=self.window) # MP: added new arguemnt
        scattering_shape = S.shape[1:]

        S = S.reshape(batch_shape + scattering_shape)

        return S


HarmonicScatteringTorch3D._document()


__all__ = ['HarmonicScatteringTorch3D']
