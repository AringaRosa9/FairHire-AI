import type { ButtonHTMLAttributes, ReactNode } from "react";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode;
  variant?: "primary" | "secondary";
};

export function Button({ children, variant = "secondary", ...props }: Props) {
  return (
    <button className="fh-button" data-variant={variant} {...props}>
      {children}
    </button>
  );
}
