class ModbusException(Exception):
    """Raised when the Modbus communication has error."""

    def __init__(self, status):
        """Initialize."""
        super().__init__(status)
        self.status = status


class ModbusPortException(ModbusException):
    """Raised when the Serial port in not available."""
