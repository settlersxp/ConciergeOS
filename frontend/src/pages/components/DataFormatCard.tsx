import type { DataFormat } from "../../types";
import { Card, FormField, Select } from "../../components/ui";

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
          </Select>
        </FormField>
      </div>
    </Card>
  );
}