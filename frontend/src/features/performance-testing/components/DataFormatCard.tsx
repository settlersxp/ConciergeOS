import type { DataFormat } from "@/shared/types";
import { Card, FormField, Select } from "@/shared/ui";

interface DataFormatCardProps {
  dataFormat: DataFormat;
  onDataFormatChange: (v: DataFormat) => void;
}

export default function DataFormatCard({
  dataFormat,
  onDataFormatChange,
}: DataFormatCardProps) {
  return (
    <Card title="Data Format">
      <div className="mt-4">
        <FormField htmlFor="dataFormat" label="Guest Data Format">
      <Select
        id="dataFormat"
        value={dataFormat}
        onChange={(e) => onDataFormatChange(e.target.value as DataFormat)}
      >
        <option value="csv">CSV</option>
        <option value="json">JSON</option>
        <option value="xml">XML</option>
        <option value="tool_calling">Tool Calls</option>
      </Select>
        </FormField>
      </div>
    </Card>
  );
}