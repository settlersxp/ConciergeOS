import { forwardRef } from "react";

interface InputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "prefix"> {
  helperText?: string;
  prefix?: string;
}

const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ helperText, prefix, className = "", ...props }, ref) => {
    return (
      <div>
        <input
          ref={ref}
          className={`w-full rounded-md border border-surface-300 bg-white px-3 py-2 text-sm text-primary-800 placeholder:text-primary-400 focus:border-secondary-400 focus:outline-none focus:ring-2 focus:ring-secondary-400/20 dark:border-primary-600 dark:bg-primary-700 dark:text-white dark:placeholder:text-primary-500 ${prefix ? "pl-10" : ""} ${className}`}
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
);

Input.displayName = "Input";

export default Input;