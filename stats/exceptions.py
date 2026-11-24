from rest_framework import status

from telemetry.exceptions import ContractError


class SimulationNotFound(ContractError):
    status_code = status.HTTP_404_NOT_FOUND
    default_code = "simulation_not_found"
    default_detail = "La simulación no existe."


class NotFoundForSimulation(ContractError):
    status_code = status.HTTP_404_NOT_FOUND
    default_code = "not_found"
    default_detail = "Este endpoint no existe para la simulación."
