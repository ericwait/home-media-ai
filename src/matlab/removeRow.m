idToRemove = rowIndex;

conn = database('mariaDB');
tableName = 'media';
columnNames = {'is_removed';'updated_at'};
datum = {1, 'NOW()'};
whereClause = sprintf('WHERE id = %d', idToRemove);
update(conn, tableName, columnNames, datum, whereClause);
close(conn);