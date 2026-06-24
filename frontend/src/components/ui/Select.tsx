interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  helperText?: string;
}

export default function Select({ helperText, className = "", ...props }: SelectProps) {
  return (
    <div>
      <select
        className={`w-full rounded-md border border-surface-300 bg-white px-3 py-2 text-sm text-primary-800 focus:border-secondary-400 focus:outline-none focus:ring-2 focus:ring-secondary-400/20 dark:border-primary-600 dark:bg-primary-700 dark:text-white ${className}`}
        {...props}
      />
      {helperText && (
        <p className="mt-1 text-xs text-primary-500 dark:text-primary-400">
          {helperText}
        </p>
      )}
    </div>
  );
}