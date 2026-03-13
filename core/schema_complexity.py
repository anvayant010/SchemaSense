from core.models import ParsedSchema
from core.schema_graph import SchemaGraph


class SchemaComplexityAnalyzer:

    def __init__(self, schema: ParsedSchema):
        self.schema = schema
        self.graph_engine = SchemaGraph(schema)
        self.graph = self.graph_engine.build_graph()

    def table_count(self):
        return len(self.graph.nodes)

    def foreign_key_count(self):
        return len(self.graph.edges)

    def join_density(self):
        if self.table_count() == 0:
            return 0
        return self.foreign_key_count() / self.table_count()

    def dependency_depth(self):
        return self.graph_engine.dependency_depth()
    
    def hub_tables(self):
        hubs = []

        for node in self.graph.nodes:
            degree = self.graph.degree(node)

            if degree >= 3:
                hubs.append(node)

        return hubs
    
    def fanout_tables(self):
        fanouts = []

        for node in self.graph.nodes:
            out_degree = self.graph.out_degree(node)

            if out_degree >= 2:
                fanouts.append(node)

        return fanouts
    
    def complexity_score(self):

        tables = self.table_count()
        joins = self.foreign_key_count()
        depth = self.dependency_depth()

        score = (
            tables * 0.3 +
            joins * 0.4 +
            depth * 0.3
        )

        return round(score, 2)