import networkx as nx
from core.models import ParsedSchema


class SchemaGraph:

    def __init__(self, schema: ParsedSchema):
        self.schema = schema
        self.graph = nx.DiGraph()

    def build_graph(self):
        """
        Build a directed graph of table dependencies.
        Nodes = tables
        Edges = foreign key relationships
        """

        for table in self.schema.tables:
            self.graph.add_node(table.name)

        for table in self.schema.tables:
            for col in table.columns:
                if col.is_foreign_key and col.references:
                    ref_table = col.references.get("table")

                    if ref_table:
                        self.graph.add_edge(
                            table.name,
                            ref_table,
                            column=col.name
                        )

        return self.graph
    
    def dependency_depth(self):
        """
        Compute maximum dependency chain length
        """

        if not self.graph.nodes:
            return 0

        longest = 0

        for node in self.graph.nodes:
            lengths = nx.single_source_shortest_path_length(self.graph, node)
            if lengths:
                longest = max(longest, max(lengths.values()))

        return longest
    
    def join_density(self):
        """
        Foreign keys / tables
        """

        table_count = len(self.graph.nodes)
        fk_count = len(self.graph.edges)

        if table_count == 0:
            return 0

        return fk_count / table_count
    
    def detect_cycles(self):
        """Detect circular dependencies
        """

        try:
            cycles = []

            for cycle in nx.simple_cycles(self.graph):
                if len(cycle) > 1:
                    cycles.append(cycle)

            return cycles
            
        except Exception:
            return []
        
    def migration_order(self):
        """
        Determine safe table creation order: referenced tables before referencing tables.
        Edges in self.graph point child -> parent (employees -> departments).
        Topological sort on the REVERSED graph gives parent-first order.
        """
        try:
            g = self.graph.copy()
            g.remove_edges_from(nx.selfloop_edges(g))
            return list(nx.topological_sort(g.reverse()))
        except nx.NetworkXUnfeasible:
            return list(self.graph.nodes)