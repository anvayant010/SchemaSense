import json

class SchemaAnalyzer:
    def __init__(self, schema, db_features_path="data/db_features.json"):
        self.schema = schema
        with open(db_features_path, "r", encoding="utf-8") as f:
            self.db_profiles = json.load(f)

    def analyze(self):
        results = {}
        for db_name, features in self.db_profiles.items():
            type_score = self._match_data_types(features["supported_types"])
            fk_score = 10 if features["foreign_key_support"] else 5
            json_score = 10 if features["json_support"] else 5
            complexity = (features["complex_query_support"] + features["scalability"]) / 2

            total = (type_score * 0.4) + (fk_score * 0.2) + (json_score * 0.1) + (complexity * 0.3)
            results[db_name] = round(total, 2)

        return dict(sorted(results.items(), key=lambda x: x[1], reverse=True))

    def _match_data_types(self, supported_types):
        all_columns = [col["data_type"].split("(")[0].upper() for table in self.schema for col in table["columns"]]
        matches = sum(1 for col in all_columns if col in supported_types)
        return (matches / len(all_columns)) * 10 if all_columns else 0
