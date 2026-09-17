from dataclasses import dataclass


@dataclass(frozen=True)
class StressCoupling:
    """
    The single term through which cognitive state reaches every distortion module.

    One stress value `s` produced by the cognitive layer scales the spatial,
    temporal and gesture modules through this one object. That shared scaling is
    the coupling: the modules do not each hold their own notion of stress, and
    there is exactly one parameter, `alpha`, controlling how hard stress bites.

    Modules may respond with different *relative* sensitivity — a hurried finger
    scatters more along the direction of travel than across it — but every
    response derives from the same `s` and the same `alpha`, so sweeping alpha
    moves the whole engine coherently (EXP-04).
    """

    alpha: float = 2.5

    def factor(self, stress, sensitivity=1.0):
        """Multiplier applied to a module's nominal spread: 1 + alpha*sensitivity*s."""
        if not 0.0 <= stress <= 1.0:
            raise ValueError(f"stress must be in [0,1], got {stress}")
        return 1.0 + self.alpha * sensitivity * stress
