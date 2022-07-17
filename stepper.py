class Stepper:
    total_steps: int = 0
    current_step: int = 0

    def show_progression(self) -> str:
        self.current_step += 1
        return str(self.current_step) + "/" + str(self.total_steps)
