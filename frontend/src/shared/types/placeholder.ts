export interface PlaceholderDefinition {
  key: string;
  description: string;
  category: "schema" | "data" | "context";
  dynamic: boolean;
  example: string;
}
