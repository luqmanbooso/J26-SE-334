class StressModel:

    def __init__(self, stress=0.0):
        self.stress = max(0.0, min(1.0, stress))

    def set_stress(self, value):
        self.stress = max(0.0, min(1.0, value))

    def increase(self, amount):
        self.stress = min(1.0, self.stress + amount)

    def decrease(self, amount):
        self.stress = max(0.0, self.stress - amount)

    def get_stress(self):
        return self.stress

# 0.0 = completely calm
# 0.5 = moderate stress
# 1.0 = maximum modeled stress