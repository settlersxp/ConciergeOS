import { useEffect } from "react";

interface ToastProps {
  message: string;
  type: "success" | "error" | "info";
  onHidden: () => void;
  duration?: number;
}

const typeClasses: Record<string, string> = {
  success: "bg-secondary-500",
  error: "bg-accent-600",
  info: "bg-primary-600",
};

export default function Toast({ message, type, onHidden, duration = 3000 }: ToastProps) {
  useEffect(() => {
    const timer = setTimeout(onHidden, duration);
    return () => clearTimeout(timer);
  }, [onHidden, duration]);

  return (
    <div
      className={`fixed right-5 top-5 z-50 rounded-lg px-5 py-3 text-sm font-medium text-white shadow-lg animate-slide-in ${typeClasses[type]}`}
      role="alert"
    >
      {message}
    </div>
  );
}