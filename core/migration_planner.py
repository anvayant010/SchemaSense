from core.models import ParsedSchema
from core.schema_graph import SchemaGraph


class MigrationPlanner:

    def __init__(self, schema: ParsedSchema):
        self.schema = schema
        self.graph_engine = SchemaGraph(schema)
        self.graph_engine.build_graph()

    def table_creation_order(self):

        return self.graph_engine.migration_order()
    
    def constraint_plan(self):

        steps = []

        if self.schema.primary_keys_count > 0:
            steps.append("Add primary key constraints")

        if self.schema.foreign_keys_count > 0:
            steps.append("Add foreign key constraints")

        return steps
    
    def index_plan(self):

        indexes = getattr(self.schema, "indexes", [])

        if not indexes:
            return ["No indexes defined"]

        steps = []

        for idx in indexes:
            steps.append(
                f"Create {'UNIQUE ' if idx.unique else ''}index {idx.name} on {idx.table}({', '.join(idx.columns)})"
            )

        return steps
    
    def generate_plan(self):

        plan = {}

        plan["table_creation_order"] = self.table_creation_order()
        plan["constraint_plan"] = self.constraint_plan()
        plan["index_plan"] = self.index_plan()

        return plan