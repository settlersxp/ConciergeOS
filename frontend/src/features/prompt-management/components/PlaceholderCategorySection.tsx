import PlaceholderItem from "./PlaceholderItem";
interface Props {
  title: string;
  items: { key: string; description: string; category: string; dynamic: boolean; example: string }[];
}
export default function PlaceholderCategorySection({ title, items }: Props) {
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-primary-800 dark:text-primary-200">{title}</h3>
      {items.map((p) => <PlaceholderItem key={p.key} placeholder={p} />)}
    </div>
  );
}
