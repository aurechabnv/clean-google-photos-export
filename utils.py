import logging
import typer


def log_console(log_message: str):
    """
    Log a message both to the console and into the logs
    Args:
        log_message: message to print
    """
    logging.info(log_message)
    typer.echo(log_message)


def warn_console(log_message: str):
    """
    Log a warning message both to the soncole and into the logs
    Args:
        log_message: message to print
    """
    logging.warning(log_message)
    typer.secho(message=log_message, fg=typer.colors.RED)


class Stepper:
    total_steps: int = 0
    current_step: int = 0

    def show_progression(self) -> str:
        """
        Returns: current progression stage as "step/total_steps"
        """
        self.current_step += 1
        return str(self.current_step) + "/" + str(self.total_steps)
