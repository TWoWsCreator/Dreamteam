from .postgres import PostgresRepository
from .series import SeriesRepository


class UnitOfWork:
    def __init__(self, connection):
        self.connection = connection
        self.players = PostgresRepository(connection)
        self.series = SeriesRepository(connection)

    def transaction(self):
        return self.connection.transaction()
