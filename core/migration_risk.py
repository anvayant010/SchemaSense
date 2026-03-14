from core.models import ParsedSchema
from core.schema_graph import SchemaGraph
from core.schema_complexity import SchemaComplexityAnalyzer


class MigrationRiskAnalyzer:

    def __init__(self, schema: ParsedSchema):
        self.schema = schema
        self.graph_engine = SchemaGraph(schema)
        self.complexity = SchemaComplexityAnalyzer(schema)

        self.graph_engine.build_graph()

    def fk_density(self):

        tables = len(self.schema.tables)

        if tables == 0:
            return 0

        return self.schema.foreign_keys_count / tables
    
    def dependency_depth(self):

        return self.graph_engine.dependency_depth()
    
    def uses_advanced_types(self):

        return self.schema.has_advanced_types
    
    def risk_score(self):

        depth = self.dependency_depth()
        fk_density = self.fk_density()
        advanced = 1 if self.uses_advanced_types() else 0

        score = (
            depth * 0.4 +
            fk_density * 0.4 +
            advanced * 0.2
        )

        return round(score, 2)
    
    def risk_level(self):

        score = self.risk_score()

        if score < 1:
            return "LOW"

        elif score < 2:
            return "MEDIUM"

        else:
            return "HIGH"
        
    def risk_factors(self):

        factors = []

        if self.dependency_depth() >= 3:
            factors.append("Deep dependency chains")

        if self.fk_density() > 1:
            factors.append("High foreign key density")

        if self.uses_advanced_types():
            factors.append("Advanced database types used")

        return factors