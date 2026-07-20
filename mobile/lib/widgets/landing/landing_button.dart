import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../theme/app_theme.dart';

enum LandingButtonVariant { primary, secondary }

/// Rectangular filled landing CTA (orange or muted gray).
class LandingButton extends StatefulWidget {
  const LandingButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.variant = LandingButtonVariant.primary,
  });

  final String label;
  final VoidCallback? onPressed;
  final LandingButtonVariant variant;

  @override
  State<LandingButton> createState() => _LandingButtonState();
}

class _LandingButtonState extends State<LandingButton> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    final isPrimary = widget.variant == LandingButtonVariant.primary;
    final base = isPrimary ? AppTheme.primaryColor : AppTheme.secondaryButton;
    final hover =
        isPrimary ? AppTheme.primaryDark : const Color(0xFFC9C4BB);
    final fg = isPrimary ? Colors.white : AppTheme.ink;

    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: GestureDetector(
        onTap: widget.onPressed,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 160),
          padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 14),
          decoration: BoxDecoration(
            color: _hovered ? hover : base,
            borderRadius: BorderRadius.circular(4),
          ),
          child: Text(
            widget.label,
            style: GoogleFonts.interTight(
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: fg,
            ),
          ),
        ),
      ),
    );
  }
}
