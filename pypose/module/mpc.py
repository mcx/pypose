import pypose as pp
import torch.nn as nn


class MPC(nn.Module):
    r'''
    Model Predictive Control (MPC) based on iterative LQR.

    Args:
        system (:obj:`instance`): The system to be soved by MPC.
        T (:obj:`int`): Time steps of system.
        steps (:obj:`int`, optional): Total number of iterations for iterative LQR.
            Default: 10.
        eps (:obj:`int`, optional): Epsilon as the tolerance. Default: 1e-4.

    Model Predictive Control, also known as Receding Horizon Control (RHC), uses the
    mathematical model of the system in order to solve a finite, moving horizon, and
    closed loop optimal control problem. Thus, the MPC scheme is able to utilize the
    information about the current state of the system in order to predict future states
    and control inputs for the system. MPC requires that at each time step we solve the
    optimization problem:

    .. math::
        \begin{align*}
          \mathop{\arg\min}\limits_{\mathbf{x}_{1:T}, \mathbf{u}_{1:T}} \sum\limits_t
          \mathbf{c}_t (\mathbf{x}_t, \mathbf{u}_t) \\
          \mathrm{s.t.} \quad \mathbf{x}_{t+1} &= \mathbf{f}(\mathbf{x}_t, \mathbf{u}_t), \\
          \mathbf{x}_1 &= \mathbf{x}_{\text{init}} \\
        \end{align*}

    where :math:`\mathbf{c}` is the cost function; :math:`\mathbf{x}`, :math:`\mathbf{u}`
    are the state and input of the linear system; :math:`\mathbf{f}` is the dynamics model;
    :math:`\mathbf{x}_{\text{init}}` is the initial state of the system.

    For the linear system with quadratic cost, MPC is equivalent to solving an LQR problem
    on each horizon as well as considering the dynamics as constraints. For nonlinear
    system, one way to solve the MPC problem is to use iterative LQR, which uses linear
    approximations of the dynamics and quadratic approximations of the cost function to
    iteratively compute a local optimal solution based on the current states and control
    sequences. The analytical derivative can be computed using one additional pass of iLQR.

    The quadratic costs of the system over the time horizon:

        .. math::
            \mathbf{c} \left( \mathbf{\tau}_t \right) = \frac{1}{2}
            \mathbf{\tau}_t^\top\mathbf{Q}_t\mathbf{\tau}_t + \mathbf{p}_t^\top\mathbf{\tau}_t

    where :math:`\mathbf{\tau}_t` = :math:`\begin{bmatrix} \mathbf{x}_t \\ \mathbf{u}_t
    \end{bmatrix}`, :math:`\mathbf{Q}` is he weight matrix of the quadratic term,
    :math:`\mathbf{p}` is the weight vector of the first-order term.

    Then LQR finds the optimal nominal trajectory :math:`\mathbf{\tau}_{1:T}^*` =
    :math:`\begin{Bmatrix} \mathbf{x}_t, \mathbf{u}_t \end{Bmatrix}_{1:T}`
    for the linear system of the optimization problem:

    .. math::
        \begin{align*}
          \mathbf{\tau}_{1:T}^* = \mathop{\arg\min}\limits_{\tau_{1:T}} \sum\limits_t\frac{1}{2}
          \mathbf{\tau}_t^\top\mathbf{Q}_t\mathbf{\tau}_t + \mathbf{p}_t^\top\mathbf{\tau}_t \\
          \mathrm{s.t.} \quad \mathbf{x}_{t+1} &= \mathbf{f}(\mathbf{x}_t, \mathbf{u}_t), \\
          \mathbf{x}_1 &= \mathbf{x}_{\text{init}} \\
        \end{align*}

    The LQR process can be summarised as a backward and a forward recursion.

    Note:
        For the details of lqr solver and the iterative LQR, please refer to :meth:`LQR`.
        Please note that the linear system with quadratic cost only requires one single
        iteration.

    Note:
        The definition of MPC is cited from this book:

        * George Nikolakopoulos, Sina Sharif Mansouri, Christoforos Kanellakis, `Aerial Robotic Workers: Design, Modeling, Control, Vision and Their Applications
          <https://doi.org/10.1016/C2017-0-02260-7>`_,
          Butterworth-Heinemann, 2023.

        The implementation of MPC is based on Eq. (10)~(13) of this paper:

        * Amos, Brandon, et al, `Differentiable mpc for end-to-end planning and control
          <https://proceedings.neurips.cc/paper/2018/hash/ba6d843eb4251a4526ce65d1807a9309-Abstract.html>`_,
          Advances in neural information processing systems 31, 2018.

    Example:
        >>> import torch, pypose as pp
        >>> class CartPole(pp.module.NLS):
        ...     def __init__(self, dt, length, cartmass, polemass, gravity):
        ...         super().__init__()
        ...         self.tau = dt
        ...         self.length = length
        ...         self.cartmass = cartmass
        ...         self.polemass = polemass
        ...         self.gravity = gravity
        ...         self.polemassLength = self.polemass * self.length
        ...         self.totalMass = self.cartmass + self.polemass
        ...
        ...     def state_transition(self, state, input, t=None):
        ...         x, xDot, theta, thetaDot = state.squeeze()
        ...         force = input.squeeze()
        ...         costheta = torch.cos(theta)
        ...         sintheta = torch.sin(theta)
        ...
        ...         temp = (
        ...             force + self.polemassLength * thetaDot**2 * sintheta
        ...         ) / self.totalMass
        ...         thetaAcc = (self.gravity * sintheta - costheta * temp) / (
        ...             self.length * (4.0 / 3.0 - self.polemass * costheta**2 / self.totalMass)
        ...         )
        ...         xAcc = temp - self.polemassLength * thetaAcc * costheta / self.totalMass
        ...
        ...         _dstate = torch.stack((xDot, xAcc, thetaDot, thetaAcc))
        ...
        ...         return (state.squeeze() + torch.mul(_dstate, self.tau)).unsqueeze(0)
        ...
        ...     def observation(self, state, input, t=None):
        ...         return state
        >>>
        >>> torch.manual_seed(0)
        >>> dt, len, m_cart, m_pole, g = 0.01, 1.5, 20, 10, 9.81
        >>> n_batch, T = 1, 5
        >>> n_state, n_ctrl = 4, 1
        >>> n_sc = n_state + n_ctrl
        >>> Q = torch.tile(torch.eye(n_state + n_ctrl, device=device), (n_batch, T, 1, 1))
        >>> p = torch.randn(n_batch, T, n_sc)
        >>> time  = torch.arange(0, T, device=device) * dt
        >>> current_u = torch.sin(time).unsqueeze(1).unsqueeze(0)
        >>> x_init = torch.tensor([[0, 0, torch.pi, 0]])
        >>> cartPoleSolver = CartPole(dt, len, m_cart, m_pole, g).to(device)
        >>> MPC = pp.module.MPC(cartPoleSolver, T, step=15).to(device)
        >>> x, u, cost = MPC(Q, p, x_init, dt, current_u)
        >>> print("x = ", x)
        >>> print("u = ", u)
        x =  tensor([[[ 0.0000e+00,  0.0000e+00,  3.1416e+00,  0.0000e+00],
                      [ 0.0000e+00, -3.7711e-04,  3.1416e+00, -1.8856e-04],
                      [-3.7711e-06, -3.0693e-04,  3.1416e+00, -1.5347e-04],
                      [-6.8404e-06, -2.4288e-04,  3.1416e+00, -1.2136e-04],
                      [-9.2692e-06, -2.6634e-04,  3.1416e+00, -1.3293e-04],
                      [-1.1933e-05, -2.2073e-04,  3.1416e+00, -1.0991e-04]]])
        u =  tensor([[[-0.8485],
                      [ 0.1579],
                      [ 0.1440],
                      [-0.0530],
                      [ 0.1023]]])
    '''
    def __init__(self, system, T, step=10, eps=1e-4):
        super().__init__()
        self.system = system
        self.T = T
        self.step = step
        self.eps = eps

    def forward(self, Q, p, x_init, dt, current_u=None):
        r'''
        Performs MPC for the discrete system.

        Args:
            Q (:obj:`Tensor`): The weight matrix of the quadratic term.
            p (:obj:`Tensor`): The weight vector of the first-order term.
            x_init (:obj:`Tensor`): The initial state of the system.
            dt (:obj:`int`): The timestamp for ths system to estimate.
            current_u (:obj:`Tensor`, optinal): The current inputs of the system along a
                trajectory. Default: ``None``.

        Returns:
            List of :obj:`Tensor`: A list of tensors including the solved state sequence
            :math:`\mathbf{x}`, the solved input sequence :math:`\mathbf{u}`, and the associated
            quadratic costs :math:`\mathbf{c}` over the time horizon.
        '''
        best = None
        u = current_u

        for i in range(self.step):

            if u is not None:
                u = u.detach()

            lqr = pp.module.LQR(self.system, Q, p, self.T)
            x, u, cost = lqr(x_init, dt, u)
            assert x.ndim == u.ndim == 3

            if best is None:
                best = {
                    'u': u,
                    'cost': cost,}
            else:
                if cost <= best['cost']+ self.eps:
                    best['u']= u
                    best['cost'] = cost

        if self.step > 1:
            current_u = best['u']

        _lqr = pp.module.LQR(self.system, Q, p, self.T)
        x, u, cost= _lqr(x_init, dt, current_u)

        return x, u, cost