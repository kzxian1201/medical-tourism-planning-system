// frontend/components/ui/LiquidGlassModal.js
import React from "react";

const VARIANT_STYLES = {
  danger: {
    confirm: "bg-red-500/30 hover:bg-red-500/50 text-red-200 font-semibold",
    cancel: "bg-gray-600/30 hover:bg-gray-600/50 text-gray-200 font-medium",
    confirmLabel: "Delete",
  },
  warning: {
    confirm: "bg-yellow-500/30 hover:bg-yellow-500/50 text-yellow-200 font-semibold",
    cancel: "bg-gray-600/30 hover:bg-gray-600/50 text-gray-200 font-medium",
    confirmLabel: "Confirm",
  },
  info: {
    confirm: "bg-blue-500/30 hover:bg-blue-500/50 text-blue-200 font-semibold",
    cancel: "bg-gray-600/30 hover:bg-gray-600/50 text-gray-200 font-medium",
    confirmLabel: "OK",
  },
};

const LiquidGlassModal = ({
  isOpen,
  title,
  message,
  onConfirm,
  onCancel,
  variant = "info",
  confirmLabel,
  cancelLabel = "Cancel",
  showCancel = true, // 可选参数，控制是否显示取消按钮
}) => {
  if (!isOpen) return null;

  const styles = VARIANT_STYLES[variant] || VARIANT_STYLES.info;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-gradient-to-br from-gray-900/80 to-gray-800/80 border border-gray-700 rounded-2xl shadow-2xl max-w-md w-full p-6 text-center space-y-6">
        {title && <h3 className="text-xl font-semibold text-primary-light">{title}</h3>}
        {message && <p className="text-gray-300">{message}</p>}
        <div className="flex justify-center space-x-4">
          {showCancel && (
            <button
              onClick={onCancel}
              className={`px-4 py-2 rounded-xl transition-all ${styles.cancel}`}
            >
              {cancelLabel}
            </button>
          )}
          <button
            onClick={onConfirm}
            className={`px-4 py-2 rounded-xl transition-all ${styles.confirm}`}
          >
            {confirmLabel || styles.confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
};

export default LiquidGlassModal;
