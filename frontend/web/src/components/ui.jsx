import { forwardRef, useEffect, useRef } from "react";
import { AnimatePresence, motion } from "framer-motion";

export function Card({ children, className = "", ...props }) {
  return (
    <div
      className={`rounded-2xl border border-ink-100 bg-white/90 backdrop-blur-sm shadow-soft ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardBody({ children, className = "" }) {
  return <div className={`p-5 sm:p-6 ${className}`}>{children}</div>;
}

export function SectionTitle({ icon, children, badge }) {
  return (
    <h2 className="flex items-center gap-2 text-[15px] font-semibold text-ink-900 mb-1">
      {icon}
      {children}
      {badge && (
        <span className="ml-1 rounded-full bg-ink-100 px-2 py-0.5 text-[11px] font-medium text-ink-500">
          {badge}
        </span>
      )}
    </h2>
  );
}

export function Badge({ children, tone = "neutral" }) {
  const tones = {
    neutral: "bg-ink-100 text-ink-600",
    brand: "bg-brand-100 text-brand-700",
    success: "bg-emerald-100 text-emerald-700",
    danger: "bg-rose-100 text-rose-700",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-medium ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

const BUTTON_TONES = {
  primary: "bg-brand-600 text-white shadow-pop hover:bg-brand-700 focus-visible:ring-brand-400",
  secondary: "bg-white text-ink-700 border border-ink-200 hover:bg-ink-50 focus-visible:ring-ink-300",
  danger: "bg-white text-rose-600 border border-rose-200 hover:bg-rose-50 focus-visible:ring-rose-300",
  success: "bg-emerald-600 text-white shadow-pop hover:bg-emerald-700 focus-visible:ring-emerald-400",
  ghost: "text-ink-500 hover:bg-ink-100 hover:text-ink-800",
};

export const Button = forwardRef(function Button(
  { children, tone = "secondary", size = "md", icon, className = "", disabled, ...props },
  ref
) {
  const sizes = {
    sm: "px-3 py-1.5 text-[13px] gap-1.5",
    md: "px-4 py-2 text-sm gap-2",
    lg: "px-5 py-2.5 text-[15px] gap-2",
  };
  return (
    <motion.button
      ref={ref}
      whileTap={disabled ? {} : { scale: 0.96 }}
      disabled={disabled}
      className={`inline-flex items-center justify-center rounded-lg font-medium transition-colors
        focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1
        disabled:opacity-40 disabled:cursor-not-allowed disabled:shadow-none
        ${BUTTON_TONES[tone]} ${sizes[size]} ${className}`}
      {...props}
    >
      {icon}
      {children}
    </motion.button>
  );
});

export function Spinner({ className = "h-4 w-4" }) {
  return (
    <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-90" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
    </svg>
  );
}

export function Input(props) {
  return (
    <input
      {...props}
      className={`w-full rounded-lg border border-ink-200 bg-white px-3.5 py-2 text-sm text-ink-900
        placeholder:text-ink-400 outline-none transition
        focus:border-brand-400 focus:ring-2 focus:ring-brand-100 ${props.className || ""}`}
    />
  );
}

export function Textarea(props) {
  return (
    <textarea
      {...props}
      className={`w-full rounded-lg border border-ink-200 bg-white px-3.5 py-2.5 text-sm text-ink-900
        placeholder:text-ink-400 outline-none transition resize-y
        focus:border-brand-400 focus:ring-2 focus:ring-brand-100 font-mono leading-relaxed ${props.className || ""}`}
    />
  );
}

export function Select({ children, className = "", ...props }) {
  return (
    <select
      {...props}
      className={`rounded-lg border border-ink-200 bg-white px-3 py-2 text-sm text-ink-900 outline-none
        transition focus:border-brand-400 focus:ring-2 focus:ring-brand-100 ${className}`}
    >
      {children}
    </select>
  );
}

// Focus-trapped confirmation dialog for destructive actions (delete memory/
// skill override/subagent) -- every such action in this app used to fire
// immediately on click with no way to back out.
export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Delete",
  tone = "danger",
  onConfirm,
  onCancel,
}) {
  const dialogRef = useRef(null);
  const confirmRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    confirmRef.current?.focus();

    function onKeyDown(e) {
      if (e.key === "Escape") {
        onCancel();
        return;
      }
      if (e.key !== "Tab") return;
      const focusable = dialogRef.current?.querySelectorAll("button, [href], input, select, textarea");
      if (!focusable || focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onCancel]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          role="presentation"
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink-950/40 backdrop-blur-[2px] p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={(e) => e.target === e.currentTarget && onCancel()}
        >
          <motion.div
            ref={dialogRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="confirm-dialog-title"
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 8 }}
            transition={{ type: "spring", stiffness: 420, damping: 32 }}
            className="w-full max-w-sm rounded-2xl border border-ink-100 bg-white p-5 shadow-pop"
          >
            <h2 id="confirm-dialog-title" className="text-[15px] font-semibold text-ink-900">
              {title}
            </h2>
            {description && <p className="mt-1.5 text-sm text-ink-500">{description}</p>}
            <div className="mt-4 flex justify-end gap-2">
              <Button onClick={onCancel}>Cancel</Button>
              <Button ref={confirmRef} tone={tone} onClick={onConfirm}>
                {confirmLabel}
              </Button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
