interface PageHeaderProps {
  title: string;
  description?: string;
  className?: string;
}

export default function PageHeader({ title, description, className = "" }: PageHeaderProps) {
  return (
    <div className={`mb-6 ${className}`}>
      <h1 className="text-2xl font-semibold text-primary-900 dark:text-white">
        {title}
      </h1>
      {description && (
        <p className="mt-1 text-sm text-primary-500 dark:text-primary-400">
          {description}
        </p>
      )}
    </div>
  );
}