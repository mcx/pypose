import torch
from torch import nn


class Controller(nn.Module):
    r"""
    This class is the basic class for all controller implementations.
    """
    def __init__(self):
        pass

    def get_control(self, parameters, state, ref_state, feed_forward_quantity):
        r"""
        Args:
            parameters: controller parameters, e.g. kp, ki, kd in PID controllers.
            state:  current system state of dynamic systems.
            ref_state:  the reference state of systems to reach.
            feed_forward_quantity: system plant input generated by other feed forward
                controllers.
        """
        pass

    def reset(self):
        r"""
        This method is used to reset the internal state.
        For example, integrated error in PID controller
        """
        pass
