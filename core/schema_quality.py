from core.models import ParsedSchema


class SchemaQualityAnalyzer:

    def __init__(self, schema: ParsedSchema):
        self.schema = schema

    def tables_without_primary_keys(self):

        tables = []

        for table in self.schema.tables:
            if not table.pk_columns:
                tables.append(table.name)

        return tables
    
    def fk_without_index(self):

        issues = []

        for table in self.schema.tables:

            indexed_columns = set()

            for idx in getattr(self.schema, "indexes", []):
                if idx.table == table.name:
                    indexed_columns.update(idx.columns)

            for col in table.columns:
                if col.is_foreign_key and col.name not in indexed_columns:
                    issues.append((table.name, col.name))

        return issues
    
    def nullable_ratio(self):

        ratios = {}

        for table in self.schema.tables:

            if not table.columns:
                continue

            nullable = sum(1 for c in table.columns if c.nullable)

            ratios[table.name] = nullable / len(table.columns)

        return ratios
    
    def weak_tables(self):

        weak = []

        ratios = self.nullable_ratio()

        for table in self.schema.tables:

            if table.name in self.tables_without_primary_keys():
                weak.append(table.name)

            elif ratios.get(table.name, 0) > 0.7:
                weak.append(table.name)

        return weak
    
    def quality_score(self):

        score = 10

        if self.tables_without_primary_keys():
            score -= 2

        if self.fk_without_index():
            score -= 2

        weak = self.weak_tables()

        score -= min(len(weak), 3)

        return max(score, 0)