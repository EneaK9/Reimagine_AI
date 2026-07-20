import 'package:flutter/material.dart';
import '../../theme/app_theme.dart';

/// Outlined circular arrow button used across landing sections.
class CircleArrowButton extends StatefulWidget {
  const CircleArrowButton({
    super.key,
    required this.onPressed,
    this.direction = AxisDirection.right,
    this.size = 52,
    this.color = AppTheme.ink,
  });

  final VoidCallback? onPressed;
  final AxisDirection direction;
  final double size;
  final Color color;

  @override
  State<CircleArrowButton> createState() => _CircleArrowButtonState();
}

class _CircleArrowButtonState extends State<CircleArrowButton> {
  bool _hovered = false;

  IconData get _icon {
    switch (widget.direction) {
      case AxisDirection.down:
        return Icons.arrow_downward_rounded;
      case AxisDirection.up:
        return Icons.arrow_upward_rounded;
      case AxisDirection.left:
        return Icons.arrow_back_rounded;
      case AxisDirection.right:
        return Icons.arrow_forward_rounded;
    }
  }

  @override
  Widget build(BuildContext context) {
    final filled = _hovered;
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: GestureDetector(
        onTap: widget.onPressed,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          width: widget.size,
          height: widget.size,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: filled ? widget.color : Colors.transparent,
            border: Border.all(color: widget.color, width: 1.2),
          ),
          child: Icon(
            _icon,
            size: widget.size * 0.38,
            color: filled ? AppTheme.background : widget.color,
          ),
        ),
      ),
    );
  }
}
