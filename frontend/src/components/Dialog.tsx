import { useEffect, type ReactNode } from "react";

interface DialogProps {
  title: string;
  onClose: () => void;
  children: ReactNode;
  minWidth?: string;
  closeOnBackdrop?: boolean;
}

export default function Dialog({
  title,
  onClose,
  children,
  minWidth = "700px",
  closeOnBackdrop = true,
}: DialogProps) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && closeOnBackdrop) onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [closeOnBackdrop, onClose]);

  return (
    <div
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)",
        display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
      }}
      onClick={closeOnBackdrop ? onClose : undefined}
    >
      <div
        style={{
          background: "#fff", borderRadius: 8, padding: 24,
          minWidth, maxWidth: 900, width: "85vw",
          maxHeight: "85vh", display: "flex", flexDirection: "column", position: "relative",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          style={{
            position: "absolute", top: 12, right: 12,
            border: "none", background: "none",
            fontSize: 20, cursor: "pointer", color: "#666",
            lineHeight: 1, padding: "4px 8px", borderRadius: 4,
          }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "#000")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "#666")}
        >
          ✕
        </button>
        <h3 style={{ margin: "0 0 16px" }}>{title}</h3>
        {children}
      </div>
    </div>
  );
}
