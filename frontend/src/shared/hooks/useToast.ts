import { useCallback, useState } from "react";

export type ToastType = "success" | "error" | "info" | "warning";

export interface ToastState {
  message: string;
  type: ToastType;
  visible: boolean;
}

interface UseToastReturn {
  toast: ToastState;
  showToast: (message: string, type?: ToastType, duration?: number) => void;
  hideToast: () => void;
}

/**
 * Hook that manages toast notification state.
 * Each call returns independent state, so every component gets its own toast.
 *
 * @example
 *   const { toast, showToast, hideToast } = useToast();
 *   return (
 *     <>
 *       {toast.visible && <Toast message={toast.message} type={toast.type} onHidden={hideToast} />}
 *       <Button onClick={() => showToast("Saved!", "success")}>Save</Button>
 *     </>
 *   );
 */
export function useToast(duration = 3000): UseToastReturn {
  const [toast, setToast] = useState<ToastState>({
    message: "",
    type: "info",
    visible: false,
  });

  const hideToast = useCallback(() => {
    setToast((prev) => ({ ...prev, visible: false }));
  }, []);

  const showToast = useCallback(
    (message: string, type: ToastType = "info", dur = duration) => {
      setToast({ message, type, visible: true });
      // Auto-hide after duration
      setTimeout(() => {
        setToast((prev) => ({ ...prev, visible: false }));
      }, dur);
    },
    [duration],
  );

  return { toast, showToast, hideToast };
}