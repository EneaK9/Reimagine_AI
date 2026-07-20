import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

/// Shared chrome for composer controls — fixed height + radius from [AppTheme].
class AppControlShell extends StatelessWidget {
  const AppControlShell({
    super.key,
    required this.child,
    this.width,
    this.color,
    this.borderColor,
    this.emphasized = false,
  });

  final Widget child;
  final double? width;
  final Color? color;
  final Color? borderColor;
  final bool emphasized;

  @override
  Widget build(BuildContext context) {
    final bg = emphasized
        ? AppTheme.primaryColor
        : (color ?? AppTheme.inputBackground);
    final side = emphasized
        ? AppTheme.primaryColor
        : (borderColor ?? AppTheme.border);

    return SizedBox(
      width: width,
      height: AppTheme.controlHeight,
      child: Material(
        color: bg,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppTheme.controlRadius),
          side: BorderSide(color: side),
        ),
        clipBehavior: Clip.antiAlias,
        child: child,
      ),
    );
  }
}

/// Square outlined control — same shell as themed text fields.
class AppIconControl extends StatelessWidget {
  const AppIconControl({
    super.key,
    required this.icon,
    this.onTap,
    this.emphasized = false,
    this.loading = false,
    this.tooltip,
  });

  final IconData icon;
  final VoidCallback? onTap;
  final bool emphasized;
  final bool loading;
  final String? tooltip;

  @override
  Widget build(BuildContext context) {
    final enabled = onTap != null && !loading;
    final iconColor = emphasized
        ? Colors.white
        : (enabled ? AppTheme.ink : AppTheme.textMuted);

    final child = AppControlShell(
      width: AppTheme.controlHeight,
      emphasized: emphasized,
      child: InkWell(
        onTap: enabled ? onTap : null,
        overlayColor: const WidgetStatePropertyAll(AppTheme.hoverGray),
        child: Center(
          child: loading
              ? SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: emphasized ? Colors.white : AppTheme.primaryColor,
                  ),
                )
              : Icon(icon, size: 18, color: iconColor),
        ),
      ),
    );

    if (tooltip == null) return child;
    return Tooltip(message: tooltip!, child: child);
  }
}

/// Single-line text field matching [AppIconControl] height/radius exactly.
class AppControlField extends StatelessWidget {
  const AppControlField({
    super.key,
    required this.controller,
    this.focusNode,
    this.hintText,
    this.enabled = true,
    this.onChanged,
    this.onSubmitted,
    this.textCapitalization = TextCapitalization.none,
  });

  final TextEditingController controller;
  final FocusNode? focusNode;
  final String? hintText;
  final bool enabled;
  final ValueChanged<String>? onChanged;
  final ValueChanged<String>? onSubmitted;
  final TextCapitalization textCapitalization;

  static const _textStyle = TextStyle(
    color: AppTheme.ink,
    fontSize: 14,
    height: 1.0,
  );

  static const _hintStyle = TextStyle(
    color: AppTheme.textMuted,
    fontSize: 14,
    height: 1.0,
  );

  @override
  Widget build(BuildContext context) {
    // Explicit vertical padding centers 14px text in the 44px shell.
    // Material TextField vertical align is unreliable on Flutter web.
    const vPad = (AppTheme.controlHeight - 14) / 2; // → 15
    return AppControlShell(
      child: CupertinoTextField(
        controller: controller,
        focusNode: focusNode,
        enabled: enabled,
        placeholder: hintText,
        placeholderStyle: _hintStyle,
        style: _textStyle,
        cursorColor: AppTheme.primaryColor,
        cursorHeight: 14,
        textCapitalization: textCapitalization,
        padding: const EdgeInsets.fromLTRB(14, vPad, 14, vPad),
        decoration: null,
        maxLines: 1,
        onChanged: onChanged,
        onSubmitted: onSubmitted,
      ),
    );
  }
}
