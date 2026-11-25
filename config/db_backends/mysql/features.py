from functools import cached_property

from django.db.backends.mysql.features import (
    DatabaseFeatures as MySQLDatabaseFeatures,
)


class DatabaseFeatures(MySQLDatabaseFeatures):
    """Compatibility features for MariaDB 10.4 shipped with XAMPP.

    Django 5.2 targets MariaDB 10.5+, mainly because 10.5 introduced
    ``INSERT ... RETURNING``. XAMPP's bundled MariaDB 10.4 is fully sufficient
    for the ORM features used by this project, so the version floor is lowered
    and unsupported RETURNING support is disabled.
    """

    @cached_property
    def minimum_database_version(self):
        if self.connection.mysql_is_mariadb:
            return (10, 4)
        return (8, 0, 11)

    @cached_property
    def can_return_columns_from_insert(self):
        return self.connection.mysql_version >= (10, 5)

    @property
    def can_return_rows_from_bulk_insert(self):
        return self.can_return_columns_from_insert
