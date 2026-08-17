import { motion } from "framer-motion";

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

export function Button({
  children,
  tone = "secondary",
  size = "md",
  icon,
  className = "",
  disabled,
  ...props
}) {
  const sizes = {
    sm: "px-3 py-1.5 text-[13px] gap-1.5",
    md: "px-4 py-2 text-sm gap-2",
    lg: "px-5 py-2.5 text-[15px] gap-2",
  };
  return (
    <motion.button
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
}

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
